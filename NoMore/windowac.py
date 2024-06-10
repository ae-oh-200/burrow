import WemoTalk
from libraries import loggerdo
from libraries import mongo
import datetime
import time

class acunit():
	zone = None
	managed = None
	ip = None
	state = None
	wemo = None
	timer = None
	wemofailure = None
	online = None
	name = None
	mqtttalker=None

	def __init__(self, mydb, zone, managed, ip, name, mqtttalker):
		self.mydb = mydb
		self.zone = zone
		self.managed = managed
		self.ip = ip
		self.wemo = WemoTalk.wemo(self.ip)
		self.timer = datetime.datetime.now() - datetime.timedelta(minutes=5)
		self.name = name
		self.state == None
		self.mqtttalker = mqtttalker

		self.wemofailure = 0
		if self.managed:
			# need to pull state to start
			loopcount = 0
			while self.state == None:
				self.checkstate()
				if self.state is not None:
					#skip the sleep to speed up
					break
				time.sleep(10)
				loopcount +=1
				if loopcount > 10:
					loggerdo.log.debug("windowac - {} was not setup correctly".format(self.name))
					raise SystemExit("error reaching out to AC {} - {}, unable to complete startup".format(self.zone, self.ip))
			loggerdo.log.debug("windowac - {} was setup correctly".format(self.name))
			loggerdo.log.debug("windowac - is set to {}".format(self.state))
			self.online = True
		else:
			loggerdo.log.debug("windowac - {} was setup as not managed".format(self.name))
			self.online = False

	def checkstate(self):
		laststate = self.state
		state = self.wemo.status()

		if state == "1":
			self.wemofailure = 0
			self.state = True
			if laststate is None:
				loggerdo.log.debug("windowac - first run for {} it was already On".format(self.name))
				mongo.logacrecord(self.mydb, zone=self.zone, state='on')
				self.mqtttalker.publishaczone(zone = self.zone, zonename=self.name, state=True)

			elif laststate != self.state:
				loggerdo.log.debug("windowac - {} was updated but not by burrow - change to On".format(self.name))
				self.timer = datetime.datetime.now() + datetime.timedelta(minutes=15)
				loggerdo.log.debug("windowac - starting timer for {}, set to {}".format(self.name, self.timer))
				mongo.logacrecord(self.mydb, zone=self.zone, state='on')
				self.mqtttalker.publishaczone(zone=self.zone, zonename=self.name, state=True)

		elif state == "0":
			self.wemofailure = 0
			self.state = False
			if laststate is None:
				loggerdo.log.debug("windowac - first run for {} it was already Off".format(self.name))
				mongo.logacrecord(self.mydb, zone=self.zone, state='off')
				self.mqtttalker.publishaczone(zone=self.zone, zonename=self.name, state=False)

			elif laststate != self.state:
				loggerdo.log.debug("windowac - {} was updated but not by burrow - change to Off".format(self.name))
				mongo.logacrecord(self.mydb, zone=self.zone, state='off')
				self.mqtttalker.publishaczone(zone=self.zone, zonename=self.name, state=False)

		elif state is None:
			self.wemofailure = +1
			loggerdo.log.debug("windowac - {} update failed. Count = {}".format(self.name, self.wemofailure))

	def off(self, force=False):
		# force is new and needs testing
		if datetime.datetime.now() > self.timer or force:
			loggerdo.log.info("windowac - Power AC off for zone {}. Force is {}".format(self.zone,force))
			if self.timer > datetime.datetime.now():
				loggerdo.log.debug("windowac - time prevented AC on for {}".format(self.name))
				return False
			self.wemo.off()
			time.sleep(3)
			self.checkstate()
			if not self.state:

				mongo.logacrecord(self.mydb, zone=self.zone, state='off')
				self.mqtttalker.publishaczone(zone=self.zone, zonename=self.name, state=False)
				self.timer = datetime.datetime.now() + datetime.timedelta(minutes=10)
				loggerdo.log.debug("windowac - starting timer for {}, set to {}".format(self.name, self.timer))
				return True
			else:
				loggerdo.log.debug("windowac - failed to turn off ac for zone {}".format(self.zone))
				return False
		else:
			loggerdo.log.info("windowac - Wemo Timer delay prevented off for ac in zone {}".format(self.zone))
			loggerdo.log.info("windowac - Wemo Timer is set for {}".format(self.timer))


	def on(self, force=False):
		if datetime.datetime.now() > self.timer or force:
			loggerdo.log.info("windowac - Power AC on for zone {}. Force is {}".format(self.zone, force))
			if self.timer > datetime.datetime.now():
				loggerdo.log.debug("windowac - time prevented AC on for {}".format(self.name))
				return False
			self.wemo.on()
			time.sleep(3)
			self.checkstate()

			if self.state:
				mongo.logacrecord(self.mydb, zone = self.zone, state='on')
				self.mqtttalker.publishaczone(zone=self.zone, zonename=self.name, state=True)
				self.timer = datetime.datetime.now() + datetime.timedelta(minutes=10)
				loggerdo.log.debug("windowac - starting timer for {}, set to {}".format(self.name, self.timer))
				return True
			else:
				loggerdo.log.debug("windowac - failed to turn on ac for zone {}".format(self.zone))
				return False
		else:
			loggerdo.log.info("windowac - Wemo Timer delay prevented on for ac in zone {}".format(self.zone))
			loggerdo.log.info("windowac - Wemo Timer is set for {}".format(self.timer))


	def ismanaged(self):
		return self.managed

	def getzone(self):
		return self.zone

	def getstate(self):
		return self.state

	def getnewstate(self):
		if self.managed:
			self.checkstate()
			self.mqtttalker.publishaczone(zone=self.zone, zonename=self.name, state=self.state)
		return self.state

