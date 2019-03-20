import numpy as np
import sys
import traceback
from sklearn.ensemble import AdaBoostClassifier
from sklearn.preprocessing import StandardScaler
from sklearn import svm
from sklearn.model_selection import GridSearchCV
from metaspam.featureextraction.sqlitebackend import SQLiteBackend
from metaspam.featureextraction.featureencoder import FeatureEncoder
from scipy.sparse import *
from sklearn.externals import joblib


"""
Class used for the evaluation part of the thesis
"""


class TestSuite:
    def __init__(self, db, featfile=None, featlabels=None, featencfile=None, encignore=None):
        """
        :param db: path to db file
        :param featfile: file with features, if using pickled features (never actually used)
        :param featlabels: file with labels, if using pickled features (never actually used)
        :param featencfile: file with featureencoder object, if using pickled features (never actually used)
        :param encignore: path to pass through "encignore" file
        """
        self.db = SQLiteBackend(db)
        if featfile is not None:
            self.feats = joblib.load(featfile)
        if featlabels is not None:
            self.featlabels = joblib.load(featlabels)
        if featencfile is not None:
            self.featenc = joblib.load(featencfile)
        self.encignore = encignore

    def extractFeatures(self, delete=[], filtr=False, cutTime=None, autodel=False):
        """
        Extract training features from mails up to specific time in the database. Only used for Pallas dataset
        :param delete: features to disregard
        :param filtr: Use filter?
        :param cutTime: Time at which to transition between training and test set
        :param autodel: Use autodetection of features with low information content
        """
        if delete == "default":
            delete = ['todomain', 'fromdomain', 'fromdomainfqn', 'msgiddomain', 'X-Mailer', 'Disposition-Notification-To', 'DomainKey-Signature', 'In-Reply-To', 'IronPort-PHdr', '', 'Authentication-Results', 'Bcc', 'BCC', 'CC', 'Cc', 'cc', 'Content-type', 'thread-index', 'DKIM-Filter']
        if autodel:
            delete.extend(self.db.identifyDelFeatures())
        self.featenc = FeatureEncoder(self.db, ignorepath=self.encignore, filtr=filtr, cutTime=cutTime, delFeatures=delete)
        self.featenc.toFile()
        print("Written feature names to File <currentFeat.ind>")

        mailIDs = self.db.getMailList(cutTime=cutTime)
        (self.feats, self.featlabels) = self.extract(mailIDs)

        print("All Features extracted")
        sparsity = (float(self.feats.count_nonzero())/(float(len(mailIDs)) * float(self.featenc.vectorLen)))*100
        print("Sparsity: " + str(sparsity) + "%")

    def extractTestFeatures(self, startTime=None):
        """
        Extract corresponding test features to "extractFeatures". Only used for Pallas dataset
        :param startTime: db time at which to start extracting test features
        """
        mids = self.featenc.db.getMailList(startTime=startTime)
        (self.test_feats, self.test_labels) = self.extract(mids)
        print("All training features extracted")

    def extract(self, mids):
        """
        Generic extract method
        :param mids: ids of mails to extract features from
        :return: features and labels
        """
        last = None
        current = None
        label = []
        featureVecs = []
        for idx, mid in enumerate(mids):
            featureVecs.append(self.featenc.mapMail(mid))
            if ((idx % 100 == 0) and not(idx == 0)) or idx == (len(mids) -1):
                current = csr_matrix(featureVecs, dtype="float64")
                if last != None:
                    last = vstack([last, current])
                else:
                    last = csr_matrix(current, dtype="float64")
                featureVecs = []
                sys.stdout.flush()
                comp = (float(idx)/float(len(mids))) * 100
                sys.stdout.write("%d%% completed. \r" % (comp))
            label.append(self.featenc.db.getEval(mid))
        sys.stdout.flush()
        return (last, label)


    def AdaboostClassifier(self, n=200, printfeat=False):
        """
        Generic AdaBoost Classifier method
        :param n: Number of estimators
        :param printfeat: Print out features importances?
        :return: Trained classifier
        """
        clf = AdaBoostClassifier(n_estimators=200)
        clf.fit(self.feats, self.featlabels)

        if printfeat:
            self.featenc.toFile()
            fp = open("currentFeat.ind", "r")
            descr = fp.read().split("\n")
            fp.close()
            fi = np.copy(clf.feature_importances_)

            for i in range(200):
                armax = np.argmax(fi)
                if fi[armax] == 0:
                    break
                print("P = " + str(fi[armax]) + ": " + descr[armax])
                fi[armax] = 0

 #       print(clf.score(self.test_feats, self.test_labels))
        return clf

    def SVMClassifier(self):
        """
        Generic lin. SVM classifier method
        :return: Trained classifier
        """
        #SVM needs scaling
        sc = StandardScaler(with_mean=False)
        sc.fit(self.feats)
        X_train_std = sc.transform(self.feats)
        self.x_test_std = sc.transform(self.test_feats)

        #Grid search to find best classifier
        params = parameters = {'loss': ('hinge', 'squared_hinge'), 'C': list(np.arange(0.00008, 0.0001, 0.000001))}
        clf = svm.LinearSVC()
        grd = GridSearchCV(clf, params)
        grd.fit(X_train_std, self.featlabels)
        return grd

    def randomSplit(self, split=0.7, traintable="traintable", testtable="testtable", limit=None, explval=10, delcutoff=0.4, metalvl=0, evalsize=0):
        """
        Main method for random sub sampling evaluation
        :param split: Train/Test split ratio
        :param traintable: name of table with training mail ids
        :param testtable: name of table with test mail ids
        :param limit: How many emails to use for trainign
        :param explval: How many explicit values per feature to keep
        :param delcutoff: Cutoff value for autodelete features
        :param metalvl: 0 - All features, 1 - no body feautes, 2 - no body features, no attachment features
        :param evalsize: Size of validation set, if used
        """
        self.db.query("SELECT count(*) FROM mails")
        size = self.db.cur.fetchall()[0][0]
        size = int(size*split)
        if limit is None:
            self.db.query("CREATE TABLE " + traintable + " AS SELECT id FROM mails ORDER BY random() LIMIT 1," + str(size))
            if testtable == "testtable":
                self.db.query("CREATE TABLE " + testtable + " AS SELECT id FROM mails EXCEPT SELECT id FROM " + traintable)
            else:
                self.db.query("DROP TABLE traintable")
                try:
                    self.db.query("DROP TABLE helper")
                except:
                    pass
                self.db.query("CREATE TABLE helper AS SELECT id FROM mails EXCEPT SELECT id FROM " + testtable)
                self.db.query("CREATE TABLE " + traintable + " AS SELECT id FROM helper ORDER BY random() LIMIT 1," + str(size))
        else:
            try:
                self.db.query("DROP TABLE helper")
            except:
                pass
            self.db.query("CREATE TABLE " + traintable + " AS SELECT id FROM mails ORDER BY random() LIMIT 1," + str(limit))
            if testtable == 'testtable':
                self.db.query("CREATE TABLE helper AS SELECT id FROM mails EXCEPT SELECT id FROM " + traintable)
                if evalsize == 0:
                    self.db.query("CREATE TABLE " + testtable + " AS SELECT id FROM helper ORDER BY random() LIMIT 1," + str(int(limit*(1-split))))
                else:
                    self.db.query("CREATE TABLE " + testtable + " AS SELECT id FROM helper ORDER BY random() LIMIT 1," + str(evalsize))
            else:
                self.db.query("DROP TABLE traintable")
                try:
                    self.db.query("DROP TABLE helper")
                except:
                    pass
                self.db.query("CREATE TABLE helper AS SELECT id FROM mails EXCEPT SELECT id FROM " + testtable)
                self.db.query("CREATE TABLE " + traintable + " AS SELECT id FROM helper ORDER BY random() LIMIT 1," + str(size))

        try:
            self.db.query("SELECT id FROM " + traintable)
            mids = self.db.getListSingleVal()

