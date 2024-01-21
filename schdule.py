import datetime
from libraries import loggerdo

from libraries import utils

import sys


class daybits:
    mode = None
    hour = None
    base = None
    high = None
    low = None

    def __init__(self, mode, hour, base, high, low):
        self.mode = mode
        self.hour = hour
        self.base = base
        self.high = high
        self.low = low


class day:
    date = None
    config = None

    activemode = None
    override = False
    modes = []
    cal = {}
    lastupdate = None
    moremode  = None

    def __init__(self, config):

        self.today = datetime.date.today()
        self.dayarray = []

        self.purgestart = config["purgestart"]
        self.cal = {}
        self.test = config["test"]
        self.activemode = None
        self.lastupdate = datetime.datetime.now()

        if config["mode"] == "heat":
            self.modes = config["heat-modes"]
            self.moremode = config["moremode"]
        else:
            self.modes = config["ac-modes"]
            # If its AC more mode shouold drop temp not bump it
            self.moremode = config["moremode"] * -1

        self.buildcal()
        # always sync
        self.synccalmode()

        self.dayload()

        loggerdo.log.debug("mongosched - day object setup complete.")
        self.fanstart = config["fans"]["start"]
        self.fanend = config["fans"]["end"]

        self.moremodebool = False
        #self.moremode = config["moremode"]


    # the cal is a dictonary, times to mode.
    # start with base as default
    def buildcal(self):
        loggerdo.log.debug("mongosched - Starting to build the cal")
        if len(self.cal) > 0:
            loggerdo.log.info("mongosched - self.cal has data already. Clearing it")
            self.cal.clear()

        # build cal dictonary, start of with default day
        for mode in self.modes:
            mode = self.modes[mode]
            loggerdo.log.info("mongosched - Checking mode: {} for default".format(mode))
            if mode['default']:
                loggerdo.log.info("mongosched - Found default, {}".format(mode['name']))
                defaultmode = mode['name']
                y = 0
                while y < 24:
                    self.cal.update({y: defaultmode})
                    y += 0.5
                break

        loggerdo.log.debug("mongosched - Built default mode, adding others.")
        # add schedule dictonary
        for mode in self.modes:
            mode = self.modes[mode]
            if mode['scheduled']:
                loggerdo.log.info("mongosched - Setting up mode, {}".format(mode["name"]))
                scheduledmode = mode['name']
                start = mode['start']
                end = mode['end']
                if end - start < 0:
                    # start and end cross midnight. Split up
                    loggerdo.log.info("mongosched - start and end cross midnight. Splitting up {}".format(scheduledmode))
                    while start < 24:
                        self.cal.update({start: scheduledmode})
                        start += 0.5
                    z = 0
                    while z < end:
                        self.cal.update({z: scheduledmode})
                        z += 0.5
                else:
                    # start and end do not corss midnight
                    loggerdo.log.info("mongosched - start and end are on same day for {}".format(scheduledmode))
                    while start <= end:
                        self.cal.update({start: scheduledmode})
                        start += 0.5

    def dayload(self):

        self.dayarray.clear()
        for mode in self.modes:

            high = self.modes[mode]['temp'] + self.modes[mode]['up']
            low = self.modes[mode]['temp'] - self.modes[mode]['down']

            x = 0

            while x < 24:
                self.dayarray.append(daybits(mode=self.modes[mode]['name'], hour=x, base=self.modes[mode]['temp'], high=high, low=low))
                x += 0.5


    def pullhourdetails(self, hour, mode=None):
        if not isinstance(hour, float):
            hour = utils.timefloor(hour)
        if not mode:
            mode = self.activemode
            loggerdo.log.debug("mongosched - mode not set for pullhourdetails, using current : {}".format(self.activemode))

        for bit in self.dayarray:

            if bit.hour == hour and bit.mode == mode:
                if self.moremodebool:
                    return bit.base + self.moremode, bit.high + self.moremode, bit.low + self.moremode
                else:
                    return bit.base, bit.high, bit.low


    def getmode(self):
        hourfloat = utils.timefloor(datetime.datetime.now())
        #return self.cal[hourfloat]
        return self.activemode


    def synccalmode(self):
        now = datetime.datetime.now()
        hourfloat = utils.timefloor(now)
        if not self.override:
            loggerdo.log.debug("mongosched - Doing a sync Cal Mode")
 
            if self.activemode != self.cal[hourfloat]:
                loggerdo.log.info("mongosched - synccalmode - Changing mode from, {} to {}".format(self.activemode, self.cal[hourfloat]))
                self.activemode = self.cal[hourfloat]
                # Need to update lastupdate timestamp to notify adaio that a change occured from this end
                self.lastupdate = datetime.datetime.now()
        else:
            loggerdo.log.debug("mongosched - Skippoing eval because override is set")

    # turn override off and go back to scheduled mode
    def disableoveride(self):
        self.override = False
        self.synccalmode()

    # override schedule, or scheduled change
    def changemode(self, newmode, override=False):
        if override:
            self.override = True
            loggerdo.log.debug("mongosched - Mode changing is off due to override")

        for mode in self.modes:
            mode = self.modes[mode]
            if newmode == mode['name']:
                loggerdo.log.info("mongosched - changemode -  Changing mode from, {} to {}".format(self.activemode, newmode))
                self.activemode = newmode
                # Need to update lastupdate timestamp to notify adaio that a change occured from this end
                self.lastupdate = datetime.datetime.now()


    def fantime(self):

        now = int(str(datetime.datetime.now().hour) + str("{:02d}".format(datetime.datetime.now().minute)))
        if (now > self.fanstart) and (now < self.fanend):
            loggerdo.log.debug("mongosched - fantime - fan can run, time for fan")
            return True
        else:
            loggerdo.log.debug("mongosched - fantime - fan can not run, no time for fan")
            return False

    def gettoday(self):
        return self.today

    def checkvalid(self):
        now = datetime.date.today()
        if self.today >= now:
            return True
        else:
            loggerdo.log.debug("mongosched - day not valid, starting next day")
            # Reload day data
            self.dayload()

            #rebuild cal?
            self.buildcal()
            # update today
            self.today = self.today + datetime.timedelta(days=1)
            loggerdo.log.info("mongosched - self.day is now set to {}".format(self.today))
            return False

    def increment(self, now=datetime.datetime.now()):
        if not isinstance(now, float):
            now = utils.timefloor(now)

        # find mode that we should adjust based on schedule
        schedmode = self.cal[now]
        for bit in self.dayarray:
            if bit.hour == now and bit.mode == schedmode:
                bit.base+=1
                bit.high+=1
                bit.low+=1
            else:
                sys.exit(666)

    def decrement(self, now=datetime.datetime.now()):
        if not isinstance(now, float):
            now = utils.timefloor(now)

        # find mode that we should adjust based on schedule
        schedmode = self.cal[now]

        for bit in self.dayarray:
            if bit.hour == now and bit.mode == schedmode:
                bit.base -= 1
                bit.high -= 1
                bit.low -= 1
            else:
                sys.exit(666)

    def updatebasetemp(self, now, temp, duration=3):
        if not isinstance(now, float):
            now = utils.timefloor(now)

        base, high, low = self.pullhourdetails(now)
        loggerdo.log.debug("mongosched - setting temp to {}, starting at time {}".format(temp, now))

        loggerdo.log.debug("mongosched - Base temp was, {}".format(base))

        high = (high - base) + temp
        low = temp - (base - low)

        end = now + duration

        while now < end:
            # loggerdo.log.info("mongosched - updating hour {}, setting base to {}".format(now, temp))
            if now > 23.5:
                break
            schedmode = self.cal[now]
            loggerdo.log.info("mongosched - updating hour {}, setting base to {} for mode {}".format(now, temp, self.getmode()))
            for bit in self.dayarray:
                if bit.hour == now and bit.mode == schedmode:
                    loggerdo.log.info('mongosched -  update {} to {} at {}'.format(schedmode,temp,now))
                    bit.base = temp
                    bit.high = high
                    bit.low = low
            now += .5
        self.lastupdate = datetime.datetime.now()

    def updatelowtemp(self, now, lowtemp, duration=3):
        if not isinstance(now, float):
            now = utils.timefloor(now)

        base, high, low = self.pullhourdetails(now)
        loggerdo.log.debug("mongosched - setting low temp to {}, starting at time {}".format(lowtemp, now))
        loggerdo.log.debug("mongosched - low temp was, {}".format(low))

        end = now + duration
        while now < end:
            loggerdo.log.debug("mongosched - updating hour {}, setting low to {}".format(now, lowtemp))
            if now > 23.5:
                break
            schedmode = self.cal[now]

            for bit in self.dayarray:
                if bit.hour == now and bit.mode == schedmode:
                    print(f'update lowtemop in {schedmode} to {lowtemp} at {now}')
                    bit.low = lowtemp
            now += .5
        self.lastupdate = datetime.datetime.now()

    def updatehightemp(self, now, hightemp, duration=3):
        if not isinstance(now, float):
            now = utils.timefloor(now)

        base, high, low = self.pullhourdetails(now)
        loggerdo.log.debug("mongosched - setting high temp to {}, starting at time {}".format(hightemp, now))
        loggerdo.log.debug("mongosched - high temp was, {}".format(high))

        end = now + duration

        while now < end:
            loggerdo.log.debug("mongosched - updating hour {}, setting high to {}".format(now, hightemp))
            if now > 23.5:
                break
            schedmode = self.cal[now]

            for bit in self.dayarray:
                if bit.hour == now and bit.mode == schedmode:
                    print(f'update high {schedmode} to {hightemp} at {now}')
                    bit.high = hightemp
            now += .5
        self.lastupdate = datetime.datetime.now()


    # Written specifically for control.py
    def pullpartsched(self, now=datetime.datetime.now()):
        if not isinstance(now, float):
            now = utils.timefloor(now)

        msg = '\n'
        until = now + 3

        while now < until:
            if now > 23.5:
                break
            schedmode = self.cal[now]
            base, high, low = self.pullhourdetails(hour=now, mode=schedmode)
            msg = msg + ("Hour-{} has high of {} and low of {}\n".format(now, high, low))
            now += 0.5

        return msg

    def getlastupdate(self):
        return self.lastupdate


