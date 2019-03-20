import email
import sys
import geoip2.database
from mail import Mail
from mailextractor import MailExtractor


class SingleExtractor(MailExtractor):
    """
    Can be used to extract a single email from a file
    """
    def __init__(self, data, geoipdb, ignore):
        self.f = open(data, "r")
        self.data = self.f.read()
        self.geoipdb = geoipdb
        self.ignore = ignore
        MailExtractor.__init__(self, data)

    def extract(self):
        self.base.append(Mail(email.message_from_string(self.data), ignorelist=self.ignore, geodb=self.geoipdb, size=sys.getsizeof(self.data)))
        self.f.close()
