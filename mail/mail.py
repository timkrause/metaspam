import email
import socket
import string
import os
import hashlib
import datetime
import dateutil
import langdetect
import chardet
import base64
import re
import geoip2.database
import magic
import quopri
import zipfile
from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from time import time
from StringIO import StringIO
from wand.image import Image
from dateutil.parser import parse
from email.header import decode_header
from email.utils import parseaddr



class Mail:
    """
    Class which represents a mail object. Capsulates python email
    objects.
    Contains all methods available to calculate engineered
    features
    """
    def __init__(self, mail, geodb=None, atlim=10, ignorelist="ignorelist", archive=False, arcDate=None, size=0): #Change ignorelist default
        """
        Initialize a mail object. Pass geodb object and list of
        features to ignore in auto feature creation to it.
        atlim parameter controls the amount of attachments to
        take into account.
        """
        self.mail = mail
        self.features = []
        self.dbID = self.dbID()
        self.attachLimit = atlim
        self.archive = archive
        self.arcDate = arcDate
        self.size = size
        print(self.size)
        if geodb == None:
            self.geoDB = geoip2.database.Reader("GeoLite2-Country.mmdb")
        else:
            self.geoDB = geodb

        if ignorelist == None:
            self.ignore = []
        else:
            f = open(ignorelist)
            self.ignore = f.read().split("\n")

    def extractFeatures(self):
        """
        Controls which features are supposed to be created
        """
        self.features = [] #Not a good idea
        self.features.append(self.subEx())
        self.features.append(self.subLen())
        self.features.append(self.subLang())
        self.features.append(self.subCod())
        self.features.append(self.subPunct())

        self.features.append(self.recCnt())
        self.features.extend(self.recParts())
        self.features.append(self.recGeoVec())
        self.features.append(self.recTimeDelta())
        self.features.extend(self.recWith())
        self.features.extend(self.recTZs())

        self.features.append(self.dateBucket())
        self.features.append(self.dateTZ())
        self.features.append(self.dateRecDelta())

        self.features.append(self.fromEx())
        self.features.append(self.fromLen())
        self.features.append(self.fromExAlias())
        self.features.append(self.fromDomain())
        self.features.append(self.fromDomainFQN())
        self.features.append(self.fromErrorsToDom())
        self.features.append(self.fromReplyToDom())
        #self.features.append(self.fromExDomain())

        self.features.append(self.toCnt())
        self.features.append(self.toDomain())
        self.features.append(self.toMsgidDom())
        #self.features.append(self.toExDomain())
        self.features.append(self.toFromDom())
        self.features.append(self.msgidDomain())
        self.features.append(self.msgidFromDom())

        self.features.append(self.attachCnt())
        self.features.extend(self.extractAttFeatures())

        self.features.extend(self.cType())
        self.features.extend(self.cTypeActual())

        self.features.append(self.partCnt())
        self.features.extend(self.partFeatures())
        self.features.append(self.partStruct())

        self.features.append(self.bodyLang())
        self.features.append(self.bodyLength())

        self.features.extend(self.xMailerTokens())

        self.features.extend(self.multipleFeatures())
        self.features.extend(self.genFeatures())

        self.features.append(self.replyToErrorsToDom())
        return self.features


    def idFeatures(self):
        """
        Returns all features necessary for identification of a mail
        """
        idf = (self.msgid(), self.date(), self.serverDate(), self.fromH(), self.to(), self.subject(), self.dbID, self.smtpFrom(), self.smtpTo(), self.size, 0)
        return idf


