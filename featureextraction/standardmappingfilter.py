class StandardMappingFilter:
    """
    Can be passed to mapping instances for
    dimensionality reduction.

    StandardMappingFilter picks the n most frequent feature
    values for explicit mapping and maps all other values
    to the 'known' dimension. Values not seen in the
    training data are mapped to the 'unknown' dimension

    data needs to be a list of tuples (value, #occurences)
    sorted in a descending fashion by #occurences
    """
    def __init__(self, data, numExplicit=10):
        self.expl = numExplicit
        self.createFilteredMapping(data)

    def createFilteredMapping(self, data):
        """
        Creates filtered mapping according to the set
        number of explicit values
        """
        self.mapp = {}
        self.known = []
        length = self.expl if self.expl < len(data) else len(data)
        for i in range(length):
            self.mapp[str(data[i][0])] = i
        #Could the naming unknown/known be a problem?
        #collisions, vulnerability etc.
#        self.mapp[".unknownFeat"] = len(self.mapp)

        if len(data) > self.expl:
            self.mapp[".knownFeat"] = len(self.mapp)
            for i in range(self.expl, len(data)):
                self.known.append(data[i][0])
            if None in self.known:
                self.known.append('None')

    def getFilteredInd(self, featVal):
        """
        Returns the index of the given feature value
        according to the previously calculated filtered
        mapping
        """
        if featVal in self.mapp:
            return self.mapp[featVal]
        elif featVal in self.known:
            return self.mapp[".knownFeat"]
        else: # self.expl == 1:
            return self.mapp[".knownFeat"]
        #else:
        #    return None
        print("This should never be printed.")
        print(self.mapp)
        print(self.known)
        print(featVal)
        print(featVal == 'None')
