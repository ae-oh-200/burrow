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
	swingmode = "burrow/burrow/getswing"

	def __init__(self, mqttconfig, burrow, house, schedule, config):
		self.mqttc = mqtt.Client()
		self.mqttc.on_message = self.on_message
		self.burrow = burrow
		self.heatbump = config["heatbump"]
		self.acdrop = config["acdrop"]
		self.tempdur = config["tempdur"]
		self.house = house
		self.schedule = schedule
		self.mqttconfig = mqttconfig
		self.mqttc.connect(self.mqttconfig["mqttserver"], 1883, 60)
		self.mqttc.subscribe(maketopics(self.mqttconfig))
		#loggerdo.log.debug("mqttbroker - set up complete")

	def on_message(self, mqttc, obj, msg):
		device = msg.topic.split("/")
		msgsplit = msg.topic.split("/")

		#loggerdo.log.debug('MQTTlistener - Message in, string is {}'.format(device))

		if device[1] == "system" and device[2] == "target":
			#loggerdo.log.debug('MQTTlistener - system/target msg')
			self.tempmessage(msg.payload.decode("utf-8"), device[3])

		elif device[1] == "system" and device[2] == "set":
			#loggerdo.log.debug('MQTTlistener - system/set msg')
			self.systemsetmessage(message=msg.payload.decode("utf-8"))
		elif device[1] == "sensor":
			#loggerdo.log.debug('MQTTlistener-Sensor - Sensor - msg in')

			self.sensormessage(msgsplit=msgsplit, fulltopic=msg.topic, message=msg.payload.decode("utf-8"))
		elif device[1] == "burrow":
			#loggerdo.log.debug('MQTTlistener - burrow msg')
			self.burrowmessage(message=msg.payload.decode("utf-8"))
		else:
			print('no message in')


	def tempmessage(self, message, CorF):
		#incoming temp, doesnt actually do anything yet
		if CorF == "set":
			#loggerdo.log.debug("MQTTlistener - temp message is in C")
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
				#loggerdo.log.debug("MQTTlistener - tempmessage is not a number - {}".format(message))
				return
			#loggerdo.log.debug(
				#"MQTTlistener - Trying to adjust target temp to {} from mqttbroker".format(temp))
			loggerdo.log.info(
				"MQTT - request to update base temp for {} to {} for 1 hour".format(str(datetime.datetime.now()),
				                                                                    temp))
			self.schedule.updatebasetemp(datetime.datetime.now(), temp, duration=self.tempdur)

		elif CorF == "setlow":
			try:
				temp = float(message)
			except ValueError:
				#loggerdo.log.debug("MQTTlistener - tempmessage is not a number - {}".format(message))
				return
			#loggerdo.log.debug(
				#"MQTTlistener - Trying to adjust target low temp to {} from mqttbroker".format(temp))
			#loggerdo.log.info(
				#"MQTT - request to update low temp for {} to {} for 1 hour".format(str(datetime.datetime.now()),
				#                                                                    temp))
			self.schedule.updatelowtemp(datetime.datetime.now(), temp, duration=self.tempdur)

		elif CorF == "sethigh":
			try:
				temp = float(message)
			except ValueError:
				#loggerdo.log.debug("MQTTlistener - tempmessage is not a number - {}".format(message))
				return
			#loggerdo.log.debug(
				#"MQTTlistener - Trying to adjust target high temp to {} from mqttbroker".format(temp))
			#loggerdo.log.info(
				#"MQTT - request to update high temp for {} to {} for 1 hour".format(str(datetime.datetime.now()),
				#                                                                   temp))
			self.schedule.updatehightemp(datetime.datetime.now(), temp, duration=self.tempdur)



	def burrowmessage(self, message):
		#loggerdo.log.debug("MQTTlistener - burrowmessage - message for burrow is {}".format(message))

		if message == "Home":
			#loggerdo.log.debug("MQTTlistener - burrowmessage - Trying to set burrow to default (Home)")
			# if burrow is on and someone is home
			#if self.burrow.getburrowstatus() and self.burrow.anyonehome:
				# Burrow is already on and someone is home
				#loggerdo.log.debug("MQTTlistener - burrowmessage - do nothing burrow is on and someone home")
			if self.burrow.getburrowstatus() is False:
				#loggerdo.log.debug("MQTTlistener - burrowmessage - burrow was off, turning it on")
				self.burrow.burrowstatus(True)
			elif self.burrow.getburrowstatus() and self.burrow.anyonehome is False:
				loggerdo.log.info("MQTTlistener - burrowmessage - burrow is on but away is set. turning away off.")
				self.burrow.turnonawayoverride()
			else:
				loggerdo.log.info("MQTTlistener - burrowmessage - Burrow home message received but cant do anything")
			# Always disable moremode when changing back to home
			self.burrow.disablemoremode()
		elif message == "Out":
			loggerdo.log.info("MQTTlistener - burrowmessage - Trying to set burrow to away, this isnt setup")
		elif message == "More":
			loggerdo.log.debug("MQTTlistener - burrowmessage - turn More mode on")
			self.burrow.enabledmoremode()
		elif message == "Off":
			#loggerdo.log.debug("MQTTlistener - burrowmessage - Trying to turn burrow off (Off)")
			self.burrow.burrowstatus(False)
		elif message == "off":
			#loggerdo.log.debug("MQTTlistener - burrowmessage - Trying to turn burrow off (off)")
			self.burrow.burrowstatus(False)
		#else:
			#loggerdo.log.debug("MQTTlistener - burrowmessage - message in for burrow change is not known, - {}".format(message))
		publish.single(self.swingmode, payload="ready", hostname=self.mqttconfig["mqttserver"])

	def systemsetmessage(self, message):
		if message == "cool":

			if self.burrow.ac is True:
				#loggerdo.log.info("MQTTlistener - MQTT request, ac is off, turning ac on")
				btemp, schedhigh, schedlow = self.schedule.pullhourdetails(datetime.datetime.now())
				# drop temp with acdrop
				self.schedule.updatebasetemp(now=datetime.datetime.now(), temp=(btemp- self.acdrop), duration=self.tempdur)
				#loggerdo.log.debug("MQTTlistener - Running eval, triggered from mqttbroker - ac")
				# run eval
				self.burrow.eval()
				# rest for 5 for ac to turn on
				time.sleep(5)
				# if ac is not on yet, drop again by a degree
				if not self.burrow.acstate:
					loggerdo.log.debug("MQTTlistener - Running eval, triggered from mqttbroker - ac")
					self.schedule.updatebasetemp(now=datetime.datetime.now(), temp=(btemp- self.acdrop -1), duration=self.tempdur)
					self.burrow.eval()


		elif message == "heat":
			# check if heat is off, and heater is "mode"
			if self.burrow.heat is True:
				loggerdo.log.info("MQTTlistener - heat - heat message, turn heat on.")

				btemp, schedhigh, schedlow = self.schedule.pullhourdetails(datetime.datetime.now())

				while  self.house.getweighthouseavg() > schedlow:
					loggerdo.log.debug("MQTTlistener - heat - house weight is more than low")
					if self.burrow.heaterstate:
						loggerdo.log.debug("MQTTlistener - heat - heater is on. didnt do anything.")
					# if the base temp is the same, bump it up. Else raise all
					if schedlow == (btemp -1):
						self.schedule.updatebasetemp(now=datetime.datetime.now(), temp=(btemp + self.heatbump),
													 duration=self.tempdur)
						loggerdo.log.debug(f"MQTTlistener - heat - raise base temp to - {btemp + self.heatbump}")
					else:
						self.schedule.updatelowtemp(now=datetime.datetime.now(), lowtemp=schedlow+1, duration=self.tempdur)
						loggerdo.log.debug(f"MQTTlistener - heat - raise low temp to - {schedlow+1}")
					self.burrow.eval()
					time.sleep(2)
					#refresh data
					btemp, schedhigh, schedlow = self.schedule.pullhourdetails(datetime.datetime.now())
				loggerdo.log.debug("MQTTlistener - heat - out of the loop")



		elif message == "fan_only":
			#loggerdo.log.info("MQTTlistener - MQTT request to run on fan.")
			if self.burrow.acstate is False and self.burrow.heaterstate is False:
				self.burrow.turnonfantimer()
				#loggerdo.log.debug("MQTTlistener - MQTT request for fan on is complete.")
			#else:
				#loggerdo.log.debug("MQTTlistener - MQTT request for fan on did not complete. Some system (ac or heat) is already on")

		elif message == "off":
			loggerdo.log.info("MQTTlistener - MQTT request to turn whatever is on off.")
			if self.burrow.fanstate:
				#loggerdo.log.debug('MQTTlistener - Fan was on, turning it off.')
				self.burrow.fanoffer()

			elif self.burrow.heaterstate is True and self.burrow.heat is True:
				loggerdo.log.info('MQTTlistener - heat is on, turn heat off')
				base, schedhigh, schedlow = self.schedule.pullhourdetails(datetime.datetime.now())

				if self.house.getweighthouseavg() > schedlow:
					self.burrow.quickheaterchange(False)
					loggerdo.log.info("MQTTlistener - MQTT request to turn heat off complete.")
					#loggerdo.log.debug('MQTTlistener - dont just turn heat off, it will be turned backed on')
				else:
					loggerdo.log.info(
						f"MQTTlistener - MQTT request to turn heat off can not be complete, low temp {schedhigh}, current temp {self.house.getweighthouseavg()}.")
					#loggerdo.log.info("MQTTlistener - MQTT request to turn heat off complete.")
					loggerdo.log.info("MQTTlistener - MQTT request to turn heat off failed, it would just turn back on")
					#self.burrow.quickheaterchange(False)

			elif self.burrow.acstate is True and self.burrow.ac is True:
				loggerdo.log.info('MQTTlistener - AC is on, turn ac off')
				base, schedhigh, schedlow = self.schedule.pullhourdetails(datetime.datetime.now())
				#Make sure we wont just turn back on
				if self.house.getweighthouseavg()-1 < schedlow:
					loggerdo.log.info('MQTTlistener - move up base because house temp -1 is less than schedlow')
					self.schedule.updatebasetemp(now=datetime.datetime.now(), temp=base+2,
					                             duration=self.tempdur)

				#See if ac turns itself off
				self.burrow.eval()
				time.sleep(2)
				# turn off as long as it will stay off
				if self.burrow.acstate is True and self.burrow.ac is True and self.house.getweighthouseavg() < schedhigh:
					self.burrow.quickACchange(False)

				else:
					loggerdo.log.info(
						f"MQTTlistener - MQTT request to turn AC off can not be complete, high temp {schedhigh}, current temp {self.house.getweighthouseavg()}.")


	def sensormessage(self,msgsplit, fulltopic, message):
		device = msgsplit[2]
		try:
			msgval = float(message)
		except (ValueError, TypeError):
			loggerdo.log.info(f"MQTTlistener-Sensor - was not able to process for {device}, data - {message}")
			return False
		if msgsplit[3] == "c":
			msgsplit.pop(-1)
			loggerdo.log.debug("MQTTlistener-Sensor - {} is in celsius - ".format(device,msgval))
			ftemp = utils.truncate((msgval * 1.8) + 32, 2)
			self.house.udatesensortemp(device, ftemp)
			publish.single(f"{'/'.join(msgsplit)}/parsed-F", payload=str(ftemp), hostname=self.mqttconfig["mqttserver"], keepalive=60)
		elif msgsplit[3] == "f":
			msgsplit.pop(-1)
			loggerdo.log.debug("MQTTlistener-Sensor - {} is {} , in fahrenheit".format(device, msgval))
			self.house.udatesensortemp(device, msgval)
			publish.single(f"{'/'.join(msgsplit)}/parsed-F", payload=str(msgval), hostname=self.mqttconfig["mqttserver"])

		elif msgsplit[3] == "h":
			loggerdo.log.debug("MQTTlistener-Sensor - {} is {} , in humidity".format(device, msgval))
			self.house.udatesensorhumidity(device, msgval)

	def run(self):
		self.mqttc.loop_forever()