#HELPERS

    def recievedIPs(self):
        """
        Parse all IPs from all Received headers
        """
        recv = self.mail.get_all("Received")
        result = []
        if recv != None:
            recv = list(reversed(recv))
            recv = ''.join(recv)
            regex = r'[0-9]+(?:\.[0-9]+){3}'
            result = re.findall(regex, recv)
        return result

    def parseRecDate(self, rec):
        result = None
        splitRec = rec.split(";")
        if len(splitRec) > 1:
            try:
                result = parse(splitRec[1])
            except:
                return None
        return result

    def getAttachments(self):
        """
        Find all attachments and some complimentary information
        """
        if hasattr(self, 'attachmts'):
            return self.attachmts

        self.attPayload = []
        self.attName = []
        self.attType = []
        self.isInline = []
        self.encoding = []
        flag = 0
        for part in self.mail.walk():
            maintype = part.get_content_maintype()
            if maintype == "image":
                if part.get_content_subtype() != "":
                    self.attType.append(part.get_content_subtype().lower())
                    if part.get_filename() != None:
                        self.attName.append(part.get_filename())
                    else:
                        self.attName.append("none." + str(part.get_content_subtype()))
                    self.attPayload.append(part.get_payload())
                    flag = 1
            if maintype == "application":
                if part.get_filename() != None:
                    fn = part.get_filename()
                    self.attName.append(fn)
                    self.attType.append(fn.split(".")[-1])
                    self.attPayload.append(part.get_payload())
                    flag = 1
            if flag and "Content-Disposition" in part:
                disp = part['Content-Disposition'].split(";")[0]
                if disp == "inline":
                    self.isInline.append(1)
                else:
                    self.isInline.append(0)
            if flag and not("Content-Disposition" in part):
                self.isInline.append(0)
            if flag:
                if "Content-Transfer-Encoding" in part:
                    self.encoding.append(part["Content-Transfer-Encoding"].lower())
                else:
                    self.encoding.append("None")
            flag = 0

        self.attchmts = [(self.attName[i], self.attType[i], self.attPayload[i], self.isInline[i], self.encoding[i]) for i in range(len(self.attName))]
#        print(sorted(self.attchmts, key=lambda x: -len(x[2])))
        self.attchmts = sorted(self.attchmts, key=lambda x: -len(x[2]))
        return self.attchmts



    def calcCommon(self, dom1, dom2):
        return int(SequenceMatcher(None, dom1, dom2).ratio()*100)

    def getErrorsToDom(self):
        result = "None"
        if "Errors-To" in self.mail:
            result = self.parseDom(self.mail["Errors-To"])
        return result

    def getReplyToDom(self):
        result = "None"
        if "Reply-To" in self.mail:
            result = self.parseDom(self.mail["Reply-To"])
        return result

    def parseDom(self, content):
        result = "None"
        helper = content.split("@")
        if len(helper) > 1:
            result = helper[1].strip("<>")
        return result

    def getRecWithTokens(self, rec):
        result = []
        delimiters = ["by", "id", ";", "via", "for", "with", "\r\n\t"]
        if "with" in rec:
            splitRec = rec.split(" ")
            try:
                indeces = [i for i, x in enumerate(splitRec) if x == "with"]
            except Exception as e:
                print(e)
                return []
            for idx in indeces:
                for i in range(idx+1, len(splitRec)):
                    if any(item in splitRec[i] for item in delimiters):
                        break
                    else:
                        result.append(splitRec[i].strip().strip("()"))
        return result


    def decodeTextBody(self, part):
        if "Content-Transfer-Encoding" in part:
            cte = part["Content-Transfer-Encoding"].lower()
            if cte == "quoted-printable":
                body = quopri.decodestring(part.get_payload())
            elif cte == "base64":
                body = base64.b64decode(part.get_payload())
            else:
                body = part.get_payload()
        else:
                body = part.get_payload()
        return body


    def decodeAtt(self, att):
        cte = att[4]
        result = ""
        if cte == "base64":
            try:
                result = base64.b64decode(att[2])
            except:
                print("Attachement decode Error")
        elif cte == "quoted-printable":
            try:
                result = quopri.decodestring(att[2])
            except:
                print("Attachement decode Error")
        else:
            result = att[4]
        return result





