from sqlitebackend import SQLiteBackend
from standardmappingfilter import StandardMappingFilter
from order import Order
from mapping import Mapping
import numpy as np

class FeatureEncoder:
    """
    Creates an order and all mappings for given data.
    Can be called to map an email to its ML feature vector
    """
    def __init__(self, db, ignorepath=None, filtr=False, cutTime=None, table=None, delFeatures=[], explval=10):
        """
        Create all necessary variables, objects
        :param db: backend object to be used
        :param ignorepath: path to file containing names of features to be disregarded in encoding, instead pass through values unencoded
        :param filtr: Use filter for mapping objects?
        :param cutTime: time at which to start using emails for classification
        :param table: name of specific table with mail ids for feature encoding, disregard rest of emails if given
        :param delFeatures: features possibly dynamically determined to be disregarded for encoding
        :param explval: number of explicit values to keep per feature for classification
        """
        self.db = db
        self.explval = explval
        self.filtr = filtr
        #Get features used for featureencoding
        self.features = self.db.getFeatureList(cutTime=cutTime, table=table)
        #Prepare list of features to be disregarded for further processing (in case wildcard "*" is given)
        delstart = []
        for feat in delFeatures:
            if feat.endswith('*'):
                delstart.append(feat[:-1])
            if feat in self.features:
                self.features.remove(feat)
        if len(delstart) > 0:
            for feat in self.features[:]:
                if any(feat.startswith(delany) for delany in delstart):
                    self.features.remove(feat)

        self.ordr = self.getOrder()
        #Prepare list of features to be passed through from given ignorefile
        self.ignore = []
        if not(ignorepath == None):
            try:
                f = open(ignorepath)
                self.ign = f.read().split("\n")
                self.ign.remove('')
                self.ignoreAny = []
                self.ignore = []
                self.ignoreBegEnd = []
                for item in self.ign:
                    if item.endswith("*"):
                        self.ignoreAny.append(item[:-1])
                    elif "*" in item and not(item.endswith("*")):
                        self.ignoreBegEnd.append(item.split("*"))
                    else:
                        self.ignore.append(item)
            except:
                print("Error opening ignore file!")
        #Create mappings for features
        self.mappings = self.getMappings()
        #Set overall length of feature vector
        self.vectorLen = self.cutPts[-1]

    def getOrder(self):
        """
        Returns or creates and returns the used order (Singleton)
        """
        if hasattr(self, 'ordr'):
            return self.ordr
        return Order(self.features)


    def startsEndsWith(self, strng, start, end):
        """
        Tests if a string starts and ends with given substrings
        :param strng: string to be tested
        :param start: prefix
        :param end: suffix
        :return: boolean
        """
        result = False
        if strng.startswith(start):
            if strng.endswith(end):
                result = True
        #print(strng + "; " + start + "; " + end + "; " + str(result))
        return result

    def getMappings(self):
        """
        Create and return mappings for all found features (Singleton)
        """
        if hasattr(self, 'mappings'):
            return self.mappings

        mappings = []
        #Lengths of mappings as indices of the overall vector length
        self.cutPts = [0]
        self.mapNames = []
        for idx, feat in enumerate(self.features):
            if not(self.isIgnoreFeat(feat)):
                if self.filtr:
                    filtrData = self.db.getDescValueCountList(str(feat))
                    #Use filter, if given
                    mappings.append(Mapping(str(feat), None, filtr=StandardMappingFilter(filtrData, numExplicit=self.explval)))
                else:
                    values = self.db.getValueList(feat)
                    mappings.append(Mapping(str(feat), values))
            else:
                #Passthrough feature, do not one-hot encode
                mappings.append(Mapping(str(feat), [], passThr=True))
            self.cutPts.append(self.cutPts[idx] + mappings[idx].length)
            self.mapNames.extend([str(feat) for i in range(self.cutPts[idx+1] - self.cutPts[idx])])
        return mappings

    def isIgnoreFeat(self, feat):
        result = False
        if feat in self.ignore:
            result = True
        elif any(self.startsEndsWith(feat, igany[0], igany[1]) for igany in self.ignoreBegEnd):
            result = True
        elif any(feat.startswith(igany) for igany in self.ignoreAny):
            result = True
        return result

    def mapMail(self, mid):
        """
        Map a mail to its machine learning feature vector and return it
        """
        result = np.array([0 for x in range(self.vectorLen)])
        mFeatures = self.db.getMailFeatureList(mid)
        for feat in mFeatures:
            if feat in self.ordr:
                idx = self.ordr[feat]
                vals = self.db.getMailValueList(mid, feat)
                #print(feat)
                result[self.cutPts[idx]:self.cutPts[idx+1]] = self.mappings[idx].getFeatureVec(vals)
                #print("\n")
        return result

    def toFile(self):
        """
        Write feature-value order to file
        """
        f = open("currentFeat.ind", "w")
        for mapp in self.mappings:
            vals = {y:x for x,y in mapp.mapp.iteritems()}
            for idx in range(len(vals)):
                f.write(str(mapp.name) + ": " + str(vals[idx].replace('\n','')) + "\n")
            if len(vals) == 0:
                f.write(str(mapp.name) + "\n")
        f.close()
