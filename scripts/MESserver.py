import Queue
import time
import threading
import email
import os
import signal
import sys
import geoip2.database
import ConfigParser
import argparse
from MES.featureextraction.sqlitebackend import SQLiteBackend
from MES.mail.mail import Mail
from twisted.internet.protocol import Factory, Protocol
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet import reactor
from sklearn.externals import joblib

"""
Script used for receiving emails send to a port. Emails can be
classified on the fly if a pickled AdaBoost classifier is given.
"""


#Global variables for inter-thread communication
global consumerThread
global classThread
global geopath
global classify


class StoppableThread(threading.Thread):
    """
    Thread which can be stopped by calling a method
    """

    def __init__(self, q, path, ignore, classQ=None):
        super(StoppableThread, self).__init__()
        self._stop = threading.Event()
        self.queue = q
        self.dbpath = path
        self.ignore = ignore
        if classQ is not None:
            self.classQ = classQ

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()

    def run(self):
        """
        Consumer method which takes queue elements and writes
        them to a DB
        """
        db = SQLiteBackend(self.dbpath)
        global geopath
        global classify
        geoipdb = geoip2.database.Reader(geopath)
        #start = ""
        cnt = 0
        while not(self.stopped()):
            try:
                #Timeout necessary to be able to check stopped criterion
                msg = self.queue.get(timeout=5)
                """print("try msg:" + msg)"""
            except:
                continue
            stream = msg.split("\n")[0]
            stream = stream.replace('\r','')
            if stream == "STREAM":
                #email completely received, create mail object
                fin = "\n".join(msg.split("\n")[1:])
#                print(">> fin: " + fin)
                mail = Mail(email.message_from_string(fin), geodb=geoipdb, ignorelist=self.ignore, size=sys.getsizeof(fin))
#                print mail
#                print mail.mail.keys()
#                print mail.extractFeatures()
                try:
                    #Try to insert email into database
                    idf = mail.idFeatures()
                    db.insert(idf, 'mails')
                    db.insert(mail.extractFeatures(), 'features')
                    db.con.commit()
                    cnt += 1
                    #If classifier is given, put email id into query for classification
                    if classify:
                        self.classQ.put(idf[6])
                    #print no. of mails consumed
                except Exception as e:
                    #if any error encountered, commit everything up until this point
                    db.con.commit()
                    print("Encountered an error. Committing everything and continuing.")
                    print(str(e))
                    continue
#                    db.con.close()
#                    print("Everything commited to DB. Bye")
                if cnt % 5 == 0:
                    db.con.commit()
                    print("Commited a total of " + str(cnt) + " mails.")
#                start = "\n".join(msg.split("\n")[1:])
#            else:
#                if not(start == ""):
#                    start += msg
        print("Received terminate...Comitting....")
        db.con.commit()
        db.disconnect()
        print("Done. Bye")


class ClassifyThread(threading.Thread):
    """
    Thread which can be stopped by calling a method, used for classification with
    given AdaBoost classifier.
    """

    def __init__(self, q, db, clf, featenc, respath):
        super(ClassifyThread, self).__init__()
        self._stop = threading.Event()
        self.queue = q
        self.clf = clf
        self.featenc = featenc
        self.db = SQLiteBackend(db)
        self.resFile = open(respath, 'a')
        self.featenc.db = self.db

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()

    def run(self):
        """
        Consumer method which takes queue elements and
        classifies them with the given AdaBoost classifier.
        """

        while not(self.stopped()):
            try:
                #Timeout necessary to be able to check stopped criterion
                mid = self.queue.get(timeout=5)
            except:
                continue
            try:
                strRes = "HAM"
                #Classify email
                res = self.clf.predict(self.featenc.mapMail(mid).reshape(1,-1))[0]
                if res == 1:
                    strRes = "SPAM"
                #Get necessary information for log file
                print(mid)
                idfeats = self.db.cur.execute("SELECT [serverdate], [smtpfrom], [smtpto], [to], [msgid], [subject], [id] FROM mails WHERE id='" + mid + "'").fetchall()[0]
                fileStr = str(idfeats[0]).replace(":", "-") + ":" + idfeats[1] + ":" + idfeats[2] + ":" +idfeats[3] + ":" + idfeats[4] + ":" + idfeats[5] + ":" + idfeats[6] + ":" + str(res) + "\n"
                #Write to log file
                self.resFile.write(fileStr)
                print("Classified mail with mID " + mid + ", Result: " + strRes)
            except Exception as e:
                print(str(e))
                print("Error classifying email.")

        print("Classification Thread received terminate...")
        self.db.disconnect()
        self.resFile.close()
        print("Done. Bye")




class EmailReceiver(Protocol):
    """
    Keeps packets from multiple socket connections
    in order and assembles emails
    """
    def dataReceived(self, data):
        self.msg += data

    def connectionMade(self):
        self.msg = ""

    def connectionLost(self, reason):
        """
        Producer puts complete email into queue
        """
        self.factory.q.put(self.msg)


class EmailReceiverFactory(Factory):
    """
    Creates EmailReceivers for each connection
    """
    protocol = EmailReceiver

    def __init__(self, queue):
        self.q = queue


def signal_handler(signal, frame):
    """
    Handle KeyboardInterrupt
    """
    print("Received Kill Signal")
    global consumerThread
    global classify
    consumerThread.stop()
    print("Set Stop!")
    while consumerThread.isAlive():
        time.sleep(2)
    if classify:
        global classThread
        classThread.stop()
        while classThread.isAlive():
            time.sleep(2)
    reactor.stop()
    print("Exited savely")
    try:
        sys.exit()
    except:
        os._exit(1)


classify = False


#Config and cmd-line parameter parsing stuff
config = ConfigParser.SafeConfigParser()
config.read("mes.cfg")

geopath = config.get('messerver', 'geo')
port = config.getint('messerver', 'port')
ignorepath = config.get('messerver', 'ignore')
resultpath = config.get('messerver', 'result')
parser = argparse.ArgumentParser()
parser.add_argument("-a", "--adaboost", help="Path to pickled classifier.")
parser.add_argument("-r", "--result", help="Path to file in which classifications are supposed to be written to.")
parser.add_argument("-odb", "--outputdb", help="Path of database to which email features should be written.", required=True)
args = parser.parse_args()


dbf = args.outputdb
print("Creating new DB file: " + str(dbf))
print("Done. Starting Server.")

if args.adaboost is not None:
    #Classifier was given, create classification thread.
    #Unpickle classifier and set featureencoder db to new db used in the consumer thread.
    (clf, featenc) = joblib.load(args.adaboost)
    classifierQ = Queue.Queue()
    classify = True
    classThread = ClassifyThread(classifierQ, dbf, clf, featenc, resultpath)
    classThread.daemon = True
    classThread.start()

#Create thread for writing new emails to db
consumerQ = Queue.Queue()
if classify:
    consumerThread = StoppableThread(consumerQ, dbf, ignorepath, classQ=classifierQ)
else:
    consumerThread = StoppableThread(consumerQ, dbf, ignorepath)
consumerThread.daemon = True
consumerThread.start()

#Initialize kill signal handler
signal.signal(signal.SIGINT, signal_handler)

endpoint = TCP4ServerEndpoint(reactor, port)
endpoint.listen(EmailReceiverFactory(consumerQ))
#Run reactor thread
print("Server started")
reactor.run()