#ID FEATURES

    #Normalized
    def date(self):
        if 'Date' in self.mail:
            try:
                date = parse(self.mail['Date'])
                epoch = datetime.datetime.utcfromtimestamp(0)
                epoch = epoch.replace(tzinfo=dateutil.tz.tzoffset(None, 0))
                return int((date - epoch).total_seconds())
            except:
                #print("Datetime format not supported")
                return "None"
        else:
            return "None"

    def serverDate(self):
        if self.archive:
            return str(parse(self.arcDate))
        return str(datetime.datetime.now())

    def msgid(self):
        if 'Message-ID' in self.mail:
            return self.mail['Message-ID'].strip('<>')
        else:
            return "None"

    def fromH(self):
        if 'From' in self.mail:
            result = self.mail['From']
            return result
        else:
            return "None"

    def to(self):
        if 'To' in self.mail:
            return self.mail['To']
        else:
            return "None"

    def subject(self):
        if 'Subject' in self.mail:
            result = self.mail['Subject']
            return result
        else:
            return ""

    def spamEval(self):
        pass

    def dbID(self):
        rand = os.urandom(10) #?
        m = hashlib.md5()
        mdstr = self.fromH() + self.to() + rand
        m.update(mdstr)
        return m.hexdigest()

    def smtpFrom(self):
        result = "None"
        if 'X-P-MX-SMTP-From' in self.mail:
            result = self.mail['X-P-MX-SMTP-From']
        return result

    def smtpTo(self):
        result = "None"
        if "X-P-MX-SMTP-To" in self.mail:
            result = self.mail['X-P-MX-SMTP-To']
        return result


#SUBJECT FEATURES

    def subEx(self):
        result = 0 if self.subject() == "" else 1
        return (self.dbID, 'subex', result)

    def subLen(self):
        return (self.dbID, 'sublen', len(self.subject()))

    def subLang(self):
        result = "None"
        sub = self.subject()
        if sub != "":
            try:
                langs = []
                for i in range(5):
                    langs.append(str(langdetect.detect(sub.decode('utf-8'))))
                result = max(set(langs), key=langs.count)
            except:
                result = "None"
        return (self.dbID, 'sublang', result)

    def subCod(self):
        return (self.dbID, 'subcod', chardet.detect(str(self.subject()))['encoding'])

    def subPunct(self):
        result = 0
        if any(char in string.punctuation for char in self.subject()):
            result = sum(p in list(string.punctuation) for p in self.subject())
        return (self.dbID, 'subpunct', result)


#RECEIVED FEATURES
    def recCnt(self):
        result = self.mail.get_all('Received')
        if result != None:
            return (self.dbID, 'reccnt', len(result))
        else:
            return (self.dbID, 'reccnt', 0)


    def recParts(self):
        #This needs to be changed or at least examined
        (fromv, byv, viav, idv, forv, tlsv) = (0,0,0,0,0,0)
        result = []
        if "Received" in self.mail:
            i = 0
            for recv in self.mail.get_all("Received"):
                fromv = 1 if "from" in recv else 0
                byv = 1 if "by" in recv else 0
                viav = 1 if "via" in recv else 0
                idv = 1 if "id" in recv else 0
                forv = 1 if "for" in recv else 0
                tlsv = 1 if "TLS" in recv else 0
                result.extend([(self.dbID, 'rec_' + str(i) + '_from', fromv),
                               (self.dbID, 'rec_' + str(i) + '_by', byv),
                               (self.dbID, 'rec_' + str(i) + '_via', viav),
                               (self.dbID, 'rec_' + str(i) + '_id', idv),
                               (self.dbID, 'rec_' + str(i) + '_for', forv),
                               (self.dbID, 'rec_' + str(i) + '_tls', tlsv)])
                i += 1
        return result

    def recGeoVec(self):
        ips = self.recievedIPs()
        result = ""
        if len(ips) > 0:
            for ip in ips:
                ipparts = ip.split(".")
                if (ipparts[0] == '10') or \
                   (ipparts[0] == '172' and \
                    16 <= int(ipparts[1]) <= 31) or \
                   (ipparts[0] == '192' and \
                    ipparts[1] == '168'):
                    if not(result.endswith("PRIV")):
                        result += "PRIV_"
                else:
                    try:
                        isocd = str(self.geoDB.country(ip).country.iso_code) + "_"
                        if not(result.endswith(isocd)):
                            result += isocd
                    except:
                        pass
        result = result.strip("_")
        return (self.dbID, 'geovec', result)

    def recTimeDelta(self):
        result = -1
        if "Received" in self.mail:
            recs = self.mail.get_all("Received")
            if len(recs) > 1:
                recNew = self.parseRecDate(recs[0])
                recOld = self.parseRecDate(recs[-1])
                if recNew != None and recOld != None:
                    try:
                        result = (recNew - recOld).total_seconds()
                    except:
                        result = 1
                        #print("Error calculating Received Date delta.")
        return (self.dbID, 'recdatedelta', result)


    def recWith(self):
        result = []
        if "Received" in self.mail:
            recs = self.mail.get_all("Received")
            for rec in recs:
                tokens = self.getRecWithTokens(rec)
                for token in tokens:
                    result.append((self.dbID, 'recwithtoken', token))
        return result

    def recTZs(self):
        result = []
        if "Received" in self.mail:
            recs = self.mail.get_all("Received")
            i = 0
            for rec in recs:
                try:
                    date = self.parseRecDate(rec)
                    result.append((self.dbID, "rec_" + str(i) + "_tz", str(date.utcoffset())))
                except:
                    #print("Error parsing Received TZ.")
                    result.append((self.dbID, "rec_" + str(i) + "_tz", "perror"))
                i += 1
        return result





