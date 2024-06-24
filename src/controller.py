import datetime
from libraries import loggerdo
import MQTTtalker
import HVACtalker
import time

class Burrow:
    ourhome = None
    schedule = None
    mqtttalker = None

    state = True
    mode = None

    heaterstate = False
    acstate = False
    fanstate = False

    fanStateLastChange = None
    coolStateLastChange = None
    heatStateLastChange = None


    quickchangeTime = None
    quickchangeSwing = None

    def __init__(self, home, schedule, config):
        self.debug = config["debug"]["controller"]
        self.ourhome = home
        self.schedule = schedule
        # self.acconfig = config['windowac']
        self.mqttserver = config["MQTT"]["mqttserver"]
        self.mqtttalker = MQTTtalker.broker(config)

        # Setup Fan
        self.fanStartDelay = config['fans']['fanStartDelay']
        self.acStartDelay = config['fans']['acStartDelay']
        self.heatStartDelay = config['fans']['heatStartDelay']
        self.fanEnabledState = config['fans']['state']
        self.defaultFanRuntime = config['fans']['defaultFanRuntime']



        self.coolStateLastChange = datetime.datetime.now()
        self.heatStateLastChange = datetime.datetime.now()
        self.fanStateLastChange = datetime.datetime.now()
        

        self.fantimer = False
        self.fantimertime = (datetime.datetime.now() - datetime.timedelta(minutes=1))

        # preset it all to false
        self.fanstate = False
        self.heaterstate = False
        self.acstate = False
        self.mode = None

        # state status should start true
        self.stateStatus = True

        # setup HVAC talker
        self.hvac = HVACtalker.hvactalk(config)

        
        # Start the setup
        self.setmode(config["mode"])


    # Setup heat/AC
    def setmode(self, mode):
        # setup mode
        loggerdo.log.debug(f"burrow - Burrow mmode should be set to - {mode}")
        if mode == "heat":
            self.mode = "heat"
            loggerdo.log.info("burrow - Burrow is set to heat mode")
        elif mode == "cool":
            self.mode = "cool"
            # setup AC, get the initial state of the wemo
            loggerdo.log.info("burrow - Burrow is set to AC mode")

        elif mode == "fan":
            self.mode = "fan"
            loggerdo.log.info("burrow - Burrow is set to fan mode")

        elif mode is False:
            self.mode = "off"
            # setup AC, get the initial state of the wemo
            loggerdo.log.info("burrow - Burrow is set to OFF mode")


    def synchvacstates(self):
        # limit the run of this to maybe prevent uneeded out of state messages

        if self.mode == "cool":
            if self.hvac.ac != self.acstate:
                loggerdo.log.info('burrow ac state {}, hvactalker ac state - {}'.format(self.acstate, self.hvac.ac))
                self.coolStateLastChange = datetime.datetime.now()
                self.acstate = self.hvac.ac               

        elif self.mode == "heat":
            if self.hvac.heat != self.heaterstate:
                loggerdo.log.info("burrow - error - hvac state out of sync with burrow, fixing - heat")
                self.heaterstate = self.hvac.heat
                self.heatStateLastChange = datetime.datetime.now()

        elif self.mode == "fan":
            loggerdo.log.debug("burrow - error - dont need to do anything for fan mode")
        elif self.mode == "off":
            loggerdo.log.debug("burrow - error - dont need to do anything for off mode")
        else:
             loggerdo.log.info("burrow - werid mode ??")

        # Fan not yet added really
        if self.hvac.fan != self.fanstate:
            loggerdo.log.info(f"burrow - error - fan is {self.hvac.fan} and burrow is {self.fanstate}")
            # unsynced state change, make sure fan timer is off
            self.fantimer = False
            self.fanStateLastChange = datetime.datetime.now()
            self.fanstate = self.hvac.fan



    def publishburrowmessage(self):
        loggerdo.log.debug(f"burrow - fan is {self.fanstate}")
        loggerdo.log.debug(f"burrow - heat is {self.heaterstate}")
        loggerdo.log.debug(f"burrow - ac is {self.acstate}")

        # Publish to homebridge every eval cycle
        self.mqtttalker.publishtemph(self.ourhome.getweighthouseavg(), self.ourhome.gethousehumidity())
        status = self.getburrowstatus()
        base, schedhigh, schedlow = self.schedule.pullhourdetails(datetime.datetime.now())

        self.mqtttalker.publishtarget(base)
        self.mqtttalker.publishhighlow(high=schedhigh, low=schedlow)


        loggerdo.log.debug("burrow - publish status of burrow itself - {}".format(status))
        if self.mode == "off" or status is False:
            self.mqtttalker.publishmode("off")
        else:
            self.mqtttalker.publishmode(self.schedule.getmode())
        self.mqtttalker.publishday(self.schedule.gettoday())
        if status is False:
            self.mqtttalker.publishsystem("off", True)
        else:
            self.mqtttalker.publishsystem(self.mode, self.getCurrentState())


    def getCurrentState(self):
        self.synchvacstates()
        if self.acstate:
            loggerdo.log.debug("burrow - getCurrentState is True, because AC")
            return True
        elif self.heaterstate:
            loggerdo.log.debug("burrow - getCurrentState is True, because HEAT")
            return True
        elif self.fanstate:
            loggerdo.log.debug("burrow - getCurrentState is True, because fanstate")
            return True
        else:
            loggerdo.log.debug("burrow - getCurrentState is False")
            return False

    def setBurrowStatus(self, status):
        if status:
            self.stateStatus = True
            loggerdo.log.info("burrow - setBurrowStatus is True. Turn Burrow on")
        else:
            self.stateStatus = False
            loggerdo.log.info("burrow - setBurrowStatus is True. Turn Burrow off")
    
    def getburrowstatus(self):
        return self.stateStatus
    
    def fanoffer(self):
        if self.fanstate is True:
            self.fanstate = False
            self.fanStateLastChange = datetime.datetime.now()
            self.hvac.FANoff()
            self.publishburrowmessage()

    def quickheaterchange(self, state):
        loggerdo.log.info(f"burrow - quickheaterchange - trying to set heat to  {state}")
        if state:
            madechange = self.hvac.HEATon()
            if madechange:
                self.HEATlastOn = datetime.datetime.now()
                self.heaterstate = True
        else:
            madechange = self.hvac.HEAToff()
            if madechange:
                self.HEATlastOff = datetime.datetime.now()
                self.heaterstate = False
        loggerdo.log.info(f"burrow - quickheaterchange - return was successful? - {madechange}")
        return madechange

    def quickACchange(self, state):
        if state:
            madechange = self.hvac.ACon()
            if madechange:
                self.AClastOn = datetime.datetime.now()
                self.acstate = True
        else:
            madechange = self.hvac.ACoff()
            if madechange:
                self.AClastOff = datetime.datetime.now()
                self.acstate = False
        loggerdo.log.info(f"burrow - quickACchange - return was successful? - {madechange}")
        return madechange
    
    def tunOnFan(self):
        if self.fanEnabledState:
            # only run in fan off
            if not self.fanstate:
                madechange = self.hvac.FANon()
                if madechange:
                    self.fantimer = True
                    self.fantimertime = (datetime.datetime.now() + datetime.timedelta(minutes=self.defaultFanRuntime))
                    self.fanstate = True
                    self.fanStateLastChange = datetime.datetime.now()
                    if self.debug:
                        loggerdo.log.info("burrow - Turning on fan timer, fan should run until {}".format(self.fantimertime))
                else:
                    loggerdo.log.info("burrow - did not turn on fan")
            else:
                loggerdo.log.info("burrow - Wanted to run on fan but its on, fan should run until {}".format(self.fantimertime))


    def getScheduleTemps(self):
        housetemp = self.ourhome.getweighthouseavg()
        btemp, schedhigh, schedlow = self.schedule.pullhourdetails(datetime.datetime.now())       



    def houseEval(self):
        #local variables
        madechange = False

        # do all the normal checks
        #
        #
         # sync cal to check if current mode is right mode. Away is a "force" mode so it wont be overwritten until that changes
        self.schedule.syncModeToCalendar()
        base, schedhigh, schedlow = self.schedule.pullhourdetails(datetime.datetime.now())
        housetemp = self.ourhome.getweighthouseavg()
        # check hvac
        self.hvac.run()

        # is burrow on? are the sensors okay?
        if not self.getburrowstatus() or housetemp is False:

            # make sure all systems are set to off

            if self.acstate is True:
                loggerdo.log.info("burrow - AC was on when system switched off, turning it off")
                madechange = self.hvac.ACoff()
                if madechange:
                    self.AClastOff = datetime.datetime.now()
                    self.acstate = False

            if self.heaterstate:
                loggerdo.log.info("burrow - Heat was on when system switched off, turning it off")
                madechange = self.hvac.HEAToff()
                if madechange:
                    self.HEATlastOff = datetime.datetime.now()
                    self.heaterstate = False
            if self.fanstate:
                loggerdo.log.info("burrow - Fan was on when system switched off, turning it off")
                madechange = self.hvac.FANoff()
                if madechange:
                    self.FanLastOff = datetime.datetime.now()
                    self.fanstate = False

            #send out updates
            self.publishburrowmessage()
            # if its the sensors, exit. If we are off stop processing 
            if housetemp is False:
                loggerdo.log.info("burrow - No sensors responding!!!")
                raise SystemExit("schedule - No sensors responding!!!")
            else:
                if self.debug:
                    loggerdo.log.info("burrow - burrow is off right now")
                else:
                    return False
                
        if self.mode == "cool":
            loggerdo.log.debug("burrow - ac status is {}".format(self.acstate))

            if housetemp >= schedhigh:
                if self.acstate is False:
                    # Check FAN
                    self.fanoffer()
                    if self.debug:
                        loggerdo.log.info("burrow - Turn AC on")
                    madechange = self.hvac.ACon()
                    if madechange:
                        self.coolStateLastChange = datetime.datetime.now()
                        self.acstate = True
                else:
                    loggerdo.log.debug("burrow - AC is already on")

            elif housetemp <= schedlow:
                if self.acstate is True:
                    if self.debug:
                        loggerdo.log.info("burrow - turn off the AC")
                    madechange = self.hvac.ACoff()
                    if madechange:
                        self.coolStateLastChange = datetime.datetime.now()
                        self.acstate = False
                else:
                    loggerdo.log.debug("burrow - AC is already off")
            else:
                loggerdo.log.debug("burrow - AC - No changes made - goldilocks")


        elif self.mode == "heat":
            # sync the heat to MQTT

            # heating mode flips the temp checks around
            loggerdo.log.debug("burrow - heater status is {}".format(self.heaterstate))

            if housetemp <= schedlow:
                # dont have an outside check yet.
                if not self.heaterstate:
                    # Check FAN
                    self.fanoffer()
                    if self.debug:
                        loggerdo.log.info("burrow - Should be turning heat on")
                    madechange = self.hvac.HEATon()
                    if madechange:
                        self.heatStateLastChange = datetime.datetime.now()
                        self.heaterstate = True
                else:
                    loggerdo.log.debug("burrow - Need heat, heat already on")

            elif housetemp >= schedhigh:
                # elif self.ourhome.gethightemp() >= schedhigh:
                if self.heaterstate:
                    if self.debug:
                        loggerdo.log.info("burrow - Should be turning off")
                    madechange = self.hvac.HEAToff()
                    if madechange:
                        self.heatStateLastChange = datetime.datetime.now()
                        self.heaterstate = False

                else:
                    loggerdo.log.debug("burrow - Do not need heat, heat already off")
            else:
                loggerdo.log.debug("burrow - HEAT - No changes made - goldilocks")
        else:
            loggerdo.log.debug("burrow - Neither heat or AC are on")
        
        # check out the fan now
        # cehck of heater and AC are off, if we fan mode should be on,  and no changes made this run
        if self.acstate is False and self.heaterstate is False and madechange is False and self.fanEnabledState:
            # see if fantimer is setup and fan is running
            if self.fantimer is True and self.fanstate is True:
                # fan is running, check if we should shut fan off
                if datetime.datetime.now() > self.fantimertime:
                    if self.debug:
                        loggerdo.log.info("burrow - Turn off fan timer, fan should have run until {}".format(self.fantimertime))

                self.fantimer = False
                madechange = self.hvac.FANoff()
                if madechange:
                    self.fanstate = False
                    self.fanStateLastChange = datetime.datetime.now()

            
            elif self.fantimer is True and self.fanstate is False:
                loggerdo.log.debug("burrow - fanrunner - fan timer running but fan off?")
                self.fantimer = False

            # check if AC has been off for enough time to turn on fan
            elif (self.coolStateLastChange + datetime.timedelta(minutes=self.acStartDelay) < datetime.datetime.now()) and \
                    (self.fanStateLastChange + datetime.timedelta(minutes=self.fanStartDelay) < datetime.datetime.now()) and \
                    self.fanstate is False and self.mode == "cool" and self.schedule.fantime():
                if self.debug:
                    loggerdo.log.info("burrow - fanrunner - time to turn on fan for a bit (ac mode)")
                madechange = self.hvac.FANon()
                if madechange:
                    self.fanstate = True
                    self.fanStateLastChange = datetime.datetime.now()

            # check if heat has been off for enough time to turn on fan
            elif (self.heatStateLastChange + datetime.timedelta(minutes=self.heatStartDelay) < datetime.datetime.now()) and \
                    (self.fanStateLastChange + datetime.timedelta(minutes=self.fanStartDelay) < datetime.datetime.now()) and \
                    self.fanstate is False and self.mode == "heat" and self.schedule.fantime():
                if self.debug:
                    loggerdo.log.info("burrow - fanrunner - time to turn on fan for a bit (heat mode)")
                madechange = self.hvac.FANon()
                if madechange:
                    self.fanstate = True
                    self.fanStateLastChange = datetime.datetime.now()
            
            # check if fan has been off long enough to turn on. only run in fan only mode
            elif (self.fanStateLastChange + datetime.timedelta(minutes=self.fanStartDelay) < datetime.datetime.now()) and \
                    self.fanstate is False and self.mode == "fan" and self.schedule.fantime() and self.getburrowstatus():
                if self.debug:
                    loggerdo.log.info("burrow - fanrunner - time to turn on fan for a bit (fan only mode)")
                madechange = self.hvac.FANon()
                if madechange:
                    self.fanstate = True
                    self.fanStateLastChange = datetime.datetime.now()

            elif self.fanstate is True and (
                    self.fanStateLastChange + datetime.timedelta(minutes=self.defaultFanRuntime) < datetime.datetime.now()):
                if self.debug:
                    loggerdo.log.info(f"burrow - fanrunner - fan has been running for {self.defaultFanRuntime} mins, turn off")
                madechange = self.hvac.FANoff()
                if madechange:
                    self.fanstate = False
                    self.fanStateLastChange = datetime.datetime.now()
        # send updates
        self.publishburrowmessage()
        loggerdo.log.debug(f"burrow - fan is {self.fanstate}")
        loggerdo.log.debug(f"burrow - heat is {self.heaterstate}")
        loggerdo.log.debug(f"burrow - ac is {self.acstate}")
        loggerdo.log.debug("burrow - burrow is enabled T/F {}".format(self.getburrowstatus()))
        return madechange

