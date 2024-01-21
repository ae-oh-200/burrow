import datetime
from libraries import loggerdo
import MQTTtalker
import occupied
import HVACtalker
import time as clock


class Burrow:
	lastupdate = None
	manualtimer = None

	heatertimer = None

	ourhome = None
	schedule = None
	anyonehome = None
	mqtttalker = None

	state = True
	statelasteupdate = None
	statetimer = None

	mode = None

	heat = False
	ac = False
	fan = False

	heaterstate = False
	heaterlastupdate = None
	acstate = False
	AClastUpdate = None

	AClastOn = None
	AClastOff = None

	HEATlastOn = None
	HEATastOff = None

	fanstate = False
	FanLastUpdate = None

	initializetempfailcount = 0

	force = None
	slap = None
	alert = None

	anyonehomeoverride = None
	moremodetime = None
	moretime = None

	def __init__(self, home, schedule, config, alert):
		self.mydb = None
		self.ourhome = home
		self.schedule = schedule
		# self.acconfig = config['windowac']
		self.test = config["test"]
		self.mqttserver = config["MQTT"]["mqttserver"]
		self.mqtttalker = MQTTtalker.broker(config["MQTT"])

		# Star the setup
		self.setmode(config["mode"])

		# Setup Fan
		self.maxfanontime = config['fans']['maxfanontime']
		self.offtime = config['fans']['offtime']
		self.acdelay = config['fans']['acdelay']
		self.heatdelay = config['fans']['heatdelay']
		self.fanenabledstate = config['fans']['state']
		self.defaultfanon = config['fans']['defaultfanon']
		# self.force = False

		# Intialize the timers so that they are not "None". I set them all to -5 minutes so they do not affect app
		self.manualtimer = (datetime.datetime.now() - datetime.timedelta(minutes=5))
		self.heatertimer = (datetime.datetime.now() - datetime.timedelta(minutes=5))
		self.lastupdate = (datetime.datetime.now() - datetime.timedelta(minutes=5))
		self.statelasteupdate = (datetime.datetime.now() - datetime.timedelta(seconds=5))
		self.AClastUpdate = (datetime.datetime.now() - datetime.timedelta(minutes=5))

		self.AClastOn = (datetime.datetime.now() - datetime.timedelta(minutes=1))
		self.AClastOff = (datetime.datetime.now() - datetime.timedelta(minutes=1))

		self.HEATlastOn = (datetime.datetime.now() - datetime.timedelta(minutes=1))
		self.HEATlastOff = (datetime.datetime.now() - datetime.timedelta(minutes=1))

		self.FanLastUpdate = (datetime.datetime.now() - datetime.timedelta(minutes=1))
		self.FanLastOn = (datetime.datetime.now() - datetime.timedelta(minutes=1))
		self.FanLastOff = (datetime.datetime.now() - datetime.timedelta(minutes=1))

		self.fantimer = False
		self.fantimertime = (datetime.datetime.now() - datetime.timedelta(minutes=1))

		self.moremodetime = (datetime.datetime.now() - datetime.timedelta(minutes=1))
		self.familyping = occupied.occupied(config)
		self.anyonehome = self.familyping.anyonehome()
		self.anyonehomeoverride = False


		self.syncstatecounter = 0
		# self.anyonehome = self.ourhome.checkanyonehome()

		self.fanstate = False
		self.heaterstate = False
		self.acstate = False

		self.slap = 0

		self.alerta = alert

		# setup HVAC talker
		self.hvac = HVACtalker.hvactalk(emalert=alert)

		#
		self.moretime = config["moretime"]

	# Setup heat/AC
	def setmode(self, mode):
		# setup mode
		loggerdo.log.debug(f"burrow - Burrow mmode should be set to - {mode}")
		if mode == "heat":
			self.heat = True
			self.mode = "heat"
			loggerdo.log.debug("burrow - Burrow is set to heat mode")
			# set heater off
			self.heaterstate = False

		elif mode == "ac":
			self.ac = True
			self.mode = "ac"
			# setup AC, get the initial state of the wemo
			loggerdo.log.debug("burrow - Burrow is set to AC mode")
			self.acstate = False

		elif mode == "fan":
			self.fan = True
			self.mode = "off"
			loggerdo.log.debug("burrow - Burrow is set to fan mode")

		elif mode is False:
			self.mode = "off"
			# setup AC, get the initial state of the wemo
			loggerdo.log.debug("burrow - Burrow is set to OFF mode")

	def getmode(self):
		return self.mode

	def overallstate(self):

		self.synchvacstates()
		if self.acstate:
			loggerdo.log.debug("burrow - overallstate is True, because AC")
			return True
		elif self.heaterstate:
			loggerdo.log.debug("burrow - overallstate is True, because HEAT")
			return True
		else:
			loggerdo.log.debug("burrow - overallstate is False")
			return False

	def synchvacstates(self):
		# limit the run of this to maybe prevent uneeded out of state messages
		if self.syncstatecounter <= 3:
			self.syncstatecounter +=1
			return
		else:
			self.syncstatecounter = 0
		if self.ac is True:
			if self.hvac.ac != self.acstate:
				loggerdo.log.info("burrow - error - hvac state out of sync with burrow, fixing - ac")
				loggerdo.log.info('burrow ac state {}, hvactalker ac state - {}'.format(self.acstate, self.hvac.ac))

				# sync off times
				if self.hvac.ac:
					self.AClastOn = datetime.datetime.now()
				else:
					self.AClastOff = datetime.datetime.now()
				self.acstate = self.hvac.ac

		if self.heat is True:
			if self.hvac.heat != self.heaterstate:
				loggerdo.log.info("burrow - error - hvac state out of sync with burrow, fixing - heat")

				if self.hvac.heat:
					self.HEATlastOn = datetime.datetime.now()
				else:
					self.HEATlastOff = datetime.datetime.now()
				self.heaterstate = self.hvac.heat

		# Fan not yet added really
		if self.hvac.fan != self.fanstate:
			loggerdo.log.info("burrow - error - hvac state out of sync with burrow, fixing - fan")
			loggerdo.log.info(f"burrow - error - fan is {self.hvac.fan} and burrow is {self.fanstate}")
			if self.hvac.fan:
				self.FanLastOn = datetime.datetime.now()
			else:
				self.FanLastOff = datetime.datetime.now()
			# unsynced state change, make sure fan timer is off
			loggerdo.log.debug("burrow - disable fan timer if running. out of sync fan")
			self.fantimer = False
			self.FanLastUpdate = datetime.datetime.now()
			self.fanstate = self.hvac.fan

	def publishburrowmessage(self):
		loggerdo.log.debug(f"burrow - fan is {self.fanstate}")
		loggerdo.log.debug(f"burrow - heat is {self.heaterstate}")
		loggerdo.log.debug(f"burrow - ac is {self.acstate}")

		# Publish to homebridge every eval cycle
		self.mqtttalker.publishtemph(self.ourhome.getweighthouseavg(), self.ourhome.gethousehumidity())

		base, schedhigh, schedlow = self.schedule.pullhourdetails(datetime.datetime.now())

		self.mqtttalker.publishtarget(base)
		self.mqtttalker.publishhighlow(high=schedhigh, low=schedlow)

		# send out al mqtt updates
		status = self.getburrowstatus()

		self.mqtttalker.publishaway(self.anyonehome)
		self.mqtttalker.publishmoremode(self.schedule.moremodebool)

		loggerdo.log.debug("burrow - publish status of burrow itself - {}".format(status))

		self.mqtttalker.publishmode(self.schedule.getmode())
		self.mqtttalker.publishday(self.schedule.gettoday())

		if self.getburrowstatus() and (self.anyonehome is False and self.anyonehomeoverride is False):
			loggerdo.log.debug(
				"burrow - publishburrowmessage - publish away, status {}, anyonehome {}, override{}".format(status,
				                                                                                            self.anyonehome,
				                                                                                            self.anyonehomeoverride))
			self.mqtttalker.publishburrow(state="Out")

		elif self.fanstate:
			self.mqtttalker.publishburrow(state="Fan")

		elif self.getburrowstatus() and (self.anyonehome or self.anyonehomeoverride):
			loggerdo.log.debug(
				"burrow - publishburrowmessage - publish burrow is on, status {}, anyonehome {}, overridee{}, mode is {}".format(
					status, self.anyonehome, self.anyonehomeoverride, self.schedule.getmode()))
			self.mqtttalker.publishburrow(state="Home")

		elif status is False:
			loggerdo.log.debug("burrow - publishburrowmessage - publish burrow off")
			self.mqtttalker.publishburrow(state="Off")

		self.mqtttalker.publishtimer(self.timercheck())

		# Publish overall state
		if self.fanstate:
			loggerdo.log.debug("burrow - publishburrowmessage - publish fanstate on")
			self.mqtttalker.publishsystem('fan_only', True)
		else:
			loggerdo.log.debug(
				"burrow - publishburrowmessage - publish {} to {}.".format(self.mode, self.overallstate()))
			self.mqtttalker.publishsystem(self.mode, self.overallstate())

	# Disable or enable the burrow 'engine'
	def burrowstatus(self, status, timer=0):
		# lets you update the status of burrow. Turning off here will allow eval to be bypassed
		if timer > 23:
			loggerdo.log.info("burrow - disable timer set to long, resetting to 0")
			timer = 0
		if status != self.state:
			self.statelasteupdate = datetime.datetime.now()
			if status == False and timer == 0:
				loggerdo.log.info("burrow - Burrow state set to off indefinitely")
				self.state = False
				self.disablemoremode()
				self.anyonehomeoverride = False
			elif status == False and timer != 0:
				loggerdo.log.info("burrow - Burrow state set to off for {} hours".format(timer))
				self.state = False
				self.statetimer = datetime.datetime.now() + datetime.timedelta(hours=timer)
				self.disablemoremode()
				self.anyonehomeoverride = False
			elif status == True:
				loggerdo.log.info("burrow - Burrow state set back on")
				self.state = True
				# Set timer back to not
				self.statetimer = None

		self.publishburrowmessage()

	# check if burrrow is enabled or not
	def getburrowstatus(self):
		if self.state == False and isinstance(self.statetimer, datetime.datetime):
			loggerdo.log.info("burrow - State is false and timer is running")
			if datetime.datetime.now() > self.statetimer:
				loggerdo.log.info("burrow - Timer is up, enabling Burrow")
				self.state = True
				self.statetimer = None
			else:
				loggerdo.log.info("burrow - Timer is still running, set to {}".format(self.statetimer))

		return self.state

	# returns timer, if disabled for a time period or None
	def getburrowstatustimer(self):
		if isinstance(self.statetimer, datetime.datetime):
			return self.statetimer
		else:
			return None

	def getheaterlastupdate(self):
		return self.heaterlastupdate

	def getheatstatus(self):
		return self.heaterstate

	# override timer starting
	def starttimer(self, time):
		loggerdo.log.debug("burrow - manual timer starting now for {}".format(time))
		self.manualtimer = (datetime.datetime.now() + datetime.timedelta(minutes=time))

	def canceltimer(self):
		self.manualtimer = datetime.datetime.now()

	# check override timer. False = off
	def timercheck(self):
		if self.manualtimer > datetime.datetime.now():
			loggerdo.log.info("burrow - Timer is running and set for {}".format(self.manualtimer.time()))
			return False
		else:
			return True
		
