#import argparse
import sys
import os
import geoip2.database
from MES.mail.singleextractor import SingleExtractor
from MES.mail.archiveextractor import ArchiveExtractor
from MES.featureextraction.sqlitebackend import SQLiteBackend
from MES.mail.mail import Mail

#parser = argparse.ArgumentParser(description="Meta Data Mail Extractor")

#Use proper argument handler in next version


f = open("../SPAMTrain.label", 'r')
labeldata = f.read()
labeldata = labeldata.split("\n")
labels = {}
for line in labeldata:
    if line != "":
        helper = line.split(" ")
        labels[helper[1]] = int(helper[0])

folder = sys.argv[1]
backend = SQLiteBackend("comspamSize.db")
geoipdb = geoip2.database.Reader("MES/files/GeoLite2-Country.mmdb")
ignore = "MES/files/ignorelist"

mids = []

for subdir, dirs, files in os.walk(folder):
    for file in files:
        #print os.path.join(subdir, file)
        filepath = subdir + os.sep + file
        data = SingleExtractor(filepath, geoipdb, ignore)
        data.extract()
        idfeats = data[0].idFeatures()
        mids.append(idfeats[6])
        if labels[str(file)] == 1:
            backend.insert(idfeats, 'mails')
        elif labels[str(file)] == 0:
            backend.insertSpam(idfeats, 'mails')
        else:
            print("Could not match " + str(file))
            continue
        backend.insert(data[0].extractFeatures(), 'features')

        print(filepath)

#backend.query("CREATE TABLE valmails ('id')")
#for mid in mids:
#    backend.query("INSERT INTO valmails VALUES ('" + str(mid) + "')")

backend.disconnect()
