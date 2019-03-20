import email
import re
import sys
from mail import Mail
from mailextractor import MailExtractor
import geoip2.database

#Extracts Emails from archive file
class ArchiveExtractor(MailExtractor):
    """
    Class used to extract spam archives.
    Needs a GeoLite Database to function.
    """
    def __init__(self, data, geofile="..files/GeoLite2-Country.mmdb", ignore="..files/ignorelist"):
        self.arc = open(data, "r")
        MailExtractor.__init__(self, data)
        self.geofile = geofile
        self.ignore = ignore


    def extract(self):
        """Extracts mails from the archive and writes them
           in a list like-object which can than be iterated over"""

        geoipdb = geoip2.database.Reader(self.geofile)
        dat = self.arc.read()

        #Match delimiting From terms
        arr = re.split("\n\nFrom.*[0-9]{4}\n\n", dat)
        fromlines = [dat.split("\n")[0]]
        fromlines.extend([froml.strip() for froml in (re.findall("\n\nFrom.*[0-9]{4}\n\n", dat))])
        self.fromaddrs = [froml.split(" ")[1] for froml in fromlines]
        self.dates = [' '.join(froml.split(" ")[2:]) for froml in fromlines]

        self.arc.close()

        #Remove artifacts in first and last mail
        arr[0] = '\n'.join(x for x in arr[0].split('\n')[2:])
        arr[-1] = '\n'.join(x for x in arr[-1].split('\n')[:-2])
        self.base = [Mail(email.message_from_string(x), geodb=geoipdb, archive=True, arcDate=self.dates[idx], ignorelist=self.ignore, size=sys.getsizeof(x)) for idx, x in enumerate(arr)]
