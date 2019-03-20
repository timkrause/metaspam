class Backend:
    """Class that should be inherited from for each backend used"""

    def createDBAndConnect(self):
        pass

    def insert(self, data):
        pass

    def insertSpam(self, data, into):
        pass

    def connect(self):
        pass

    def disconnect(self):
        pass

    def delete(self, data):
        pass

    def query(self, qu):
        pass

    def get(self, data):
        pass

    def queryVal(self, qu, val):
        pass

    def buildValueStr(self, dat):
        pass

    def killSpamassEmails(self):
        pass

    def getListSingleVal(self):
        pass

    def getFeatureList(self):
        """Returns a list of all distinct features"""
        pass

    def saveOrderToFile(self):
        """Save order of features to file. Desc"""
        pass

    def getMailList(self):
        """
        Returns a list of all distinct Mail IDs found
        in the feature table
        """
        pass

    def getValueList(self, feature):
        """
        Returns a list of all distinct values for a given
        feature
        """
        pass

    def getMailFeatureList(self, dbid):
        """
        Returns a list of distinct features for one given mail ID
        """
        pass

    def getMailValueList(self, dbid, feature):
        """
        Returns a list of all feature values for a given mail ID
        and feature name
        """
        pass

    def getEval(self, dbid):
        pass

    def getDescValueCountList(self, value):
        pass

    def getIDMails(self):
        pass

    def identifyDelFeatures(self, cutoff=0.4):
        pass
