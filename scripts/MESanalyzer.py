import argparse
import numpy as np
from MES.featureextraction.sqlitebackend import SQLiteBackend
from MES.featureextraction.featureencoder import FeatureEncoder
from MES.mail.mail import Mail
from sklearn.externals import joblib

"""
Script used to analyze a pickled AdaBoost Classifier
"""


parser = argparse.ArgumentParser()
#If only the next one or two arguments are given, the feature importances will be displayed
parser.add_argument("-a", "--adaboost", help="Path to pickled classifier file.", required=True)
parser.add_argument("-n", "--number", help='How many feature importances to print.')
#If the next two are given as well, one or multiple emails are classified and their class probabilites claculated.
parser.add_argument("-db", "--database", help='Path to database file')
parser.add_argument("-mid", "--mailid", nargs='+', help="Mail ID(s) to be classified")
args = parser.parse_args()

(clf, featenc) = joblib.load(args.adaboost)

if args.database is not None and args.mailid is not None:
    #DB and mID(s) were given
    db = SQLiteBackend(args.database)
    featenc.db = db
    for mid in args.mailid:
        probs = clf.predict_proba(featenc.mapMail(mid).reshape(1,-1))
        print("Class probabilities for mail " + mid + ": " + str(probs[0]))
else:
    #Only display feature importances
    print("Feature Importances for given classifier:")
    print("<importance>: <feature>[: <value>]")
    featenc.toFile()
    fp = open("currentFeat.ind", "r")
    descr = fp.read().split("\n")
    fp.close()
    fi = np.copy(clf.feature_importances_)
    no = 200
    if args.number is not None:
        no = int(args.number)
    for i in range(no):
        armax = np.argmax(fi)
        if fi[armax] == 0:
            break
        print(str(fi[armax]) + ": " + descr[armax])
        fi[armax] = 0