#DATE FEATURES

    def dateBucket(self):
        date = self.date()
        result = -10000000 #Default value if no date header exists
        if date != "None":
            try:
                if self.arcDate is None:
                    now = int(time())
                    result = now - date
                else:
                    if "Date" in self.mail:
                        dt = self.mail["Date"]
                        try:
                            serverdate = parse(self.arcDate)
                            date = parse(dt)
                            result = int((serverdate - date).total_seconds())
                        except TypeError:
                            serverdate = parse(self.arcDate + " +0100")
                            date = parse(dt)
                            result = int((serverdate - date).total_seconds())
            except Exception as e:
                print(e)
        return (self.dbID, 'datebucket', result)

    def dateTZ(self):
        result = "None"
        if 'Date' in self.mail:
            date = self.mail['Date']
            try:#parse time zone from date header
                result = re.search('(\+|\-)[0-9]{4}', date).group(0)
            except AttributeError:
                result = "None"
        return (self.dbID, 'tz', result)

    def dateRecDelta(self):
        result = -1
        if "Date" in self.mail:
            try:
                date = self.mail["Date"]
                date = parse(date)
            except:
                return (self.dbID, 'daterecdelta', 0)
            if "Received" in self.mail:
                try:
                    recDate = self.parseRecDate(self.mail["Received"])
                    if recDate != None:
                        result = (recDate - date).total_seconds()
                except:
                    result = -1
        return (self.dbID, 'daterecdelta', result)


