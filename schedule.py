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
    debug = None
    activemode = None
    isAway = False
    modes = []
    cal = {}
    lastCalendarUpdate = None


    def __init__(self, config):

        self.today = datetime.date.today()
        self.dayarray = []
        self.cal = {}
        self.activemode = None
        self.debug = config["debug"]["schedule"]
        self.lastCalendarUpdate = datetime.datetime.now()

        self.isAway = False


        if config["mode"] == "heat":
            self.mode = "heat"
            self.dayLayout = config["heat"]
            self.modes = config["heat-modes"]
            self.moremode = config["moremode"]
        else:
            self.modes = config["cool"]
            # If its AC more mode shouold drop temp not bump it
            self.mode = "cool"
            self.moremode = config["moremode"] * -1

        self.buildcal()
        # always sync
        self.synccalmode()

        self.createDay()

        loggerdo.log.debug("schedule - day object setup complete.")
        self.fanstart = config["fans"]["start"]
        self.fanend = config["fans"]["end"]

        self.moremodebool = False
        #self.moremode = config["moremode"]


    # the cal is a dictonary, times to mode.
    # start with base as default
    def buildcal(self):
        loggerdo.log.debug("schedule - Starting to build the cal")
        if len(self.cal) > 0:
            if self.debug:
                loggerdo.log.info("schedule - self.cal has data already. Clearing it")
            self.cal.clear()
        
        #check for default, make sure there is only 1
        defaultCount = 0
        for section in self.dayLayout:
            if section['default']:
                defaultCount +=1
        if defaultCount > 1:
            loggerdo.log.error("schedule - Checking mode: {} for default".format(mode))
            raise SystemExit("schedule - Checking mode: {} for default".format(mode))
        
        # build cal dictonary, start of with default day
        for section in self.dayLayout:
            mode = self.dayLayout[section]
            loggerdo.log.info("schedule - Checking mode: {} for default".format(mode))
            if mode['default']:
                if self.debug:
                    if self.debug:
                        loggerdo.log.info("schedule - Found default, {}".format(mode['name']))
                defaultmode = mode['name']
                y = 0
                # assign the cal to default
                while y < 24:
                    self.cal.update({y: defaultmode})
                    y += 0.5
                break

        loggerdo.log.debug("schedule - Built default mode, adding others.")
        # add schedule dictonary
        for section in self.dayLayout:
            mode = self.dayLayout[section]
            if mode['scheduled']:
                loggerdo.log.info("schedule - Setting up mode, {}".format(mode["name"]))
                scheduledmode = mode['name']
                start = mode['start']
                end = mode['end']
                if end - start < 0:
                    # start and end cross midnight. Split up
                    if self.debug:
                        loggerdo.log.info("schedule - start and end cross midnight. Splitting up {}".format(scheduledmode))
                    while start < 24:
                        self.cal.update({start: scheduledmode})
                        start += 0.5
                    z = 0
                    while z < end:
                        self.cal.update({z: scheduledmode})
                        z += 0.5
                else:
                    # start and end do not corss midnight
                    if self.debug:
                        loggerdo.log.info("schedule - start and end are on same day for {}".format(scheduledmode))
                    while start <= end:
                        self.cal.update({start: scheduledmode})
                        start += 0.5

    def createDay(self):

        self.dayarray.clear()
        for section in self.dayLayout:
            # up/down at aded from base temp
            high = self.modes[section]['temp'] + self.modes[section]['up']
            low = self.modes[section]['temp'] - self.modes[section]['down']
            # create an array of daybit objects for every mode and every 30 minutes 
            x = 0
            while x < 24:
                self.dayarray.append(daybits(mode=self.modes[section]['name'], hour=x, base=self.modes[section]['temp'], high=high, low=low))
                x += 0.5


    def pullhourdetails(self, hour, mode=None):
        if not isinstance(hour, float):
            hour = utils.timefloor(hour)
        # check if mode is set or not
        if mode is None:
            # if its set, and we are away. Change to away, else use active
            if self.isAway:
                mode = "away"
            else:
                mode = self.activemode
        
        loggerdo.log.debug("schedule - mode not set for pullhourdetails, using current : {}".format(self.activemode))
        for bit in self.dayarray:
            if bit.hour == hour and bit.mode == mode:
                return bit.base, bit.high, bit.low


    def getmode(self):
        if self.isAway:
            return "away"
        else:
            return self.activemode

    def setAway(self, toggle):
        if toggle:
            self.isAway = True
        else:
            self.isAway = False
    
    def syncModeToCalendar(self):
        now = datetime.datetime.now()
        hourfloat = utils.timefloor(now)

        if self.activemode != self.cal[hourfloat]:
            loggerdo.log.info("schedule - synccalmode - Changing mode from, {} to {}".format(self.activemode, self.cal[hourfloat]))
            self.activemode = self.cal[hourfloat]
            # Need to update lastCalendarUpdate timestamp to notify adaio that a change occured from this end
            self.lastCalendarUpdate = datetime.datetime.now()


    def fantime(self):

        now = int(str(datetime.datetime.now().hour) + str("{:02d}".format(datetime.datetime.now().minute)))
        if (now > self.fanstart) and (now < self.fanend):
            loggerdo.log.debug("schedule - fantime - fan can run, time for fan")
            return True
        else:
            loggerdo.log.debug("schedule - fantime - fan can not run, no time for fan")
            return False

    def gettoday(self):
        return self.today

    def rebuildDay(self):
        # Reload day data
        self.createDay()

        #rebuild cal?
        self.buildcal()
        # update today
        self.today = self.today + datetime.timedelta(days=1)
        loggerdo.log.info("schedule - self.day is now set to {}".format(self.today))

    def checkvalid(self):
        now = datetime.date.today()
        if self.today >= now:
            return True
        else:
            loggerdo.log.debug("schedule - day not valid, starting next day")
            self.rebuildDay()
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
        loggerdo.log.debug("schedule - setting temp to {}, starting at time {}".format(temp, now))

        loggerdo.log.debug("schedule - Base temp was, {}".format(base))

        high = (high - base) + temp
        low = temp - (base - low)

        end = now + duration

        while now < end:
            # loggerdo.log.info("schedule - updating hour {}, setting base to {}".format(now, temp))
            if now > 23.5:
                break
            schedmode = self.cal[now]
            loggerdo.log.info("schedule - updating hour {}, setting base to {} for mode {}".format(now, temp, self.getmode()))
            for bit in self.dayarray:
                if bit.hour == now and bit.mode == schedmode:
                    loggerdo.log.info('schedule -  update {} to {} at {}'.format(schedmode,temp,now))
                    bit.base = temp
                    bit.high = high
                    bit.low = low
            now += .5
        self.lastCalendarUpdate = datetime.datetime.now()

    def updatelowtemp(self, now, lowtemp, duration=3):
        if not isinstance(now, float):
            now = utils.timefloor(now)

        base, high, low = self.pullhourdetails(now)
        loggerdo.log.debug("schedule - setting low temp to {}, starting at time {}".format(lowtemp, now))
        loggerdo.log.debug("schedule - low temp was, {}".format(low))

        end = now + duration
        while now < end:
            loggerdo.log.debug("schedule - updating hour {}, setting low to {}".format(now, lowtemp))
            if now > 23.5:
                break
            schedmode = self.cal[now]

            for bit in self.dayarray:
                if bit.hour == now and bit.mode == schedmode:
                    print(f'update lowtemop in {schedmode} to {lowtemp} at {now}')
                    bit.low = lowtemp
            now += .5
        self.lastCalendarUpdate = datetime.datetime.now()

    def updatehightemp(self, now, hightemp, duration=3):
        if not isinstance(now, float):
            now = utils.timefloor(now)

        base, high, low = self.pullhourdetails(now)
        loggerdo.log.debug("schedule - setting high temp to {}, starting at time {}".format(hightemp, now))
        loggerdo.log.debug("schedule - high temp was, {}".format(high))

        end = now + duration

        while now < end:
            loggerdo.log.debug("schedule - updating hour {}, setting high to {}".format(now, hightemp))
            if now > 23.5:
                break
            schedmode = self.cal[now]

            for bit in self.dayarray:
                if bit.hour == now and bit.mode == schedmode:
                    print(f'update high {schedmode} to {hightemp} at {now}')
                    bit.high = hightemp
            now += .5
        self.lastCalendarUpdate = datetime.datetime.now()


    def getlastCalendarUpdate(self):
        return self.lastCalendarUpdate


