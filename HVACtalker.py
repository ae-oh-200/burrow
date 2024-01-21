import time
import paho.mqtt.publish as publish
#import paho.mqtt.subscribe as subscribe
from libraries import loggerdo
import datetime
import paho.mqtt.client as mqtt


COOLset = 'burrow/HVAC/COOL/set'
HEATset = 'burrow/HVAC/HEAT/set'
FANset = 'burrow/HVAC/FAN/set'

class hvactalk():

	hvacbroker = None
	syncerr = 0

	def __init__(self, emalert):
		self.hvacbroker = broker()
		self.ac = False
		self.heat = False
		self.fan = False
		self.host = '192.168.5.70'
		self.emalert = emalert
		self.syncerr = 0
		# Run start
		self.start()

	def sendalert(self, system, message):
		loggerdo.log.debug("HVACtalker - sending alert for - {}".format(system))
		subject = "{} threw an error".format(system)
		message = "{}\n current time is {}, we will keep trying".format(message, datetime.datetime.now())
		self.emalert.shout(subject, message)


	def ACon(self):
		loggerdo.log.debug("hvactalk - Turning AC on, waiting for reply")
		publish.single(COOLset, payload=str(True), hostname=self.host, keepalive=60)

		# check to see if response has come back yet.
		for counter in range(10):
			if self.hvacbroker.ac is True:
				self.ac = True
				loggerdo.log.info("hvactalk - reply for ac on, returning true")
				return True
			else:
				time.sleep(15)

		self.sendalert(system='ACon', message='HVACtalker - unable to turn AC on after 10 tries')
		loggerdo.log.info("hvactalk - did not receive reply for ac on, not updating. return False")

		return False

	def ACoff(self):

		loggerdo.log.debug("hvactalk - Turning AC off, waiting for reply")
		publish.single(COOLset, payload=str(False), hostname=self.host, keepalive=60)
		for counter in range(10):
			if self.hvacbroker.ac is False:
				self.ac = False
				loggerdo.log.info("hvactalk - reply for ac off, returning true")
				return True
			else:
				time.sleep(15)
		self.sendalert(system='ACoff', message='HVACtalker - unable to turn AC off after 10 tries')
		loggerdo.log.info("hvactalk - did not receive reply for ac off, not updating")
		return False

	def FANon(self):
		loggerdo.log.debug("hvactalk - Turning FAN on, waiting for reply")
		publish.single(FANset, payload=str(True), hostname=self.host, keepalive=60)
		# check to see if response has come back yet.
		for counter in range(10):
			if self.hvacbroker.fan is True:
				self.fan = True
				loggerdo.log.info("hvactalk - reply for fan on, returning true")
				return True
			else:
				time.sleep(15)
		self.sendalert(system='FANon', message='HVACtalker - unable to turn FAN on after 10 tries')
		loggerdo.log.info("hvactalk - did not receive reply for fan on, not updating. return False")

		return False

	def FANoff(self):
		loggerdo.log.debug("hvactalk - Turning FAN off, waiting for reply")
		publish.single(FANset, payload=str(False), hostname=self.host, keepalive=60)
		for counter in range(10):
			if self.hvacbroker.fan is False:
				self.fan = False
				loggerdo.log.info("hvactalk - reply for fan off, returning true")
				return True
			else:
				time.sleep(15)
		self.sendalert(system='FANoff', message='HVACtalker - unable to turn FAN off after 10 tries')
		loggerdo.log.info("hvactalk - did not receive reply for ac off, not updating")
		return False

	def HEATon(self):
		loggerdo.log.debug("hvactalk - Turning HEAT on, waiting for reply")
		publish.single(HEATset, payload=str(True), hostname=self.host, keepalive=60)
		for counter in range(10):
			if self.hvacbroker.heat is True:
				self.heat = True
				loggerdo.log.info(f"hvactalk - reply for heat on, returning true. count - {counter}")
				return True
			else:
				time.sleep(15)
		self.sendalert(system='HEATon', message='HVACtalker - unable to turn HEAT on after 10 tries')
		loggerdo.log.info("hvactalk - did not receive reply for heat off, not updating")
		return False

	def HEAToff(self):
		loggerdo.log.debug("hvactalk - Turning HEAT off, waiting for reply")
		publish.single(HEATset, payload=str(False), hostname=self.host, keepalive=60)
		for counter in range(10):
			if self.hvacbroker.heat is False:
				self.heat = False
				loggerdo.log.info(f"hvactalk - reply for heat off, returning true. count - {counter}")
				return True
			else:
				time.sleep(15)
		self.sendalert(system='HEAToff', message='HVACtalker - unable to turn HEAT off after 10 tries')
		loggerdo.log.info("hvactalk - did not receive reply for heat off, not updating")
		return False


	def start(self):
		# Start by makeing sure everything is off.
		publish.single(HEATset, payload=str(False), hostname=self.host, keepalive=60)
		publish.single(COOLset, payload=str(False), hostname=self.host, keepalive=60)
		publish.single(FANset, payload=str(False),  hostname=self.host, keepalive=60)
		return True


	def run(self):

		#do maintenance stuff

		# check to see if a sync has happened in last 10 minutes
		if self.hvacbroker.lastsync  < datetime.datetime.now() - datetime.timedelta(minutes=5):
			self.syncerr +=1
			loggerdo.log.debug("hvactalk - lastsync shouldnt be more than 5 minutes old, HVAC talk fail")
			if (self.syncerr% 100) == 0:
				self.sendalert(system='hvacsync', message='HVACtalker - unable to sync HVAC, err = {}. last sync {}'.format(self.syncerr, self.hvacbroker.lastsync))
			elif self.syncerr == 1000:
				#sync err at 1000, make sure we shut it down if its listening
				self.start()
		else:
			# reset syncerr
			if self.syncerr > 1:
				self.sendalert(system='hvacsync',
				               message='HVACtalker - sync HVAC error cleared, count was = {}'.format(self.syncerr))
			self.syncerr = 0

		if self.hvacbroker.ac != self.ac:
			loggerdo.log.debug("hvactalk - ac out of sync with mqtt")
			loggerdo.log.debug("hvactalk - setting ac to {}".format(self.hvacbroker.ac))
			self.ac = self.hvacbroker.ac

		if self.hvacbroker.heat != self.heat:
			loggerdo.log.debug("hvactalk - heat out of sync with mqtt")
			loggerdo.log.debug("hvactalk - setting heat to {}".format(self.hvacbroker.heat))
			self.heat = self.hvacbroker.heat


		if self.hvacbroker.fan != self.fan:
			loggerdo.log.debug("hvactalk - fan out of sync with mqtt")
			loggerdo.log.debug("hvactalk - setting fan to {}".format(self.hvacbroker.fan))
			self.fan = self.hvacbroker.fan


