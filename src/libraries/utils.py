import datetime
import yaml
from . import mailer, loggerdo
import math
import requests

def time_plus(time, timedelta):
    start = datetime.datetime(
        2000, 1, 1,
        hour=time.hour, minute=time.minute, second=time.second)
    end = start + timedelta
    return end.time()

def clean(input):
    char_set = set("!@#%&*()[]{}/?\"\n\r<>")
    for char in char_set:
        input = input.replace(char, "")
    input.replace(" ","")
    input = input.lower()
    input = stripspace(input)
    return input

def auth(subject, key):
    subject = clean(subject)
    if subject == key:
        return True
    else:
        return False

def stripnewline(input):
    return input.split('\n')[0]

def stripspace(input):
    return input.replace(' ','')

def loadconfig(configfile):
    with open(configfile, 'r') as file:
        config = yaml.load(file, Loader=yaml.FullLoader)
    return config

def truncate(n, decimals=0):
    multiplier = 10 ** decimals
    return int(n * multiplier) / multiplier

def min2dec(min):
    return truncate(min/60, 2)

def timefloor(now):
    if not isinstance(now,datetime.datetime):
        loggerdo.log.debug("non datetime sent to timefloor, sent a {}".format(now))
        now = datetime.datetime.today().replace(hour=now,minute=00,second=00,microsecond=0)

    mins = min2dec(now.minute)
    hours = now.hour
    time = mins + hours
    nearesthalf = round(time * 2) / 2
    if time < nearesthalf:
        return nearesthalf - 0.5
    else:
        return nearesthalf

def round_down(n, decimals=0):
    multiplier = 10 ** decimals
    return math.floor(n*multiplier) / multiplier


def checkmail(addr, user, password, key):
    message, subject, date, sender = mailer.ReEmail(addr, user, password)
    #check subject for key
    if subject != None:
        mailer.reply(sender,'processing request',message, user,password,addr)
        return clean(stripnewline(message)), clean(subject), date, sender, auth(clean(subject),key)
    else:
        return None, None, None, None, None

def bouncesensor(ip, port = 6969):
    url = 'http://{}:{}/reset'.format(ip, port)
    try:
        r = requests.get(url)
        if r.ok:
            return True
        else:
            loggerdo.log.debug("bouncesensor - error in making connection, {}".format(ip))
            loggerdo.log.warning(r)
            return False
    except requests.ConnectTimeout as e:
        loggerdo.log.warning("bouncesensor - Connection timed out, {}".format(ip))
        return False
    except requests.ConnectionError as e:
        loggerdo.log.warning("bouncesensor - Connection error, {}".format(ip))
        return False
    except requests.RequestException as e:
        loggerdo.log.warning("bouncesensor - There was an ambiguous exception that occurred, {}".format(ip))
        return False

if __name__ == "__main__":
    word = ' iNfo '
    print(clean(word))