#Enrondel            delete = ['todomain', 'fromdomain', 'fromdomainfqn', 'msgiddomain', 'X-Mailer', 'Disposition-Notification-To', 'DomainKey-Signature', 'In-Reply-To', 'IronPort-PHdr', '', 'Authentication-Results', 'Bcc', 'BCC', 'CC', 'Cc', 'cc', 'Content-type', 'thread-index', 'DKIM-Filter', 'X-bcc', 'X-MimeOLE', 'Mime-Version', 'geovec', 'msgidfromdom', 'tofromdom', 'reccnt', 'tomsgiddom', 'X-From', 'X-To', 'X-cc', 'X-FileName', 'MIME-Version', 'X-MSMail-Priority', 'X-Priority', 'X-Keywords', 'rec_0_tls', 'replyerrordom', 'rec_0_by', 'tocnt']
            delete = ['todomain', 'fromdomain', 'fromdomainfqn', 'msgiddomain', 'X-Mailer', 'Disposition-Notification-To', 'DomainKey-Signature', 'In-Reply-To', 'IronPort-PHdr', '', 'Authentication-Results', 'Bcc', 'BCC', 'CC', 'Cc', 'cc', 'Content-type', 'thread-index', 'DKIM-Filter']
            delete.extend(self.db.identifyDelFeatures(cutoff=delcutoff))
            if metalvl == 1:
                delete.extend(['bodylen', 'bodylang'])
            if metalvl == 2:
                delete.extend(['bodylen', 'bodylang', 'attach*'])
            self.featenc = FeatureEncoder(self.db, ignorepath=self.encignore, filtr=True, table=traintable, delFeatures=delete, explval=explval)
            print("Featureencoder created.")
            print("Extracting training features....")
            (self.feats, self.featlabels) = self.extract(mids)
            print("Done.")
            print("Extracting test features....")
            self.db.query("SELECT id FROM " + testtable)
            self.mids = self.db.getListSingleVal()
            (self.test_feats, self.test_labels) = self.extract(self.mids)
            print("Done.")

            if delete:
                self.db.query("DROP TABLE " + traintable)
                if testtable == "testtable":
                    self.db.query("DROP TABLE " + testtable)
        except:
            traceback.print_exc()
            self.db.query("DROP TABLE " + traintable)
            if testtable == "testtable":
                self.db.query("DROP TABLE " + testtable)


#ts = TestSuite("comspam.db", encignore="encIgnoreEnron")
#svmres = []
#adares = []

#for i in range(5):
#    print("Split " + str(i+1) + ": \n")
#    ts.randomSplit(limit=3000)
#    svmc = ts.SVMClassifier()
#    svmres.append(svmc.score(ts.x_test_std, ts.test_labels))
#    adares.append(ts.AdaboostClassifier(printfeat=False).score(ts.test_feats, ts.test_labels))

#ts.randomSplit(limit=3000)
#clf = ts.AdaboostClassifier(printfeat=True)

#for i in range(ts.test_feats.shape[0]):
#    res = clf.predict(ts.test_feats.getrow(i))

#    if res != ts.test_labels[i]:
#        ts.db.cur.execute("SELECT eval, smtpfrom, subject FROM mails WHERE id='" + ts.mids[i] + "'")
    #result.append([str(enc.db.cur.fetchall()), clf.predict_proba(x_test.getrow(i))])
#        print(str(ts.db.cur.fetchall()) + ";  " + str(clf.predict_proba(ts.test_feats.getrow(i))))
    #wrong += 1



#print("SVM Results: " + str(svmres))
#print("Adaboost Results: " + str(adares))

#ts.AdaboostClassifier()