class broker:


	mqttc = None
	mqttconnected = False
	mqttserver = None
	topicarray = []
	topiclist = {}
	messageflag = None
	ac = None
	heat = None
	fan = None

	lastsync = None

	def __init__(self):

		self.ac = False
		self.heat = False
		self.fan = False
		self.lastsync = datetime.datetime.now() - datetime.timedelta(minutes=1)

		self.SetupTopicArray()

		self.mqttc = mqtt.Client()
		self.mqttserver = '192.168.5.70'

		self.mqttc.on_message = self.on_message
		self.mqttc.on_connect = self.on_connect
		self.mqttc.on_disconnect = self.on_disconnect

		self.mqttc.connect(self.mqttserver)

		self.mqttc.loop_start()


	def on_connect(self, mqttc, obj, flags, rc):

		loggerdo.log.debug("hvactalk - mqtt connected")

		loggerdo.log.info("Connected with result code " + str(rc))
		loggerdo.log.debug("Connected to %s:%s" % (mqttc._host, mqttc._port))

		# Pause for 30 seconds to prevent immediate reconnect
		time.sleep(3)
		self.mqttc.subscribe(self.topicarray)
		self.mqttconnected = True
		loggerdo.log.debug("hvactalk - MQTT - connect done")


	def on_message(self, mqttc, obj, msg):
		msgsplit = msg.topic.split("/")
		message = msg.payload.decode("utf-8")
		if message == "True":
			message = True
		elif message == "False":
			message = False

		if msgsplit[1] == "HVAC":
			if msgsplit[2] == "COOL" and msgsplit[3] == "get":
				# check to see if message has an updated for us or just syncing
				if message != self.ac:
					loggerdo.log.debug("hvactalk - MQTT - AC message in")
					if message is True:
						loggerdo.log.debug("hvactalk - mqtt - AC ON message")
						self.messageflag = True
						self.ac = True

					elif message is False:
						loggerdo.log.debug("hvactalk - mqtt - AC off message")
						self.messageflag = True
						self.ac = False

			elif msgsplit[2] == "HEAT" and msgsplit[3] == "get":

				if message != self.heat:
					loggerdo.log.debug("hvactalk - MQTT - HEAT message in")
					if message is True:
						loggerdo.log.debug("hvactalk - mqtt - HEAT ON message")
						self.messageflag = True
						self.heat = True

					elif message is False:
						loggerdo.log.debug("hvactalk - mqtt - HEAT off message")
						self.messageflag = True
						self.heat = False

			if msgsplit[2] == "FAN" and msgsplit[3] == "get":
				if message != self.fan:
					loggerdo.log.debug("hvactalk - MQTT - FAN message in")
					if message is True:
						loggerdo.log.debug("hvactalk - mqtt - FAN ON message")
						self.messageflag = True
						self.fan = True

					elif message is False:
						loggerdo.log.debug("hvactalk - mqtt - FAN off message")
						self.messageflag = True
						self.fan = False

			elif msgsplit[2] == "sync":
				# convert msg to datetime
				try:
					self.lastsync = datetime.datetime.strptime(message, '%Y-%m-%d %H:%M:%S.%f')
					loggerdo.log.debug(f"hvactalk - mqtt - update lastsync to {self.lastsync} off a message")
				except:
					loggerdo.log.debug('hvactalk - could not convert sync msg to datetime')
					print('could not convert sync msg to datetime')


	def on_disconnect(self, mqttc, obj, rc):
		loggerdo.log.debug("hvactalk - MQTT - disconnected")
		self.mqttconnected = False

		if rc != 0:
			loggerdo.log.debug("hvactalk - MQTT - Unexpected disconnection.")

		while not self.mqttconnected:
			try:
				self.mqttc.reconnect()
			except ConnectionRefusedError:
				loggerdo.log.debug("hvactalk - MQTT - Unable to reconnect, Connection Refused")
				time.sleep(30)
			except OSError as e:
				loggerdo.log.debug('OS Error, {}'.format(str(e)))
				time.sleep(30)
			else:
				loggerdo.log.debug("hvactalk - MQTT - Reconnected.")
				time.sleep(30)





	def SetupTopicArray(self):
		# subscribe to these to get updtes
		self.topiclist.update({'COOLset': 'burrow/HVAC/COOL/get'})
		self.topiclist.update({'HEATset': 'burrow/HVAC/HEAT/get'})
		self.topiclist.update({'FANset': 'burrow/HVAC/FAN/get'})
		self.topiclist.update({'sync': 'burrow/HVAC/sync'})
		#self.topiclist.update({'drop': 'burrow/HVAC/dropped'})

		for topic in self.topiclist:
			self.topicarray.append((self.topiclist[topic], 0))

	def run(self):
		self.mqttc.loop_forever()


