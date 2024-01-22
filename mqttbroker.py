
#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2010-2013 Roger Light <roger@atchoo.org>
#
# All rights reserved. This program and the accompanying materials
# are made available under the terms of the Eclipse Distribution License v1.0
# which accompanies this distribution.
#
# The Eclipse Distribution License is available at
#   http://www.eclipse.org/org/documents/edl-v10.php.
#
# Contributors:
#    Roger Light - initial implementation
# Copyright (c) 2010,2011 Roger Light <roger@atchoo.org>
# All rights reserved.

# This shows a simple example of an MQTT subscriber.

import paho  # Ensures paho is in PYTHONPATH
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import yaml, json, datetime
from os import path
from libraries import loggerdo, utils



def loadconfig(configfile):
	with open(configfile, 'r') as file:
		config = yaml.load(file, Loader=yaml.FullLoader)
	return config


def checkmessage(messagestring):
	message = json.loads(messagestring)
	loggerdo.log.debug("json after convert to dict {}".format(messagestring))
	#if there is a time key, update it to be a datetime object from string
	if 'time' in message:
		message["time"] = datetime.datetime.strptime(message["time"], "%m-%d-%Y, %H:%M:%S")
	return message


class broker():
	mqttc = None
	house = None
	burrow = None
	schedule = None
	tbump = None
	heatbump = None

	def __init__(self, mqttconfig, house, burrow, schedule, heatbump):
		self.mqttc = mqtt.Client()
		self.house = house
		self.burrow = burrow
		self.schedule = schedule
		self.mqttc.on_message = self.on_message
		#self.mqttc.on_connect = self.on_connect
		self.mqttc.on_publish = self.on_publish
		#self.mqttc.on_subscribe = self.on_subscribe
		self.heatbump = heatbump


		self.mqttc.connect(mqttconfig["mqttserver"], 1883, 60)
		topics = self.gettopics(mqttconfig)


		#this would subscribe to all with qos of 0
		self.mqttc.subscribe(topics)

		loggerdo.log.debug("mqttbroker - set up complete")

	def gettopics(self, mqttconfig ):
		listtopic = []
		for topic in mqttconfig["topics"]:
			topics = ("{}/{}".format(mqttconfig["topicroot"], topic), 0)
			listtopic.append(topics)
		loggerdo.log.debug("mqttbroker - I want to subscribe to {}".format(listtopic))
		return listtopic




	def on_publish(self, mqttc, obj, mid):
		print("on publish")
		#print("mid: " + str(mid))
		pass

	def on_connect(self,mqttc, obj, flags, rc):
		print("rc: " + str(rc))

	def on_subscribe(self, mqttc, obj, mid, granted_qos):
		loggerdo.log.debug("mqttbroker - Subscribed: " + str(mid) + " " + str(granted_qos))


	def on_message(self, mqttc, obj, msg):
		device = msg.topic.split("/")

		if device[1] == "system":
			self.systemmessagein(device[2], msg.payload.decode("utf-8"))
		elif device[1] == "sensor":
			self.sensormessagein(device[2],  msg.payload.decode("utf-8"))
		elif device[1] == "test":
			loggerdo.log.debug("mqttbroker - test message found in mqtt, {}".format(msg.payload.decode("utf-8")))
		else:
			loggerdo.log.debug("mqttbroker - message string not understood {}".format(msg.topic))


	def systemmessagein(self, device, message):
		message = checkmessage(message)

		#response to a message from heater with status update, sends update over to Burrow which processe it.
		if device == "heater":
			loggerdo.log.debug("mqttbroker - message for heater is {}".format(message))
			if self.burrow.getheaterlastupdate() == None:
				loggerdo.log.debug("mqttbroker - Update heater state to {}, because it was set to None".format(message["state"]))
				self.burrow.firstheaterstatus(message["state"])

			elif message["time"] > self.burrow.getheaterlastupdate():
				loggerdo.log.debug("mqttbroker - Update heater state to {}, because message has newer time".format(message["state"]))
				self.burrow.setheaterstatus(message["state"])
			else:
				loggerdo.log.debug("mqttbroker - Not doing anything with system message, timing off. Time for last update {}, time in {}".format(self.burrow.getheaterlastupdate(),message["time"]))

		elif device == "burrow":
			loggerdo.log.debug("mqttbroker - message for burrow is {}".format(message))
			if message["system"] == "HEAT":
				loggerdo.log.debug("mqttbroker - try to turn on heat")
				if self.burrow.getmode() == "heat":
					loggerdo.log.debug("mqttbroker - burrow is in heat mode")
					if not self.burrow.getheatstatus():
						loggerdo.log.info("mqttbroker - MQTT request, heat is off, turning heat on")
						#self.burrow.heaton(force=True)

						btemp, schedhigh, schedlow = self.schedule.pullhourdetails(datetime.datetime.now())

						loggerdo.log.debug("mqttbroker - Bump base temp from {}, to {}".format(btemp, self.heatbump))
						self.schedule.updatebasetemp(now= datetime.datetime.now(), temp=self.heatbump, duration = 1)
						loggerdo.log.debug("mqttbroker - Running eval, triggered from mqttbroker")
						self.burrow.eval()

					else:
						loggerdo.log.debug("mqttbroker - Heat is already on. - mqttbroker")

			 #Not using AC stuff right now.
			elif message["system"] == "AC":
				print("Turn on AC")

			elif message["system"] == "OFF":
				loggerdo.log.debug("mqttbroker - Turn system off")

				#are we in heat mode
				if self.burrow.getmode() == "heat":
					#check to see if the heat is on.
					if self.burrow.getheatstatus():
						loggerdo.log.info("mqttbroker - MQTT request, heat is on, turning heat off")
						self.burrow.heatoff(force=True)
						#Timer to make sure heat stays off for a bit
						loggerdo.log.debug("mqttbroker - Setting burrow timer for 10 minutes")
						self.burrow.starttimer(10)

		elif device == "target":
			#change back to f
			message["temp"] = utils.truncate((message["temp"] * 1.8)+32,2)

			loggerdo.log.debug("mqttbroker - Trying to adjust target temp to {} from mqttbroker".format(message["temp"]))

			self.schedule.updatebasetemp(datetime.datetime.now(), message["temp"], duration = 1)


	def sensormessagein(self, topic, message):
		loggerdo.log.debug("mqttbroker - sensor message recieved for {}".format(topic))
		message = checkmessage(message)
		self.house.settemp(topic, message)



	def buildmessage(system, state):
		data = {system: state, "time": datetime.datetime.now()}
		return json.dumps(data)


	def sendmqtt(topic, payload, ret, ip):
		loggerdo.log.info("Topic is {}".format(topic))
		loggerdo.log.info("payload is {}".format(payload))
		loggerdo.log.info("ip is {}".format(ip))
		publish.single(topic, payload=payload, retain=ret, hostname=ip, keepalive=60)



	def on_publish(self, mqttc, obj, mid):
		print("mid: " + str(mid))


	def on_subscribe(self, mqttc, obj, mid, granted_qos):
		print("Subscribed: " + str(mid) + " " + str(granted_qos))


	def on_log(self, mqttc, obj, level, string):
		print(string)



	def run(self):
		self.mqttc.loop_forever()
