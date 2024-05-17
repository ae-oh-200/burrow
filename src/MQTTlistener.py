from libraries import loggerdo
from libraries import utils
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import json
import datetime
import time

def checkmessage(messagestring):
	message = json.loads(messagestring)
	#loggerdo.log.debug("MQTTlistener - json after convert to dict {}".format(messagestring))
	# if there is a time key, update it to be a datetime object from string
	if 'time' in message:
		# if datetime is a epoch, convert it. otherwise it is a string.
		if isinstance(message["time"], int):
			message["time"] = datetime.datetime.fromtimestamp(message["time"])
		else:
			try:
				# Try time with micro seconds
				message["time"] = datetime.datetime.strptime(message["time"], "%m-%d-%Y, %H:%M:%S.%f")
			except ValueError:
				# fall back to time format without microseconds
				message["time"] = datetime.datetime.strptime(message["time"], "%m-%d-%Y, %H:%M:%S")
	return message


def maketopics(mqttconfig):
	listtopic = []
	for topic in mqttconfig["topiclist"]:
		listtopic.append((topic, 0))
		loggerdo.log.debug("MQTTlistener - Subscribe to {}".format(topic))
	return listtopic


class broker:
	mqttc = None
	house = None
	burrow = None
	schedule = None
	heatbump = None
	acdrop = None
	tempdur = None


	def __init__(self, burrow, house, schedule, config):
		self.mqttc = mqtt.Client()

		self.debug = config["debug"]["mqttlistener"]
		self.mqttc.on_message = self.on_message
		self.burrow = burrow

		self.quickchangeSwingTime = config["quickchangeSwingTime"]
		self.quickchangeSwing = config["quickchangeSwing"]
		
		self.house = house
		self.schedule = schedule

		self.mqttc.connect(config["MQTT"]["mqttserver"])
		self.mqttc.subscribe(maketopics(config["MQTT"]))
		#loggerdo.log.debug("mqttbroker - set up complete")

		# flip quickchange for cool
		if self.burrow.mode == "cool":
			self.quickchangeSwing = self.quickchangeSwing * -1


	def on_message(self, mqttc, obj, msg):
		device = msg.topic.split("/")
		msgsplit = msg.topic.split("/")

		if device[1] == "system" and device[2] == "target":
			self.TargetTempMessage(msg.payload.decode("utf-8"), device[3])
		elif device[1] == "system" and device[2] == "set":
			self.systemSetMessage(message=msg.payload.decode("utf-8"))
		elif device[1] == "sensor":
			pass
			loggerdo.log.debug('MQTTlistener-Sensor - Sensor - msg in (wrong)')
		elif device[1] == "burrow":
			self.burrowmessage(message=msg.payload.decode("utf-8"))
		else:
			loggerdo.log.debug('MQTTlistener - Message in, string is {}'.format(device))
			loggerdo.log.info('MQTTlistener-Sensor - msg in (wrong)')


	def TargetTempMessage(self, message, CorF):
		#incoming temp, doesnt actually do anything yet
		if CorF == "set":
			# Convert to F for no reason right now
			temp = utils.truncate((message * 1.8) + 32, 2)
		#elif CorF == "setf":
			#loggerdo.log.debug("MQTTlistener - temp message is in F")

		if CorF == "set" or CorF == "setf":
			if CorF == "set":
				#loggerdo.log.debug("MQTTlistener - temp message is in C")
				# Convert to F for no reason right now
				temp = utils.truncate((message * 1.8) + 32, 2)
			try:
				temp = float(message)
			except ValueError:
				loggerdo.log.info("MQTTlistener - tempmessage is not a good number - {}".format(message))
				return
			#loggerdo.log.debug(
				#"MQTTlistener - Trying to adjust target temp to {} from mqttbroker".format(temp))
			loggerdo.log.info(
				f"MQTT - request to update base temp to {temp} for {self.quickchangeSwingTime} hours")
			self.schedule.updatebasetemp(datetime.datetime.now(), temp, duration=self.quickchangeSwingTime)



	def burrowmessage(self, message):
		#loggerdo.log.debug("MQTTlistener - burrowmessage - message for burrow is {}".format(message))

		if message == "Home":
			#loggerdo.log.debug("MQTTlistener - burrowmessage - Trying to set burrow to default (Home)")
			# if burrow is on and someone is home
			#if self.burrow.getburrowstatus() and self.burrow.anyonehome:
				# Burrow is already on and someone is home
				#loggerdo.log.debug("MQTTlistener - burrowmessage - do nothing burrow is on and someone home")
			if self.burrow.getburrowstatus() is False:
				if self.debug:
					loggerdo.log.debug("MQTTlistener - burrowmessage - burrow was off, turning it on")
				self.burrow.burrowstatus(True)
			elif self.burrow.getburrowstatus() and self.burrow.anyonehome is False:
				if self.debug:
					loggerdo.log.info("MQTTlistener - burrowmessage - burrow is on but away is set. turning away off.")
				self.burrow.turnonawayoverride()
			else:
				if self.debug:
					loggerdo.log.info("MQTTlistener - burrowmessage - Burrow home message received but cant do anything")

		elif message == "Out":
			loggerdo.log.info("MQTTlistener - burrowmessage - Trying to set burrow to away, this isnt setup")

		elif message == "More":
			if self.debug:
				loggerdo.log.info("MQTTlistener - burrowmessage - turn More mode on")
			btemp, schedhigh, schedlow = self.schedule.pullhourdetails(datetime.datetime.now())
			self.schedule.updatebasetemp(now=datetime.datetime.now(), temp=(btemp + self.quickchangeSwing), duration=self.quickchangeSwingTime)

		elif message == "Off":
			if self.debug:
				loggerdo.log.info("MQTTlistener - burrowmessage - Trying to turn burrow off (Off)")
			self.burrow.burrowstatus(False)
		elif message == "off":
			if self.debug:
				loggerdo.log.info("MQTTlistener - burrowmessage - Trying to turn burrow off (off)")
			self.burrow.burrowstatus(False)

	def systemSetMessage(self, message):
		if message == "cool":

			if self.burrow.mode == "cool":
				loggerdo.log.info("MQTTlistener - MQTT request, ac is off, turning ac on")
				btemp, schedhigh, schedlow = self.schedule.pullhourdetails(datetime.datetime.now())
				# drop temp with acdrop
				while self.house.getweighthouseavg() > schedhigh: 
					self.schedule.updatebasetemp(now=datetime.datetime.now(), temp=(btemp- 1), duration=self.quickchangeSwingTime)
					btemp, schedhigh, schedlow = self.schedule.pullhourdetails(datetime.datetime.now())
				if self.debug:
					loggerdo.log.info(f"MQTTlistener - new base temp is {btemp}")
	

		elif message == "heat":
			# check if heat is off, and heater is "mode"
			if self.burrow.mode == "heat":
				loggerdo.log.info("MQTTlistener - heat - heat message, turn heat on.")
				if self.burrow.heaterstate:
						loggerdo.log.info("MQTTlistener - heat - heater is on. didnt do anything.")
						return
				btemp, schedhigh, schedlow = self.schedule.pullhourdetails(datetime.datetime.now())

				while self.house.getweighthouseavg() >= schedlow:
					self.schedule.updatebasetemp(now=datetime.datetime.now(), temp=(btemp + 1), duration=self.quickchangeSwingTime)
					btemp, schedhigh, schedlow = self.schedule.pullhourdetails(datetime.datetime.now())
					if self.debug:
						loggerdo.log.info(f"MQTTlistener - new base temp is {btemp}")

		elif message == "fan_only":
			loggerdo.log.info("MQTTlistener - MQTT request to run on fan.")
			if self.burrow.acstate is False and self.burrow.heaterstate is False:
				self.burrow.tunOnFan()

		elif message == "off":
			loggerdo.log.info("MQTTlistener - MQTT request to turn whatever is on off.")
			if self.burrow.fanstate:
				if self.debug:
					loggerdo.log.info('MQTTlistener - Fan was on, turning it off.')
				self.burrow.fanoffer()
		
			# check for heat and needs to be off
			elif self.burrow.heaterstate is True and self.burrow.mode == "heat":
				if self.debug:
					loggerdo.log.info('MQTTlistener - heat is on, turn heat off')
				base, schedhigh, schedlow = self.schedule.pullhourdetails(datetime.datetime.now())
				# make sure that it doesnt turn back on right away

				while self.house.getweighthouseavg() > schedhigh:
					self.schedule.updatebasetemp(now=datetime.datetime.now(), temp=base-1,
					                             duration=self.quickchangeSwingTime)
					base, schedhigh, schedlow = self.schedule.pullhourdetails(datetime.datetime.now())

				self.burrow.quickheaterchange(False)
				if self.debug:
					loggerdo.log.info("MQTTlistener - MQTT request to turn heat off complete.")

			#check if ac is and needs to be off
			elif self.burrow.acstate is True and self.burrow.mode == "cool":
				if self.debug:
					loggerdo.log.info('MQTTlistener - AC is on, turn ac off')

				base, schedhigh, schedlow = self.schedule.pullhourdetails(datetime.datetime.now())

				# First need to make sure we wont just turn back on
				while self.house.getweighthouseavg() < schedlow:
					self.schedule.updatebasetemp(now=datetime.datetime.now(), temp=base+1,
					                             duration=self.quickchangeSwingTime)
					base, schedhigh, schedlow = self.schedule.pullhourdetails(datetime.datetime.now())

				self.burrow.quickACchange(False)
				if self.debug:
					loggerdo.log.info("MQTTlistener - MQTT request to turn ac off complete.")
			else:
				loggerdo.log.debug("MQTTlistener - MQTT request to turn something off, but nothing to do.")


		else:
			loggerdo.log.info(f"MQTTlistener - WERID MESSAGE, {message}")

			#See if ac turns itse


	def run(self):
		self.mqttc.loop_forever()