#FROM FEATURES

    def fromEx(self):
        result = 0 if self.fromH == "None" else 1
        return (self.dbID, 'fromex', result)

    def fromLen(self):
        fromv = self.fromH()
        result = 0 if fromv == "None" else len(fromv)
        return (self.dbID, "fromlen", result)

    def fromExAlias(self):
        fromv = self.fromH()
        result = 0
        if fromv != "None" and parseaddr(fromv)[0] != "":
            result = 1
        return (self.dbID, "fromexalias", result)

    def fromDomainFQN(self):
        fromv = self.fromH()
        result = "None"
        if fromv != "None":
            addr = parseaddr(fromv)[1]
            if addr != "":
                dom = addr.split("@")
                if len(dom) > 1:
                    result = dom[1]
        return (self.dbID, 'fromdomainfqn', result)

    def fromDomain(self):
        result = "None"
        fqn = self.fromDomainFQN()[2]
        if fqn != "None":
            result = fqn.split(".")
            if len(result) > 2:
                result = '.'.join(result[-2:])
                result = result.lower()
            else:
                result = fqn.lower()
        return (self.dbID, 'fromdomain', result)


    def fromExDomain(self): #Takes VERY long
        dom = self.fromDomain()[2]
        result = 0
        if dom != "None":
            try:
                socket.gethostbyname(dom)
                result = 1
            except socket.gaierror:
                return (self.dbID, 'fromexdomain', 0)
        return (self.dbID, 'fromexdomain', result)

    def fromErrorsToDom(self):
        result = -1
        dom = self.fromDomain()[2]
        erto = self.getErrorsToDom()
        if dom != "None" and erto != "None":
            result = self.calcCommon(dom, erto)
        return (self.dbID, 'fromerrorstodom', result)

    def fromReplyToDom(self):
        result = -1
        dom = self.fromDomain()[2]
        rplyto = self.getReplyToDom()
        if dom != "None" and rplyto != "None":
            result = self.calcCommon(dom, rplyto)
        return (self.dbID, 'fromreplytodom', result)




#TO FEATURES

    def toCnt(self):
        #Not perfect
        result = 0
        tov = self.to()
        if tov != 0:
            tos = tov.split(",")
            result = len(tos)
            if result > 1:
                for to in tos:
                    if to.count('"') % 2 == 1:
                        result -= 1
        return (self.dbID, 'tocnt', result)

    def toDomain(self):
        tov = self.to()
        result = "None"
        if tov != "None":
            addr = parseaddr(tov)[1]
            if addr != "":
                dom = addr.split("@")
                if len(dom) > 1:
                    result = dom[1].lower()
        return (self.dbID, 'todomain', result)

    def toExDomain(self): #Takes VERY long
        #Only takes first into account
        dom = self.toDomain()[2]
        result = 0
        if dom != "None":
            try:
                socket.gethostbyname(dom)
                result = 1
            except socket.gaierror:
                return (self.dbID, 'toexdomain', 0)
        return(self.dbID, 'toexdomain', result)

    def toFromDom(self):
        result = 0
        fromdom = self.fromDomainFQN()[2]
        todom = self.toDomain()[2]
        if fromdom != "None" and todom != "None":
                result = self.calcCommon(fromdom, todom)
        return (self.dbID, 'tofromdom', result)

    def toMsgidDom(self):
        result = -1
        todom = self.toDomain()[2]
        msgid = self.msgidDomain()[2]
        if todom != "None" and msgid != "None":
            result = self.calcCommon(todom, msgid)
        return (self.dbID, 'tomsgiddom', result)

#MSGID FEATURES

    def msgidDomain(self):
        msgid = self.msgid()
        result = "None"
        if msgid != "None":
            data = msgid.split("@")
            if len(data) > 1:
                result = data[1].lower()
        return (self.dbID, 'msgiddomain', result)

    def msgidFromDom(self):
        result = -1
        msgid = self.msgidDomain()[2]
        fromv = self.fromDomainFQN()[2]
        if msgid != "None" and fromv != "None":
            result = self.calcCommon(msgid, fromv)
        return (self.dbID, 'msgidfromdom', result)

