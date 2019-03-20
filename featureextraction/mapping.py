class Mapping:
    """
    Represents a mapping of all values for one feature
    to an order of those values
    """
    def __init__(self, name, values, filtr=None, passThr=False):
        """
        :param name: Name of feature this object represents
        :param values: values of this feature in the db
        :param filtr: Whether to use mapping filter or not
        :param passThr: Is this feature a pass through feature? (i.e. on the ignore list)
        """
        self.name = name
        self.filtr = filtr
        self.mapp = {}
        self.passThr = passThr
        if not(self.passThr):
            if self.filtr == None:
                #Just order values in the order given
                for idx, item in enumerate(values):
                        self.mapp[str(item)] = idx
                #Add dimension for unknown values
                self.mapp[".unknownFeat"] = len(self.mapp)
                self.length = len(self.mapp)
            else:
                self.mapp = self.filtr.mapp
                self.length = len(self.mapp)
        if self.passThr:
            self.length = 1
#        print(self.name + "\n")
#        print(str(self.mapp) + "\n\n")


    def getFeatureVec(self, featVals):
        """
        Returns the feature vector created by passing featVals
        through the mapping
        """
        if not(self.passThr):
            result = [0 for i in range(self.length)]
            for item in featVals:
                if self.filtr == None:
                    if item in self.mapp:
                        result[self.mapp[item]] = 1
                    else: #Unknown value
                        #Is this a mistake now?
                        #result[-1] = 1
                        pass
                else:
                    ind = self.filtr.getFilteredInd(item)
                    if ind is not None:
                        result[ind] = 1
                    else:
                        pass
            return result
        else:
            if len(featVals) == 1:
                if featVals[0] == '':
                    return [-1]
                try:
                    return [int(featVals[0])]
                except:
                    return [int(float(featVals[0]))]
            else:

                print("Error: Feature value size > 1!")
