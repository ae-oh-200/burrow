import datetime
from libraries import loggerdo
import MQTTtalker
from libraries import occupied
import HVACtalker
import time

class Burrow:
    ourhome = None
    schedule = None
    anyonehome = None
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
        self.mqtttalker = MQTTtalker.broker(config["MQTT"])

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


        self.familyping = occupied.occupied(config)
        self.anyonehome = self.familyping.anyonehome()

        self.homeAwayOverride = False


        self.syncstatecounter = 0



        # preset it all to false
        self.fanstate = False
        self.heaterstate = False
        self.acstate = False
        self.mode = None

        # state status should start true
        self.stateStatus = True

        # setup HVAC talker
        self.hvac = HVACtalker.hvactalk(mqttserver=config["MQTT"]["mqttserver"], controlRoot=config["controlRoot"], debug= config["debug"]["hvactalker"])

        #
        self.moretime = config["moretime"]
        
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
                self.self.heatStateLastChange = datetime.datetime.now()

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

        # send out al mqtt updates
        
        self.mqtttalker.publishaway(self.anyonehome)
        self.mqtttalker.publishmoremode(self.schedule.moremodebool)

        loggerdo.log.debug("burrow - publish status of burrow itself - {}".format(status))

        self.mqtttalker.publishmode(self.schedule.getmode())
        self.mqtttalker.publishday(self.schedule.gettoday())

        if self.anyonehome is False and self.homeAwayOverride is False:
            loggerdo.log.debug(
                "burrow - publishburrowmessage - publish away, status {}, anyonehome {}, override{}".format(status,
                                                                                                            self.anyonehome,
                                                                                                            self.homeAwayOverride))
            self.mqtttalker.publishburrow(state="Out")

        #fan is here because I need to tell HA if fan is on
        elif self.fanstate:
            self.mqtttalker.publishburrow(state="Fan")

        elif self.getburrowstatus() and (self.anyonehome or self.homeAwayOverride):
            loggerdo.log.debug(
                "burrow - publishburrowmessage - publish burrow is on, status {}, anyonehome {}, overridee{}, mode is {}".format(
                    status, self.anyonehome, self.homeAwayOverride, self.schedule.getmode()))
            self.mqtttalker.publishburrow(state="Home")

        elif status is False:
            loggerdo.log.debug("burrow - publishburrowmessage - publish burrow off")
            self.mqtttalker.publishburrow(state="Off")



        loggerdo.log.debug(
            "burrow - publishburrowmessage - publish {} to {}.".format(self.mode, self.getCurrentState()))
        self.mqtttalker.publishsystem(self.mode, self.getCurrentState())


    def getCurrentState(self):
        self.synchvacstates()
        if self.acstate:
            loggerdo.log.debug("burrow - getCurrentState is True, because AC")
            return True
        elif self.heaterstate:
            loggerdo.log.debug("burrow - getCurrentState is True, because HEAT")
            return True
        else:
            loggerdo.log.debug("burrow - getCurrentState is False")
            return False

    def setBurrowStatus(self, status):
        if status:
            self.stateStatus = True
        else:
            self.stateStatus = False
    
    def getburrowstatus(self):
        return self.stateStatus
    

    def turnonawayoverride(self):
        # self.schedule.changemode('away', True)
        # self.schedule.disableoveride()
        self.homeAwayOverride = True

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
        loggerdo.log.info(f"burrow - quickheaterchange - return was suessfull? - {madechange}")
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


    # Turns awaymode on in the schdule object
    def awaymode(self):

        # check if anyone is home?
        # the return should be true if someone is home
        checkforanyonehome = self.familyping.anyonehome()
        # clear old override if someone is home now

        if checkforanyonehome and self.homeAwayOverride:
            loggerdo.log.info("burrow - someone is home now, turning off the awaymode override")
            self.homeAwayOverride = False

        # check if no one is home and the home override is on
        if checkforanyonehome is False and self.homeAwayOverride is True:
            # loggerdo.log.info("burrow - Away mode override on, dont allow away mode")
            # self.schedule.changemode('away', True)
            if self.schedule.getmode() == 'away':
                loggerdo.log.info("burrow - Away mode override on, dont allow away mode. Turn off override")
                self.schedule.setAway(False)

        else:
            if self.anyonehome != checkforanyonehome:
                if self.debug:
                    loggerdo.log.info("burrow - change detected in awaymode")

                # if someone is home.
                if checkforanyonehome:
                    if self.anyonehome is False:
                        loggerdo.log.info(
                            "burrow - Turn off away mode someone is home (homeaway override not conisdered)")
                    self.schedule.setAway(False)
                    self.anyonehome = checkforanyonehome
                    self.homeAwayOverride = False
                else:
                    # no one is home
                    self.schedule.setAway(True)
                    self.anyonehome = checkforanyonehome
            else:
                loggerdo.log.debug("burrow - no change deteced in awaymode")
                # make sure override is off
                self.homeAwayOverride = False

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
                # leave function
                return True
            
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


