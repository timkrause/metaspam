#import argparse
import sys
import socket
import time
from ..featureextraction.singleextractor import SingleExtractor
from ..featureextraction.archiveextractor import ArchiveExtractor
from ..mail.mail import Mail

#Test script for sending emails to MESServer instance through a socket


#Use proper argument handler in next version







if sys.argv[1] == "-s":
    data = SingleExtractor(sys.argv[2])

if sys.argv[1] == "-arc":
    data = ArchiveExtractor(sys.argv[2])

data.extract()


for i in range(5000):
#    s = raw_input("Next?" )
#    time.sleep(.01)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("127.0.0.1", 8154))
#    if s == "":
    ms = "STREAM\n"
    for part in data[i].mail.walk():
        ms += part.as_string()
    sent = sock.send(ms)
    if sent == 0:
        raise RuntimeError("socket connection broken while trying to send")
    sock.close()
    #else:
        #sock.close()
        #break
