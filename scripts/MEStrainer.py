import argparse
import ConfigParser
import sqlite3
import sys
import datetime
from sklearn.ensemble import AdaBoostClassifier
from MES.featureextraction.sqlitebackend import SQLiteBackend
from MES.featureextraction.featureencoder import FeatureEncoder
from scipy.sparse import *
from sklearn.externals import joblib
from dateutil.parser import parse

"""
Script used for training an AdaBoost classifier with one or multiple given dbs
"""


def extract(mids, featenc):
    """
    Generic extract method
    :param mids: ids of mails to extract features from
    :return: features and labels
    """
#   last holds stacked results of previous iterations
    last = None
    current = None
    label = []
    featureVecs = []
    for idx, mid in enumerate(mids):
        featureVecs.append(featenc.mapMail(mid))
        if ((idx % 100 == 0) and not (idx == 0)) or idx == (len(mids) - 1):
            #Sparse representation with csr_matrix for speed and size improvements
            current = csr_matrix(featureVecs, dtype="float64")
            if last != None:
                last = vstack([last, current])
            else:
                last = csr_matrix(current, dtype="float64")
            featureVecs = []
            #Pretty prints
            sys.stdout.flush()
            comp = (float(idx) / float(len(mids))) * 100
            sys.stdout.write("%d%% completed. \r" % (comp))
        label.append(featenc.db.getEval(mid))
    sys.stdout.flush()
    return (last, label)

#Config and cmd-line argument parsing stuff
config = ConfigParser.SafeConfigParser()
config.read("mes.cfg")
cutoffval = config.getfloat('mestrainer', 'cutoff')
expl = config.getint('mestrainer', 'explval')
tsize = config.getint('mestrainer', 'trainingsize')
estimators = config.getint('mestrainer', 'n_estimators')
encignorepath = config.get('mestrainer', 'encignore')
parser = argparse.ArgumentParser()
parser.add_argument("-a", "--adaboost", nargs='+', help="Path of file, to which pickled AdaBoost classifier should be written.", required=True)
parser.add_argument("-db", "--database", nargs='+', help="Path of database file(s) from which to use emails for training.", required=True)
parser.add_argument("-odb", "--outputdb", nargs='+', help="Path of database to which the training features should be written", required=True)
parser.add_argument("-m", "--multiplier", nargs='+', help="Database multipliers for amount of emails used for training per database. Must be entered in the same order as database files.")
args = parser.parse_args()

def alreadyExists(db, idfeats):
    lowerdate = parse(idfeats[2]) - datetime.timedelta(0,60)
    upperdate = lowerdate + datetime.timedelta(0,120)
    qu = "SELECT * FROM mails WHERE serverdate > ? AND serverdate < ? AND smtpfrom=? AND subject=?"
    qudata = (str(lowerdate), str(upperdate), idfeats[7], idfeats[5])
    db.cur.execute(qu, qudata)
    res = db.cur.fetchall()
    if len(res) > 0:
        return True
    else:
        return False



#Calculate ratio needed for extracting the correct amount of emails from each db
sum = 0
for mult in args.multiplier:
    sum += float(mult)

mult = int(float(tsize)/float(sum))

#Connect to new training data db
newdb = SQLiteBackend(args.outputdb[0])

#Copy data from each db into newdb
for idx, db in enumerate(args.database):
    print("Copying data from Database " + str(idx) + "...")
    con = sqlite3.connect(db)
    con.text_factory = str
    cur = con.cursor()
    limit = int(float(args.multiplier[idx]) * mult)

    mails = cur.execute("SELECT * FROM mails ORDER BY random() LIMIT 1," + str(limit))
    #remember ids
    ids = []
    cols = ('msgid', 'date', 'serverdate', 'from', 'to', 'subject', 'id', 'smtpfrom', 'smtpto', 'size', 'eval')

    #First 'mails'table
    #Try five rounds of finding non duplicates, if there are any.
    #We go on if the amount of duplicates is less than 10% of the amount of emails extracted
    #from the current db.
    doubles = 0
    rounds = 5
    for i in range(rounds):
        for row in mails.fetchall():
            if alreadyExists(newdb, row):
                doubles +=1
                continue
            ins = 'INSERT INTO %s %s VALUES (%s)' % ('mails', cols, ','.join(['?'] * len(cols)))
            newdb.cur.execute(ins, row).fetchall()
            ids.append(row[6])
        if doubles < 0.1*limit:
            break
        else:
            print("Found " + str(doubles) + " duplicates in DB " + str(idx) +". Trying to find non-duplicates, if available. Try " + str(i) + " of " + str(rounds) + ".")
            mails = cur.execute("SELECT * FROM mails ORDER BY random() LIMIT 1," + str(doubles))
            doubles = 0

    cols = ('id', 'feature', 'value')

    #Then get features via ids and insert into newdb
    for id in ids:
        feats = cur.execute("SELECT * FROM features WHERE id='" + id + "'")
        for row in feats.fetchall():
            ins = 'INSERT INTO %s %s VALUES (%s)' % ('features', cols, ','.join(['?'] * len(cols)))
            newdb.cur.execute(ins, row)
    con.close()
    print("Done.")
newdb.con.commit()
print("Training database " + args.outputdb[0] + " created.")


newdb.query("SELECT id FROM mails")
mids = newdb.getListSingleVal()
#Disregard these features
delete = ['todomain', 'fromdomain', 'fromdomainfqn', 'msgiddomain', 'X-Mailer', 'Disposition-Notification-To',
          'DomainKey-Signature', 'In-Reply-To', 'IronPort-PHdr', '', 'Authentication-Results', 'Bcc', 'BCC',
          'CC', 'Cc', 'cc', 'Content-type', 'thread-index', 'DKIM-Filter']
#And these automatically detected ones
delete.extend(newdb.identifyDelFeatures(cutoff=cutoffval))

print("Creating FeatureEncoder...")
featenc = FeatureEncoder(newdb, ignorepath=encignorepath, filtr=True, delFeatures=delete, explval=expl)
print("Done.")
print("Extracting training features...")
(feats, featlabels) = extract(mids, featenc)
print("Done.")

print("Training AdaBoost Classifier...")
clf = AdaBoostClassifier(n_estimators=estimators)
clf.fit(feats, featlabels)
print("Done.")

joblib.dump((clf, featenc), args.adaboost[0])
print("Written classifier to pickled file " + args.adaboost[0] + ".")

