from backend import Backend
import os.path
import sqlite3 as lite
from StringIO import StringIO

class SQLiteBackend(Backend):
    """
    Implements a backend for using SQLite3.
    See Backend class for further comments.
    """

    def __init__(self, data, idDB="mails", featureDB="features", orderFile="order", toMem=False):
        if not(toMem):
            self.path = data
            self.idDB = idDB
            self.featureDB = featureDB
            self.orderFile = orderFile
            #Use db if given, otherwise create new db
            if os.path.isfile(self.path):
                self.connect()
            else:
                self.createDBAndConnect()
        else: #Write given DB to memory and use memory DB from here.
            con = lite.connect(data)
            con.text_factory = str
            tempfile = StringIO()
            for line in con.iterdump():
                tempfile.write('%s\n' % line)
            con.close()
            tempfile.seek(0)
            self.con = lite.connect(":memory:")
            self.con.text_factory = str
            self.cur = self.con.cursor()
            self.cur.executescript(tempfile.read())
            self.con.commit()

    def connect(self):
        """
        Connect to given db file.
        """
        self.con = lite.connect(self.path, timeout=25, check_same_thread=False)
        self.con.text_factory = str
        self.cur = self.con.cursor()

    def refreshConnection(self):
        """
        Renew connection. Useful in case of unpickleing db handler.
        """
        self.con = lite.connect(self.path, timeout=25, check_same_thread=False)
        self.con.text_factory = str
        self.cur = self.con.cursor()
        print("Reconnected!")

    def createDBAndConnect(self):
        """
        Create new db if none was given at instanciation time.
        """
        self.connect()
        self.cur.execute("CREATE TABLE mails ('msgid', 'date', 'serverdate', 'from', 'to', 'subject', 'id', 'smtpfrom', 'smtpto', 'size', 'eval')")
        self.cur.execute("CREATE TABLE features ('id', 'feature', 'value')")
        self.cur.execute("CREATE INDEX indexID ON features (id)")
        self.cur.execute("CREATE INDEX indexFeature ON features (feature)")
        self.cur.execute("CREATE INDEX indexIDFeature ON features (id, feature)")
        self.con.commit()

    def disconnect(self):
        self.con.commit() #This is not a good idea. Caution.
        self.con.close()

    def queryVal(self, qu, val):
        """
        Query with given values outside of string.
        :param qu: Query String
        :param val: Given value(s)
        :return: execute result
        """
        return self.cur.execute(qu, val)


    def query(self, qu):
        """
        Query without given parameters.
        :param qu: Query String
        :return: execite result
        """
        return self.cur.execute(qu)

    def buildValueStr(self, dat):
        """
        Build a String of the necessary format for SQL insertion
        """
        valueStr = "("
        for i in range(len(dat)):
            valueStr += "?,"
        valueStr = valueStr[:-1] + ")"
        return valueStr

    def insert(self, data, into):
        """
        Insert into given table
        :param data: data to insert
        :param into: table to insert into
        """
        if not(isinstance(data, list)):
            valueStr = self.buildValueStr(data)
            self.cur.execute("INSERT INTO " + into + " VALUES " + valueStr, data)
        else:
            valueStr = self.buildValueStr(data[0])
            self.cur.executemany("INSERT INTO " + into + " VALUES " + valueStr, data)

    def insertSpam(self, data, into):
        """
        Explicitly insert spam.
        :param data: data to insert
        :param into: table to insert into
        """
        data = list(data)
        data[-1] = 1
        data = tuple(data)
        self.insert(data, into)

    def killSpamassEmails(self):
        """
        Delete emails of SpamAssassin instance.
        """
        qu = "SELECT id FROM mails WHERE 'from'='ignore@compiling.spamassassin.taint.org'"
        self.query(qu)
        ids = self.getListSingleVal()
        for mid in ids:
            self.query("DELETE FROM mails WHERE id='" + str(mid) + "'")
        self.con.commit()

    def getListSingleVal(self):
        """
        Returns a list from the result of fetchall() where
        we only expect one value per returned tuple
        """
        result = []
        for item in self.cur.fetchall():
            result.append(str(item[0])) #Maybe keep unicdoe string?
        return result

    def getFeatureList(self, cutTime=None, table=None):
        """
        Get list of used features in db.
        :param cutTime: time up to which to extract features
        :param table: optional table for more restricted feature list
        :return: List of Features
        """
        if cutTime is None and table is None :
            qu = "SELECT DISTINCT feature FROM features ORDER BY feature"
        elif cutTime is not None and table is None:
            qu = "SELECT DISTINCT feature FROM features, mails WHERE features.id = mails.id AND mails.serverdate < '" + cutTime + "' ORDER BY features.feature"
        elif cutTime is None and table is not None:
            qu = "SELECT DISTINCT feature FROM features, mails, " + table + " WHERE mails.id = " + table + ".id AND mails.id = features.id ORDER BY features.feature"
        else:
            qu = "SELECT DISTINCT feature FROM features, mails, " + table + " WHERE mails.id = " + table + ".id AND mails.id = features.id AND mails.serverdate < '" + cutTime + "' ORDER BY features.feature"
        self.query(qu)
        return self.getListSingleVal()


    def saveOrderToFile(self):
        """
        Save calculated order
        """
        try:
            f = open(self.orderFile, "w")
            for item in self.getFeatureList():
                f.write(str(item) + "\n")
            f.close()
        except:
            print("Error: Saving order failed!")

    def getMailList(self, startTime=None, cutTime=None, table=None):
        """
        Get list of mail ids.
        :param startTime: Time of emails at which to start id extraction
        :param cutTime: Time of emails at which to stop id extraction
        :param table: Use ids of specific table given
        :return: List of mail ids
        """
        if startTime is None and cutTime is None:
            qu = "SELECT DISTINCT id FROM mails"
        if startTime is not None:
            qu = "SELECT DISTINCT id FROM mails WHERE serverdate > '" + startTime + "'"
        if cutTime is not None:
            qu = "SELECT DISTINCT id FROM mails WHERE serverdate < '" + cutTime + "'"
        if table is not None:
            qu = "SELECT id FROM " + table
        self.query(qu)
        return self.getListSingleVal()

    def getValueList(self, feature, cutTime=None, table=None):
        """
        Get all values of a specific feature.
        :param feature: Feature we want distinct values of
        :param cutTime: Time of emails at which to start looking for values
        :param table: table on which to look for values.
        :return: List of distinct values for feature
        """
        if cutTime is None:
            qu = "SELECT DISTINCT value FROM features WHERE feature=?"
        else:
            qu = "SELECT DISTINCT value FROM features, mails WHERE features.id = mails.id AND mails.serverdate < '" + cutTime + "' AND feature=?"
        if table is not None:
            qu = "SELECT DISTINCT value FROM features, mail, " + table + " WHERE mails.id = " + table + ".id AND features.id = mails.id AND feature=?"
        self.queryVal(qu, (feature,))
        return self.getListSingleVal()

    def getMailFeatureList(self, dbid):
        """
        Get features of one email.
        :param dbid: id of email
        :return: list of all distinct features of email dbid.
        """
        qu = "SELECT DISTINCT feature FROM features WHERE id='" + dbid + "'"
        self.query(qu)
        return self.getListSingleVal()

    def getMailValueList(self, dbid, feature):
        """
        Get all values of feature from mail dbid
        :param dbid: id of email
        :param feature: feature to get values of
        :return: list of values
        """
        qu = "SELECT value FROM features WHERE id=? AND feature=?"
        self.queryVal(qu, (dbid, feature))
        return self.getListSingleVal()

    def getEval(self, dbid):
        """
        Get classification of email dbid
        :param dbid: id of email
        :return: classification (spam/ham)
        """
        qu = "SELECT eval FROM mails WHERE id='" + dbid + "'"
        self.query(qu)
        return int((self.cur.fetchall()[0][0]))

    def getDescValueCountList(self, value):
        """
        Get list of values for specific feature in descending order of occurences.
        :param value: name of feature
        :return: list of values in decending order.
        """
        qu = "SELECT DISTINCT value, count(value) AS countof FROM (SELECT feature, value FROM features WHERE feature=?) GROUP BY value ORDER BY countof DESC"
        self.queryVal(qu, (value,))
        return self.cur.fetchall()

    def getIDMails(self):
        """
        Get identifying information for all emails
        :return: List of identifying information
        """
        qu = "SELECT id, serverdate, subject, smtpfrom FROM mails"
        self.query(qu)
        return self.cur.fetchall()

    def identifyDelFeatures(self, cutoff=0.65):
        """
        Identify all features to be disregarded for classification because of low information content
        :param cutoff: time of email at which to start looking for features
        :return: list of features to be disregarded
        """
        result = []
        feats = self.getFeatureList()
        for feat in feats:
            self.cur.execute("SELECT count(*) FROM features WHERE feature=?", (feat,))
            noc = float(self.cur.fetchall()[0][0])
            self.cur.execute("SELECT count(DISTINCT value) FROM features WHERE feature=?", (feat,))
            nou = float(self.cur.fetchall()[0][0])
            if nou/noc > cutoff:
                result.append(feat)
        return result