#	def sendalert(self, system, message):
#		loggerdo.log.debug("burrow - sending alert for - {}".format(system))
#		subject = "{} threw an error".format(system)
#		message = "{}\n current time is {}, we will keep trying".format(message, datetime.datetime.now())
#		self.alerta.shout(subject, message)

	def turnonawayoverride(self):
		# self.schedule.changemode('away', True)
		# self.schedule.disableoveride()
		self.anyonehomeoverride = True

	# Turns awaymode on in the schdule object
	def awaymode(self):

		# check if anyone is home?
		# the return should be true if someone is home
		checkforanyonehome = self.familyping.anyonehome()
		# clear old override if someone is home now

		if checkforanyonehome and self.anyonehomeoverride:
			loggerdo.log.info("burrow - someone is home now, turning off the awaymode override")
			self.anyonehomeoverride = False

		if checkforanyonehome is False and self.anyonehomeoverride is True:
			# loggerdo.log.info("burrow - Away mode override on, dont allow away mode")
			# self.schedule.changemode('away', True)
			if self.schedule.getmode() == 'away':
				loggerdo.log.info("burrow - Away mode override on, dont allow away mode. Turn off override")
				self.schedule.disableoveride()

		else:
			if self.anyonehome != checkforanyonehome:

				loggerdo.log.info("burrow - change deteced in awaymode")

				if checkforanyonehome:
					# someone is home
					if self.anyonehome is False:
						loggerdo.log.info(
							"burrow - Turn off away mode someone is home (homeaway override not conisdered)")
					self.schedule.disableoveride()
					self.anyonehome = checkforanyonehome
					self.anyonehomeoverride = False
				else:
					# no one is home
					self.schedule.changemode('away', True)
					self.anyonehome = checkforanyonehome
			else:
				loggerdo.log.debug("burrow - no change deteced in awaymode")
				# make sure override is off
				self.anyonehomeoverride = False

	def forcetoggle(self):
		if self.force:
			self.force = False
		else:
			self.force = True

	def turnonfantimer(self):
		if self.fanenabledstate:
			self.fantimer = True
			self.fantimertime = (datetime.datetime.now() + datetime.timedelta(minutes=self.defaultfanon))
			self.fanstate = True
			self.FanLastUpdate = datetime.datetime.now()
			self.FanLastOn = datetime.datetime.now()
			self.hvac.FANon()
			loggerdo.log.info("burrow - Turning on fan timer, fan should run until {}".format(self.fantimertime))
		else:
			loggerdo.log.info("burrow - not turning on fan timer".format(self.fantimertime))

	def checkfantimer(self):
		# Check to see if fan timer is still valid
		if datetime.datetime.now() > self.fantimertime:
			loggerdo.log.info("burrow - Turn off fan timer, fan should have run until {}".format(self.fantimertime))
			# turn fan and fan timer off
			self.fantimer = False
			self.hvac.FANoff()
			self.fanstate = False
			self.FanLastUpdate = datetime.datetime.now()
			self.FanLastOff = datetime.datetime.now()

	def fanoffer(self):
		if self.fanstate is True:
			self.fanstate = False
			self.FanLastUpdate = datetime.datetime.now()
			self.FanLastOff = datetime.datetime.now()
			self.hvac.FANoff()
			self.publishburrowmessage()

	def fanrunner(self):
		# check first if fan has been disbaled
		if self.fanenabledstate is False:
			return False

		# check if anyone home
		if self.anyonehome is False:
			# was fan running between anyonehome going false and now.
			if self.fantimer is True and self.fanstate is True:
				loggerdo.log.info("burrow - fanrunner - stopping fanrunner because no one home")
				self.hvac.FANoff()

				self.fanstate = False
				self.FanLastUpdate = datetime.datetime.now()
				self.FanLastOff = datetime.datetime.now()
				self.fantimer = False
			loggerdo.log.debug("burrow - fanrunner - skipping fanrunner because no one home")
			return

		# check first if ac or heat is on
		if self.acstate is False and self.heaterstate is False:
			loggerdo.log.debug(f"burrow - fanrunner - fantimer is {self.fantimer} and fanstate is {self.fanstate}")

			if self.fantimer is True and self.fanstate is True:
				# fan is running, check if we should shut fan off
				self.checkfantimer()
				# leave function
				pass
			elif self.fantimer is True and self.fanstate is False:
				loggerdo.log.debug("burrow - fanrunner - fan timer running but fan off?")
				self.fantimer = False

			# self.heatdelay

			# check if AC has been off for 10+ mins
			if (self.AClastOff + datetime.timedelta(minutes=self.acdelay) < datetime.datetime.now()) and \
					(self.FanLastOff + datetime.timedelta(minutes=self.offtime) < datetime.datetime.now()) and \
					self.fanstate is False and self.ac and self.schedule.fantime() and self.getburrowstatus():
				loggerdo.log.debug("burrow - fanrunner - time to turn on fan for a bit (ac mode)")
				self.hvac.FANon()
				self.fanstate = True
				self.FanLastUpdate = datetime.datetime.now()
				self.FanLastOn = datetime.datetime.now()

			elif (self.HEATlastOff + datetime.timedelta(minutes=self.heatdelay) < datetime.datetime.now()) and \
					(self.FanLastOff + datetime.timedelta(minutes=self.offtime) < datetime.datetime.now()) and \
					self.fanstate is False and self.heat and self.schedule.fantime() and self.getburrowstatus():
				loggerdo.log.debug("burrow - fanrunner - time to turn on fan for a bit (heat mode)")
				self.hvac.FANon()
				self.fanstate = True
				self.FanLastUpdate = datetime.datetime.now()
				self.FanLastOn = datetime.datetime.now()

			elif (self.FanLastOff + datetime.timedelta(minutes=self.offtime) < datetime.datetime.now()) and \
					self.fanstate is False and self.fan and self.schedule.fantime() and self.getburrowstatus():
				loggerdo.log.debug("burrow - fanrunner - time to turn on fan for a bit (fan only mode)")
				self.hvac.FANon()
				self.fanstate = True
				self.FanLastUpdate = datetime.datetime.now()
				self.FanLastOn = datetime.datetime.now()

			elif self.fanstate is True and (
					self.FanLastOn + datetime.timedelta(minutes=self.maxfanontime) < datetime.datetime.now()):
				loggerdo.log.info(f"burrow - fanrunner - fan has been running for {self.maxfanontime} mins, turn off")
				self.fanstate = False
				self.hvac.FANoff()
				self.FanLastUpdate = datetime.datetime.now()
				self.FanLastOff = datetime.datetime.now()

			# lif self.schedule.fantime() is False and self.fanstate is True:
			elif self.schedule.fantime() is False and self.fantimer is True:
				loggerdo.log.debug("burrow - fanrunner - out of schedule, turn fan off")
				self.hvac.FANoff()
				self.fanstate = False
				self.FanLastUpdate = datetime.datetime.now()
				self.FanLastOff = datetime.datetime.now()
				self.fantimer = False

			else:
				loggerdo.log.debug("burrow - fanrunner - No changes be make")
				pass

		return True

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

	def enabledmoremode(self):
		self.schedule.moremodebool = True
		self.moremodetime = datetime.datetime.now()
		loggerdo.log.info(
			f"burrow - Turn moremode on. Auto moremode off at {self.moremodetime + datetime.timedelta(hours=self.moretime)}")

	def disablemoremode(self):
		self.schedule.moremodebool = False

	def checkmoremode(self):
		if self.schedule.moremodebool:
			if self.moremodetime + datetime.timedelta(hours=self.moretime) < datetime.datetime.now():
				loggerdo.log.info("burrow - time to turn moremode off")
				self.schedule.moremodebool = False

	def eval(self):
		self.ourhome.getsenseorhealth()
		madechange = False
		# Check to make sure we have at least a sensor
		if not self.ourhome.getinitialize():
			loggerdo.log.debug("burrow - sensors have not yet been initalized")
			# Try and start things up
			self.ourhome.initializesensor()
			loggerdo.log.debug("burrow - initializing sensors completed")

		# Run away mode check
		self.awaymode()
		# check if more mode is on/ready to turn off
		self.checkmoremode()
		# sync cal to check if current mode is right mode. Away is a "force" mode so it wont be overwritten until that changes
		self.schedule.synccalmode()

		# sync up states
		self.overallstate()

		# Move this to end
		# self.publishburrowmessage()

		base, schedhigh, schedlow = self.schedule.pullhourdetails(datetime.datetime.now())

		# Dont do any of this AC stuff if AC is not enabled.

		# check hvac
		self.hvac.run()

		# timercheck and updatetimer should let this run or not
		if self.timercheck() and self.getburrowstatus():
			# if all sensors down, make sure systems off an move on
			if self.ourhome.getweighthouseavg() is False:
				loggerdo.log.info("burrow - No sensors responding!!!")
				clock.sleep(1)
				loggerdo.log.info("burrow - Done waiting for sensors, restarting")
				# check for ac being on, shut down
				if self.ac is True:
					if self.acstate is True:
						madechange = self.hvac.ACoff()
						if madechange:
							self.AClastOff = datetime.datetime.now()
							self.acstate = False
				# check for heat being on, shut down
				elif self.heat is True:
					if self.heaterstate:
						madechange = self.hvac.HEAToff()
						if madechange:
							self.HEATlastOff = datetime.datetime.now()
							self.heaterstate = False

				# should look at fans?

				# dont run the test of this function
				self.publishburrowmessage()
				return False

			housetemp = self.ourhome.getweighthouseavg()
			loggerdo.log.debug("burrow - eval starting")
			loggerdo.log.debug("burrow - Current base temp is set to - {}".format(base))
			loggerdo.log.debug("burrow - Current low is set to - {}".format(schedlow))
			loggerdo.log.debug("burrow - Current high is set to - {}".format(schedhigh))
			loggerdo.log.debug("burrow - Current inside average is - {}".format(self.ourhome.getweighthouseavg()))
			loggerdo.log.debug("burrow - Mode is - {}".format(self.schedule.getmode()))


			if self.ac is True:
				loggerdo.log.debug("burrow - ac status is {}".format(self.acstate))

				if housetemp > schedhigh:
					if self.acstate is False:
						# Check FAN
						self.fanoffer()
						loggerdo.log.debug("burrow - Turn AC on")
						madechange = self.hvac.ACon()
						if madechange:
							self.AClastOn = datetime.datetime.now()
							self.acstate = True
					else:
						loggerdo.log.debug("burrow - AC is already on")

				elif housetemp <= schedlow:
					if self.acstate is True:
						loggerdo.log.debug("burrow - turn off the AC")
						madechange = self.hvac.ACoff()
						if madechange:
							self.AClastOff = datetime.datetime.now()
							self.acstate = False
					else:
						loggerdo.log.debug("burrow - AC is already off")
				else:
					loggerdo.log.debug("burrow - AC - No changes made - goldilocks")


			elif self.heat is True:
				# sync the heat to MQTT

				# heating mode flips the temp checks around
				loggerdo.log.debug("burrow - heater status is {}".format(self.heaterstate))

				if self.ourhome.getweighthouseavg() < schedlow:
					# dont have an outside check yet.
					if not self.heaterstate:
						# Check FAN
						self.fanoffer()
						loggerdo.log.debug("burrow - Should be turning heat on")
						madechange = self.hvac.HEATon()
						if madechange:
							self.HEATlastOn = datetime.datetime.now()
							self.heaterstate = True
					else:
						loggerdo.log.debug("burrow - Need heat, heat already on")

				elif self.ourhome.getweighthouseavg() >= schedhigh:
					# elif self.ourhome.gethightemp() >= schedhigh:
					if self.heaterstate:
						loggerdo.log.debug("burrow - Should be turning off")
						madechange = self.hvac.HEAToff()
						if madechange:
							self.HEATlastOff = datetime.datetime.now()
							self.heaterstate = False

					else:
						loggerdo.log.debug("burrow - Do not need heat, heat already off")
				else:
					loggerdo.log.debug("burrow - HEAT - No changes made - goldilocks")
			else:
				loggerdo.log.debug("burrow - Neither heat or AC are on")

		# loggerdo.log.debug("burrow - eval complete, sending mqtt overall state update for {} as as {}".format(self.mode, self.overallstate()))

		# fan runner here?
		self.fanrunner()
		# send updates
		self.publishburrowmessage()
		loggerdo.log.debug(f"burrow - fan is {self.fanstate}")
		loggerdo.log.debug(f"burrow - heat is {self.heaterstate}")
		loggerdo.log.debug(f"burrow - ac is {self.acstate}")
		loggerdo.log.debug("burrow - burrow is enabled T/F {}".format(self.getburrowstatus()))
		loggerdo.log.debug("burrow - timer is running (False = yes) {}".format(self.timercheck()))
		return madechange