#ATTACHMENT FEATURES

    def extractAttFeatures(self):
        atts = self.getAttachments()
        result = []
        counters = {}
        for att in atts:
            try:
                mtype = self.attachMagicType(att)
                if mtype != "":
                    ftype = mtype.split(";")[0].split("/")[1]
                    if ftype in counters:
                        counters[ftype] += 1
                    else:
                        counters[ftype] = 1
                    fname = "attach" + "_" + ftype + str(counters[ftype])
                    if len(mtype.split(";")) > 1:
                        result.append((self.dbID, fname + "_mm_enc", mtype.split(";")[1]))

                    result.append((self.dbID, fname + "_name", str(att[0])))
                    result.append((self.dbID, fname + "_email_t", str(att[1])))
                    result.append((self.dbID, fname + "_inline", att[3]))
                    result.append((self.dbID, fname + "_enc", str(att[4])))
                    result.append((self.dbID, fname + "_len", len(att[2])))
                    if mtype.startswith("image"):
                        try:
                            result.append((self.dbID, fname + "_pix", self.imageSize(att)))
                            result.append((self.dbID, fname + "_depth", self.imageDepth(att)))
                        except:
                            print("Error in image analysis")

                    if ("zip" in att[0]) or ("zip" in att[1]) or ("zip" in mtype):
                        try:
                            sio = StringIO(self.decodeAtt(att))
                            with zipfile.ZipFile(sio, 'r') as zf:
                                st = set()
                                for item in zf.namelist():
                                    itemsp = item.split(".")
                                    if len(itemsp) > 1:
                                        st.add(itemsp[-1])
                                    else:
                                        st.add("notype")
                                for idx, item in enumerate(st):
                                    if idx > 9:
                                        break
                                    result.append((self.dbID, fname + "_zipf_" + str(idx), str(item)))
                        except Exception as e:
                            print(e)
                            print("Error in handling zipfile")
            except:
                print("Attachment Error")
        return result


    def attachCnt(self):
        att = self.getAttachments()
        return (self.dbID, 'attachcnt', len(att))

    def imageSize(self, att):
        imgtypes = ['jpg', 'png', 'gif', 'eps', 'jpeg', 'tiff']
        result = ""
        if att[1] in imgtypes:
            try:
                img = self.decodeAtt(att)
            except:
                print("Image decode error")
                image = None
            try:
                image = Image(blob=img)
            except:
                print("Image Error")
            if image != None:
                size = image.width * image.height
                result = str(size)
                image.close()
        return result

    def imageDepth(self, att):
        imgtypes = ['jpg', 'png', 'gif', 'eps', 'jpeg', 'tiff']
        result = ""
        if att[1] in imgtypes:
            try:
                img = self.decodeAtt(att)
            except:
                print("Image decode error")
                image = None
            try:
                image = Image(blob=img)
            except:
                print("Image Error")
            if image != None:
                result = str(image.depth)
                image.close()
        return result

    def attachMagicType(self, att):
        magt = magic.Magic(flags=magic.MAGIC_MIME_TYPE)
        mage = magic.Magic(flags=magic.MAGIC_MIME_ENCODING)
        result = ""
        try:
            blob = self.decodeAtt(att)
        except:
            print("Decode Error!")
            return result
        try:
            result = result + magt.id_buffer(blob) + ";" + mage.id_buffer(blob)
        except:
            print("Attachement decode Error")
        magt.close()
        mage.close()
        return result

#MAIN CONTENT-TYPE FEATURES

    def cType(self):
        result = []
        if "Content-Type" in self.mail:
            try:
                ctype = self.mail["Content-Type"].split(";")
                for part in ctype:
                    if "=" in part:
                        spPart = part.split("=")
                        if len(spPart) > 1:
                            name = spPart[0].strip()
                            if name != "boundary" and not("id" in name):
                                val = spPart[1].strip().strip("'").strip('"')
                                result.append((self.dbID, 'root_Content-Type_' + str(name), val))
                    else:
                        result.append((self.dbID, 'root_Content-Type', part.strip()))
            except:
                print("Error extracting root ctype")

        return result

    def cTypeActual(self):
        result = []
        if "Content-Type" in self.mail:
            if "text/" in self.mail["Content-Type"]:
                try:
                    body = self.decodeTextBody(self.mail)
                    res = "html" if bool(BeautifulSoup(body, "html.parser").find()) else "plain"
                    result.append((self.dbID, 'root_Content-Type_actual', res))
                except:
                    pass
        return result



