import email
from email.parser import Parser
from email.header import decode_header
from email.utils import formatdate
import imaplib
from libraries import loggerdo, utils
import datetime, time



def guess_charset(msg):
    charset = msg.get_charset()
    if charset is None:
        content_type = msg.get('Content-Type', '').lower()
        pos = content_type.find('charset=')
        if pos >= 0:
            charset = content_type[pos + 8:].strip()
    return charset

def get_info(msg):
    if (msg.is_multipart()):
        parts = msg.get_payload()
        for n, part in enumerate(parts):
            return get_info(part)
    if not msg.is_multipart():
        content_type = msg.get_content_type()
        if content_type == 'text/plain':
            content = msg.get_payload(decode=True)
            charset = guess_charset(msg)
            if charset:
                content = content.decode(charset)
            return content

class connection():
    username = None
    password = None
    conn = None
    url = None
    createtime = None

    def __init__(self, username, password, address):
        self.username = username
        self.password = password
        self.url = address
        self.createtime = datetime.datetime.now()
        self.openconn()

    def openconn(self):
        loggerdo.log.info("Opening up connection to mail server")
        box = imaplib.IMAP4_SSL(self.url, 993)
        box.login(self.username, self.password)
        box.select('Inbox')
        loggerdo.log.info("saving connection")
        self.conn = box


    def keepalive(self):
        self.conn.noop()

    def reconnect(self):
        try:
            loggerdo.log.info("closing old mail connection, its was opened {}".format(self.createtime))
            self.close()
            self.openconn()
            self.createtime = datetime.datetime.now()

        except ConnectionRefusedError:
            loggerdo.log.debug('imapobjmailer - reconnect failed')

    def checkmail(self):
        # check to see if we need to reconnect
        if self.createtime + datetime.timedelta(hours=4) < datetime.datetime.now():
            self.reconnect()

        typ, data = self.conn.search(None, 'UnSeen')
        if typ != 'OK':
            loggerdo.log.debug("imapobjmailer -  Did not connect to server.")
            return None, None
        else:
            return data, len(data[0].split())

    def fetch(self, data):
        for num in data[0].split():
            rv, msg = self.conn.fetch(num, '(RFC822)')
            for response in msg:
                if isinstance(response, tuple):
                    email_parser = email.parser.BytesFeedParser()
                    email_parser.feed(response[1])
                    msg = email_parser.close()
                    subject = decode_header(msg["Subject"])[0][0]
                    sender = decode_header(msg["Return-Path"])[0][0]
                    sender = sender.replace(">","")
                    sender = sender.replace("<","")
                    message = get_info(msg)
                    date = decode_header(msg["Date"])[0][0]

                if rv != 'OK':
                    print (f"ERROR getting message {num}")
                    return "ERROR"
            #delete mail by updating the flag
            #box.store(num, '+FLAGS', '\\Deleted')
            return message, subject, date, sender

    def clear(self):
        self.conn.expunge()

    def close(self):
        self.clear()
        self.conn.close()
        self.conn.logout()



if __name__ == "__main__":
    addr = ""
    user = ""
    password = ""
    mailer = connection(user, password, addr)
    x = 0
    while x < 10:
        data, msgcount = mailer.checkmail()
        if msgcount > 0:
            print("You have mail")
            mailer.fetch(data)
        else:
            print("No mail")
        time.sleep(30)
        x +=1
    #mailer.fetch(data)
    mailer.close()

