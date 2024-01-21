import datetime
import libraries
import logging
import logging as log
from logging import handlers
from libraries import loggerdo
from flask import Flask
from flask import request
from flask.logging import default_handler


#Stop getting each and every log message
logging.getLogger('werkzeug').disabled = True

house = None
scheduler = None
burrow = None


class statcache:
    forcestatus = None
    statcache = None
    statusupdate = None


    def __init__(self, burrow):
        self.statcache = None
        self.statusupdate = statusupdate = datetime.datetime.now() - datetime.timedelta(minutes=10)
        self.forcestatus = True
        self.burrow = burrow
        self.checkstatus()

    def boolcache(self, stat):
        if stat == "on":
            return True
        else:
            return False


    #Alot of functions call this during an app load, this should limit the amount of times we really pull status
    # Force is for when we change something to force and update
    def checkstatus(self, force = False):
        if self.burrow.mode == "ac":
            self.forcestatus = force
            if self.forcestatus == True or self.statusupdate == None:
                self.statcache = self.burrow.getwemostatus()
                self.forcestatus = False
                self.statusupdate = datetime.datetime.now()
                loggerdo.log.warning("Reset statcache to {}, because force".format(self.statcache))
            elif datetime.datetime.now() > self.statusupdate + datetime.timedelta(minutes=5):
                self.statcache = self.burrow.getwemostatus()
                self.statusupdate = datetime.datetime.now()
                loggerdo.log.warning("Reset statcache to {}, because time".format(self.statcache))
        #else:
            #loggerdo.log.info("Didnt poll status, using cache")

    def getstatus(self):
        self.checkstatus()
        loggerdo.log.info("last status cache update - {}".format(self.statusupdate))
        return self.boolcache(self.statcache)



#Updates the schedule object. Hardcoded to +3 hours
def updateschedule(scheduler,tempchangedirection):
    now = datetime.datetime.now()
    thishour = now.hour
    #print("thishour = {}".format(thishour))
    max = thishour + 3
    loggerdo.log.info("max is set to - {}".format(max))
    while thishour <= max:
        if thishour > 23.5:
            break
        if tempchangedirection:
            scheduler.increment(now)
            loggerdo.log.info("thishour - {}, up".format(thishour))
        else:
            scheduler.decrement(now)
            loggerdo.log.info("thishour - {}, down".format(thishour))
        now = now + datetime.timedelta(minutes=30)
        thishour += 0.5



#API MACHINE
def flaskrunner(house, scheduler, burrow):

    acstatuscache = statcache(burrow)
    loggerdo.log.info("statcache = {}".format(acstatuscache.checkstatus()))
    sysmode = burrow.getmode()

    #setup objects


    app = Flask(__name__)

    @app.route('/')
    def run():
        acstatuscache.checkstatus(force=True)
        return("NOTHING HERE")
        print("root hit")

    @app.route('/system')
    def getsystem():
        return str(sysmode)

    @app.route('/tempup')
    def up():
        acstatuscache.checkstatus(force=True)
        updateschedule(scheduler, True)
        loggerdo.log.info("Bump temp - web")
        return ('', 204)

    @app.route('/tempdown')
    def down():
        acstatuscache.checkstatus(force=True)
        updateschedule(scheduler, False)
        loggerdo.log.info("Drop temp - web")
        return ('', 204)

    @app.route('/zonetemp')
    def getzonetemps():
        zone = request.args.get('zone', default = 1, type = int)
        acstatuscache.checkstatus()
        return str(house.getzonetemp(zone))

    @app.route('/weighttemp')
    def getweighttemp():
        return str(house.getweightroomavg())

    @app.route('/systemtogg')
    def systemtogg():
        if sysmode == "ac":
            burrow.acwebtogg()
            return ('', 202)
        elif sysmode == "heat":
            if burrow.getheatstatus():
                burrow.heatoff()
                return ('', 202)
            else:
                burrow.heaton()
                return ('', 202)


    @app.route('/getmode')
    def mode():
        return str(scheduler.activemode)

    @app.route('/getbase')
    def getbase():
        base, schedhigh, schedlow = scheduler.pullhourdetails(datetime.datetime.now())
        return (str(base))

    @app.route('/outsidetemp')
    def getouside():
        return str(house.gettempoutside())

    @app.route('/systemstatus')
    def systemstatus():
        if sysmode == "ac":
            acstatuscache.checkstatus()
            return str(acstatuscache.getstatus())

        elif sysmode == "heat":
            return str(burrow.getheatstatus())

    @app.route('/gettimer')
    def gettimer():
        timerstatus = burrow.timercheck()
        if timerstatus:
            return str(False)
        else:
            return str(True)


    @app.route('/burrowstatus')
    def burrowstatus():
        return str(burrow.getburrowstatus())
        #return ('', 200)

    @app.route('/burrowtogg')
    def burrowtogg():
        if burrow.getburrowstatus():
            burrow.burrowstatus(False)
        else:
            burrow.burrowstatus(True)
        return ('', 202)


    @app.route('/canceltimer')
    def canceltimer():
        burrow.canceltimer()
        return ('', 200)

    @app.route('/getsched')
    def printschd():
        msg = "<table>\n<tr>\n"
        msg = msg + "<th>Hour</th>\n"
        msg = msg + "<th>Base</th>\n"
        #msg = msg + "<th>H/L</th>\n"
        msg = msg + "</tr>\n"
        acstatuscache.checkstatus()

        #sched output format is {hourfloat:x.getbase()}
        scheddata = scheduler.websched(datetime.datetime.now())


        now = datetime.datetime.now()

        for key, val in scheddata.items():

            if (key%1) > 0:
                splited = str(key).split(".")
                dt = "{}:30".format(splited[0])
                dt = (datetime.datetime.strptime(dt, '%H:%M'))
                dt = dt.strftime("%-I:%M%p")
            else:
                key = int(key)
                dt = (datetime.datetime.strptime(str(key), '%H'))
                dt = dt.strftime("%-I:%M%p")


            msg = msg + "<tr>\n"
            msg = msg + "<td>{}</td>\n".format(dt)
            msg = msg + "<td>{}</td>\n".format(val)

            #msg = msg + "<td>{}/{}</td>\n".format(high[x],low[x])

            msg = msg + "</tr>\n"

            now = now + datetime.timedelta(minutes=30)

        msg = msg + "</table>"
        return msg

    #do not nead so much logging once its working

    app.logger.removeHandler(default_handler)
    #This should be run on a trusted network, since its open wide.
    app.run(host='0.0.0.0', port=5900)

if __name__ == "__main__":

    flaskrunner()

