from email.mime.text import MIMEText
import smtplib, ssl
from . import utils
#import logging
from libraries import loggerdo
import poplib
from email.parser import Parser
from email.header import decode_header
from email.utils import formatdate

#most of this was scraped from the internet. I lost the URLs where they were sourced from, but I do not take credit for making this.


def reply(destination,subject,body,user,password,addr):
    #content = 'something in the body'
    #subject = 'something in the subject'
    # typical values for text_subtype are plain, html, xml

    text_subtype = 'plain'
    msg = MIMEText(body, text_subtype)
    msg['Subject'] = subject
    msg['From'] = user # some SMTP servers will do this automatically, not all
    msg["Date"] = formatdate(localtime = True)
    #context is required
    #context = ssl.create_default_context()

    try:
        mailer = smtplib.SMTP(host=addr)
    except TimeoutError:
        loggerdo.log.info(f"unable to connect to mail server {addr}.")
        return
    #mailer.starttls(context=context)
    mailer.set_debuglevel(False)
    #mailer.login(user, password)
    try:
        mailer.sendmail(user, destination, msg.as_string())
    except Exception as e:
        loggerdo.log.info("sending mail did not work, {}".format(e))
    finally:
        mailer.quit()
"""
def reply(destination,subject,body,user,password,addr):
    #content = 'something in the body'
    #subject = 'something in the subject'
    # typical values for text_subtype are plain, html, xml

    text_subtype = 'plain'
    msg = MIMEText(body, text_subtype)
    msg['Subject'] = subject
    msg['From'] = user # some SMTP servers will do this automatically, not all
    msg["Date"] = formatdate(localtime = True)
    #context is required
    context = ssl.create_default_context()

    mailer = smtplib.SMTP(host=addr,port=587)
    mailer.starttls(context=context)
    mailer.set_debuglevel(False)
    mailer.login(user, password)
    try:
        mailer.sendmail(user, destination, msg.as_string())
    except Exception as e:
        loggerdo.log.error("sending mail did not work, {}".format(e))
    finally:
        mailer.quit()
"""
def Get_info(msg):
    if (msg.is_multipart()):
        parts = msg.get_payload()
        for n, part in enumerate(parts):
            return Get_info(part)
    if not msg.is_multipart():
        content_type = msg.get_content_type()
        if content_type == 'text/plain':
            content = msg.get_payload(decode=True)
            charset = guess_charset(msg)
            if charset:
                content = content.decode(charset)
            return content

def guess_charset(msg):
    charset = msg.get_charset()
    if charset is None:
        content_type = msg.get('Content-Type', '').lower()
        pos = content_type.find('charset=')
        if pos >= 0:
            charset = content_type[pos + 8:].strip()
    return charset


def ReEmail(addr, user, password):
    try:
        pp = poplib.POP3_SSL(addr, '995')
        pp.user(user)
        pp.pass_(password)
        resp, mails, octets = pp.list()
        index = len(mails)
        if index > 0:
            resp, lines, octets = pp.retr(index)
            msg_content = b'\r\n'.join(lines).decode('utf-8')
            pp.dele(index)
            pp.quit()
            msg = Parser().parsestr(msg_content)
            message = Get_info(msg)
            subject = msg.get('Subject')
            date = msg.get('Date')
            sender = msg.get('Return-Path')
            sender = sender.replace(">","")
            sender = sender.replace("<","")
            return message, subject, date, sender
    except ConnectionResetError as e:
        loggerdo.log.error('ConnectionResetError')
    except Exception as e:
        loggerdo.log.error("unknow error, {}".format(e))
    return None, None, None, None


if __name__ =='__main__':
    addr = '10.10.105.31'
    user = 'burrow@dale.fail'
    password = 'something'
    key = 'something'

    print("hello world")
    sender= 'dale@mytuttle.com'
    message = 'do do do'

    reply(sender,'processing request',message, user,password,addr)