#PART FEATURES

    def partCnt(self):
        return (self.dbID, 'partcnt', len(list(self.mail.walk())))

    def partCTypeActual(self):
        result = []
        parts = list(self.mail.walk())[1:]
        i = 0
        for part in parts:
            if "Content-Type" in part:
                ctype = part["Content-Type"].split(";")[0]
                try:
                    if "text/" in ctype:
                        body = self.decodeTextBody(part)
                        res = "html" if bool(BeautifulSoup(body, "html.parser").find()) else "plain"
                        result.append((self.dbID, 'part' + str(i) + '_Content-Type_actual', res))
                except Exception as e:
                    pass
            i += 1
        return result

    def partFeatures(self):
        result = []
        parts = list(self.mail.walk())[1:]
        for idx, part in enumerate(parts):
            result.extend(self.extractPartFeatures(part, idx))
        result.extend(self.partCTypeActual())
        return result

    def extractPartFeatures(self, part, num):
        result = []
        for key in part.keys():
            if "ID" in key or "Id" in key:
                continue
            for feat in part.get_all(key):
                vals = feat.split(";")
                for val in vals:
                    v = val.split("=")
                    if len(v) == 1:
                        result.append((self.dbID, "part" + str(num) + "_" + str(key), v[0]))
                    else:
                        if not("boundary" in v[0]) and not("-date" in v[0]):
                            result.append((self.dbID, "part" + str(num) + "_" + str(key) + "_" + str(v[0]).strip(), v[1].strip("'").strip('"')))
        return result


    def partStruct(self):
        result = self.partStructRec(self.mail, "", "1", 1)
        return (self.dbID, 'partstruct', result)

    def partStructRec(self, part, result, depth, cnt):
        if not(part.is_multipart()):
            result = result + str(depth) + "." + str(cnt) + ";"
            return result
        else:
            result = result + str(depth) + "." + str(cnt) + ";"
            ndepth = str(depth) + "." + str(cnt)
            for i, prt in enumerate(part.get_payload()):
                result = result + self.partStructRec(prt, "", ndepth, i+1)
            return result




#BODY FEATURES

    def bodyLang(self):
        result = "None"
        for part in self.mail.walk():
            if "Content-Type" in part:
                if part["Content-Type"].startswith("text"):
                    try:
                        langs = []
                        for i in range(5):
                            langs.append(str(langdetect.detect(part.get_payload().decode('utf-8'))))
                        result = max(set(langs), key=langs.count)
                        break
                    except:
                        result = "None"
                        break
        return (self.dbID, 'bodylang', result)

    def bodyLength(self):
        result = 0
        for part in self.mail.walk():
            if "Content-Type" in part:
                if part["Content-Type"].startswith("text"):
                    result += len(part.get_payload())
        return (self.dbID, 'bodylen', result)

#X-MAILER FEATURES

    def xMailerTokens(self):
        result = []
        if "X-Mailer" in self.mail:
            tokens = self.mail["X-Mailer"].split(" ")
            for token in tokens:
                result.append((self.dbID, 'xmailertoken', token))
        return result

#USER-AGENT FEATURES

    def userAgentTokens(self):
        result = []
        if "User-Agent" in self.mail:
            tokens = self.mail["User-Agent"].split(" ")
            for token in tokens:
                result.append((self.dbID, 'useragenttoken', token))
        return result

#AUTOGEN FEATURES

    def multipleFeatures(self):
        """
        Finds all headers which appear more than once in the mail
        """
        result = []
        for key in list(set(self.mail.keys())):
            if len(self.mail.get_all(key)) > 1:
                result.append((self.dbID, 'multifeature', key))
        return result

    def genFeatures(self):
        """
        Returns all header and value pairs for which the header
        is not on the ignore list
        """
        result = []
        for key in list(set(self.mail.keys())):
            if not(key in self.ignore):
                for k in self.mail.get_all(key):
                    result.append((self.dbID, key, k))
        return result

#MISCELLANEOUS FEATURES

    def replyToErrorsToDom(self):
        result = -1
        replyto = self.getReplyToDom()
        errorsto = self.getErrorsToDom()
        if replyto != "None" and errorsto != "None":
            result = self.calcCommon(replyto, errorsto)
        return (self.dbID, 'replyerrordom', result)
