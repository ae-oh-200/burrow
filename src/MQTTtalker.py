from libraries import utils
from libraries import loggerdo
import paho.mqtt.publish as publish
import json
import datetime
import time


class broker:
	host = None
	topic_targettemp = None
	topic_currenttempf = None
	topic_currenttempc = None
	topic_humidity = None
	topic_heater = None
	topic_burrow = None
	topic_systemhb = None

	def __init__(self, config):
		self.host = config["MQTT"]["mqttserver"]
		self.debug = config["debug"]["mqtttalker"]
		self.topic_targettemp = 'burrow/system/target/get'
		self.topic_targettemphigh = 'burrow/system/target/high'
		self.topic_targettemplow = 'burrow/system/target/low'

		self.topic_currenttempf = 'burrow/temperature/f'
		self.topic_currenttempc = 'burrow/temperature/c'
		self.topic_humidity = 'burrow/humidity'

		self.topic_burrow = 'burrow/burrow/get'
		self.topic_systemhb = 'burrow/system/get'
		self.topic_zoneroot = 'burrow/zones'
		self.topic_burrow_mode = 'burrow/burrow/mode'
		self.topic_day = 'burrow/burrow/day'
		self.topic_burrow_away = 'burrow/system/away/get'
		self.topic_timer_state = 'burrow/burrow/timer/state'
		self.topic_moremode = 'burrow/burrow/moremodestate'
		self.topic_anyonehome = 'burrow/burrow/anyonehomestate'

	def publishtemph(self, tempf, humidity):
		# keeping it simple and backwards compatible
		loggerdo.log.debug("MQTTtalker - Publish t/h {}/{}".format(tempf, humidity))
		self.publishtemperaturec(tempf)
		self.publishhumidity(humidity)

	def publishtemperaturec(self, tempf):
		#send F first
		self.publishtemperaturef(tempf)
		# convert back to celsius
		tempc = utils.truncate((tempf-32) * 5/9,2)
		jsonmsg = json.dumps({"temp": tempc, "time": datetime.datetime.now().strftime("%m-%d-%Y, %H:%M:%S")})
		try:
			publish.single(self.topic_currenttempc, payload=jsonmsg, hostname=self.host, keepalive=60)
		except Exception as e:
			loggerdo.log.info("MQTTtalker - publishtemperaturec - error - ", e)

	def publishtemperaturef(self, tempf):
		# convert back to celsius
		jsonmsg = json.dumps({"temp": tempf, "time": datetime.datetime.now().strftime("%m-%d-%Y, %H:%M:%S")})
		try:
			publish.single(self.topic_currenttempf, payload=tempf, hostname=self.host, keepalive=60)
		except Exception as e:
			loggerdo.log.info("MQTTtalker - publishtemperaturef - error - ", e)

	def publishhumidity(self, humidity):
		# publish humidity
		jsonmsg = json.dumps({"humidity": humidity, "time": datetime.datetime.now().strftime("%m-%d-%Y, %H:%M:%S")})
		try:
			publish.single(self.topic_humidity, payload=humidity, hostname=self.host, keepalive=60)
		except Exception as e:
			loggerdo.log.info("MQTTtalker - publishhumidity - error - ", e)

	def publishtarget(self, tempf):
		# publish the current temp in celsius
		tempc = utils.truncate((tempf - 32) * 5 / 9, 2)
		loggerdo.log.debug("MQTTtalker - publish target temperature in celsius {}".format(tempc))
		jsonmsg = json.dumps({"temp": tempc, "tempf": tempf, "time": datetime.datetime.now().strftime("%m-%d-%Y, %H:%M:%S")})
		try:
			publish.single(self.topic_targettemp, payload=tempf, hostname=self.host, keepalive=60)
		except Exception as e:
			loggerdo.log.info("MQTTtalker - publishtarget - error - ", e)

	def publishhighlow(self, high, low):
		# publish the current temp in celsius
		try:
			publish.single(self.topic_targettemplow, payload=low, hostname=self.host, keepalive=60)
			publish.single(self.topic_targettemphigh, payload=high, hostname=self.host, keepalive=60)
		except Exception as e:
			loggerdo.log.info("MQTTtalker - publishhighlow - error - ", e)

	def publishburrow(self, state):
		loggerdo.log.debug("MQTTtalker - update burrow, set to {}".format(state))
		#jsonmsg = json.dumps({"state": state, "time": datetime.datetime.now().strftime("%m-%d-%Y, %H:%M:%S")})
		#publish.single(self.topic_burrow, payload=jsonmsg, retain=True, hostname=self.host, keepalive=60)
		try:
			publish.single(self.topic_burrow, payload=state, hostname=self.host, keepalive=60)
		except Exception as e:
			loggerdo.log.info("MQTTtalker - publishburrow - error - ", e)


	def publishaczone(self, zone, zonename, state):
		loggerdo.log.debug("MQTTtalker - sending zone update for {} with {}".format(zonename, state))
		jsonmsg = json.dumps(
			{"zone": zonename, "state": state, "time": datetime.datetime.now().strftime("%m-%d-%Y, %H:%M:%S")})
		topic = self.topic_zoneroot + '/' + str(zone)
		try:
			publish.single(topic, payload=jsonmsg, hostname=self.host, keepalive=60)
		except Exception as e:
			loggerdo.log.info("MQTTtalker - publishaczone - error - ", e)

	def publishsystem(self, system, status):
		# this was when I inteded to allow the home app to switch from heat -> ac -> to off
		try:
			if system == "heat" and status:
				loggerdo.log.debug("MQTTtalker - Publish heat on homebridge mqttthing")
				publish.single(self.topic_systemhb, payload="heat", hostname=self.host, keepalive=60)
			elif system == "heat" and not status:
				loggerdo.log.debug("MQTTtalker - Publish off to homebridge mqttthing")
				publish.single(self.topic_systemhb, payload="auto", hostname=self.host, keepalive=60)
			elif system == "ac" and status:
				loggerdo.log.debug("MQTTtalker - Publish ac on to homebridge mqttthing")
				publish.single(self.topic_systemhb, payload="cool", hostname=self.host, keepalive=60)
			elif system == "ac" and status is False:
				loggerdo.log.debug("MQTTtalker - Publish off to homebridge mqttthing")
				publish.single(self.topic_systemhb, payload="auto", hostname=self.host, keepalive=60)
			elif system == "fan" and status:
				loggerdo.log.debug("MQTTtalker - Publish fan to homebridge mqttthing")
				publish.single(self.topic_systemhb, payload="fan_only", hostname=self.host, keepalive=60)
			elif system == "fan" and status is False:
				loggerdo.log.debug("MQTTtalker - Publish fan auto to homebridge mqttthing")
				publish.single(self.topic_systemhb, payload="auto", hostname=self.host, keepalive=60)
			elif system == "off":
				loggerdo.log.debug("MQTTtalker - Publish off to homebridge mqttthing")
				publish.single(self.topic_systemhb, payload="off", hostname=self.host, keepalive=60)
		except Exception as e:
			loggerdo.log.info("MQTTtalker - publishsystem - error - ", e)

	def publishmode(self, mode):
		loggerdo.log.debug("MQTTtalker - sending mode update, {}".format(mode))
		try:
			publish.single(self.topic_burrow_mode, payload=mode, hostname=self.host, keepalive=60)
		except Exception as e:
			loggerdo.log.info("MQTTtalker - publishmode - error - ", e)

	def publishday(self, day):
		loggerdo.log.debug("MQTTtalker - sending day update, {}".format(day))
		try:
			publish.single(self.topic_day, payload=str(day), hostname=self.host, keepalive=60)
		except Exception as e:
			loggerdo.log.info("MQTTtalker - publishday - error - ", e)


	def publishaway(self, anyonehome):
		try:
			publish.single(self.topic_anyonehome, payload=str(anyonehome), hostname=self.host, keepalive=60)
		except Exception as e:
			loggerdo.log.info("MQTTtalker - publishtemperaturec - error - ", e)

