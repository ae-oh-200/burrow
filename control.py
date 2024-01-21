from libraries import loggerdo, mailer, utils
import imapobjmailer as mappy
import datetime
from imaplib import IMAP4

class controller:
    update = False
    house = None
    scheduler = None
    burrow = None
    actoggle = None
    tempchangedirection = None
    tempchange = None
    key = None
    keyauth = None
    mailer = None

    def __init__(self,house,scheduler, burrow, config):
        self.house = house
        self.scheduler = scheduler
        self.burrow = burrow
        self.addr = config['addr']
        self.user = config['user']
        self.password = config['password']
        self.key = config['key']
        self.keyauth = config['keyauth']
        self.mailer = mappy.connection(config['user'], config['password'], config['addr'])


    #mailerpoll grabs the messages from the mailbox and sends them to be checked by actionparser
    def mailerpoll(self):
        try:
            self.mailer.keepalive()
        except IMAP4.abort:
            loggerdo.log.debug('control -imap conn failed, caaught')
            self.mailer.reconnect()
            return False
        except IMAP4.error:
            loggerdo.log.debug('control - general IMAP error')
            return False
        except TimeoutError:
            loggerdo.log.debug('control - Timeout error')
            return False
        else:

            data, msgcount = self.mailer.checkmail()
            if msgcount > 0:
                message, subject, date, sender = self.mailer.fetch(data)
                message = utils.clean(utils.stripnewline(message))
                subject = utils.clean(subject)
                auth = utils.auth(utils.clean(subject),self.key)
                aparse = self.actionparser(subject, message, sender, auth)
                if aparse == None:
                    return False
                else:
                    return True
            else:
                return False

    #called from goburrow to reset "flags" back to none
    def updateoff(self):
        self.update = False
        self.actoggle = None
        self.tempchangedirection = None
        self.tempchange = None

    def getscheddump(self):
        schd = self.scheduler.dumpsched()
        x = 0
        msg = ''
        while x < (len(schd)/2):
            msg += "Hour {}, Mode {}\n".format(x, schd[x])
            x += 0.5
        return msg

    #Generates the long info message responsen from most obejcts
    def getinfo(self):
        loggerdo.log.info("getinfo starting")
        message = self.house.getallzonetext()
        message = message + "Average room temp = {}\n".format(self.house.checkavgroomtemp())
        message = message + "Weighted average room temp = {}\n".format(self.house.getweightroomavg())
        outsidetemp, outsidetemplimit = self.house.getoutside()
        schedbase, schedhigh, schedlow = self.scheduler.pullhourdetails(datetime.datetime.now())
        message = message + f"outside = {outsidetemp}\noutside limit = {outsidetemplimit}\n"
        message = message + "AC Status = {}\n".format(self.burrow.getwemostatus())

        message = message + "Anyone home? {}\n".format(self.house.checkanyonehome())
        message = message + "scheduler time is {}\n".format(utils.timefloor(datetime.datetime.now()))
        message = message + "current base,low,high {},{},{}\n".format(schedbase, schedlow, schedhigh)


        #Is Burrow enabled if not check for a timer
        burrowstate = self.burrow.getburrowstatus()

        message = message + "Is Burrow enabled? {}\n".format(burrowstate)

        if not burrowstate and isinstance(self.burrow.getburrowstatustimer(), datetime.datetime):
            message = message + "Burrow is enabled at {}\n".format(self.burrow.getburrowstatustimer())

        #is timer running
        message = message + "Disable timer running is - {} (True = off)\n".format(self.burrow.timercheck())
        message = message + "Running in mode - {}\n".format(self.scheduler.activemode)

        #get schedule last
        message = message + "\n\n"
        message = message + self.scheduler.pullpartsched(datetime.datetime.now())

        loggerdo.log.info("getinfo ending")
        return message


    #long stream of if statements to check emails
    def actionparser(self, subject, message, sender, auth):
        loggerdo.log.info("Subject - {}".format(subject))
        loggerdo.log.info("Message - {}".format(message))
        loggerdo.log.info("Auth - {}".format(auth))
        loggerdo.log.info("sender - {}".format(sender))

        if auth:
            #split email at =, if not present len will be 1
            command = message.split('=')
            loggerdo.log.info("command = {}".format(command))

            loggerdo.log.info("command lengh = {}".format(len(command)))
            #only thing we use =X is for disable
            if auth and len(command) == 2:
                if command[0] == 'disable':
                    loggerdo.log.info("disable triggered, with timer")
                    self.burrow.burrowstatus(False, int(command[1]))
                    mailer.reply(sender,'request complete', message, self.user, self.password, self.addr)
                    return ("Good")
                else:
                    mailer.reply(sender,'cannot complete request', message, self.user, self.password, self.addr)

            #for everything else
            elif auth and len(command) == 1:
                loggerdo.log.info("auth good, lengh 1 and an action")
                if command[0] == 'off':
                    loggerdo.log.info("off triggered")
                    self.update = True
                    self.actoggle = False
                    mailer.reply(sender,'request complete', message, self.user, self.password, self.addr)
                    return ("Good")
                elif command[0] == 'on':
                    loggerdo.log.info("on triggered")
                    self.update = True
                    self.actoggle = True
                    mailer.reply(sender,'request complete', message, self.user, self.password, self.addr)
                    return ("Good")
                elif command[0] == 'info':
                    loggerdo.log.info("info triggered")
                    repymessage = self.getinfo()
                    mailer.reply(sender,'request complete', repymessage, self.user, self.password, self.addr)
                    return ("Good")
                elif command[0] == 'up':
                    loggerdo.log.info("up triggered")
                    self.update = True
                    self.tempchangedirection = True
                    mailer.reply(sender,'request complete', message, self.user, self.password, self.addr)
                    return ("Good")
                elif command[0] == 'down':
                    loggerdo.log.info("up triggered")
                    self.update = True
                    self.tempchangedirection = False
                    mailer.reply(sender,'request complete', message, self.user, self.password, self.addr)
                    return ("Good")
                elif command[0] == 'disable':
                    loggerdo.log.info("disable triggered")
                    self.burrow.burrowstatus(False)
                    mailer.reply(sender,'request complete', message, self.user, self.password, self.addr)
                    return ("Good")
                elif command[0] == 'enable':
                    loggerdo.log.info("enable triggered")
                    self.burrow.burrowstatus(True)
                    mailer.reply(sender,'request complete', message, self.user, self.password, self.addr)
                    return ("Good")
                elif command[0] == 'dump':
                    loggerdo.log.info("dump schedule")
                    message = self.getscheddump()
                    mailer.reply(sender, 'request complete', message, self.user, self.password, self.addr)
                    return ("Good")
                else:
                    #not a command
                    loggerdo.log.info("enable triggered")
                    mailer.reply(sender,'Not a command.', message, self.user, self.password, self.addr)
                    return ("Good")
            else:
                if sender in self.keyauth:
                    mailer.reply(sender,'failed', message)
                return None


if __name__ =='__main__':

    #testing.
    print("hello world")
    cando ={
        'roomtemphigh',
        'roomtemplow',
        'outsidelimit',
        'nightstart',
        'nightend'
         }
    print(cando)
    newcando = " "
    newcando.join(cando)
    listToStr = ' \n'.join([str(elem) for elem in cando])
    print(listToStr)

