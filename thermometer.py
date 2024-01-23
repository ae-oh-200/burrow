from libraries import loggerdo
from libraries import utils
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import json
import datetime



#Would like humidity and temperature to return as 1 get request


def maketopics(mqttconfig):
	listtopic = []
	for topic in mqttconfig["sensorlist"]:
		listtopic.append((topic, 0))
		loggerdo.log.debug("thermometer - Subscribe to {}".format(topic))
	return listtopic


class thermometer:
    zone = None
    temp = None
    lasttemp = None
    humidity = None
    lasthumidity = None
    lastupdate = None
    weight = None
    test = None

    def __init__(self, zone, weight, topic, test = False):
        self.zone = zone
        self.weight = weight
        self.topic = topic
        self.test = test
        self.lastupdate = datetime.datetime.now()

    def settemp(self, temp):
        self.lasttemp = self.temp
        self.temp = temp
        self.lastupdate = datetime.datetime.now()

    def sethumidity(self, humidity):
        self.lasthumidity = self.humidity
        self.humidity = humidity
        self.lastupdate = datetime.datetime.now()

    def gettemp(self):
        return self.temp

    def gethumidity(self):
        return self.humidity

    def getzone(self):
        return self.zone

    def gettopic(self):
        return self.topic

    def getweight(self):
        return self.weight


class broker:
	mqttc = None
	house = None
	schedule = None


	def __init__(self, house, config):
		self.mqttc = mqtt.Client()
		self.mqttc.on_message = self.on_message
		self.host = config["MQTT"]["mqttserver"]
		self.house = house

		self.mqttc.connect(self.host, 1883, 60)
		self.mqttc.subscribe(maketopics(config["MQTT"]))
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
			publish.single(f"{'/'.join(msgsplit)}/parsed-F", payload=str(ftemp), hostname=self.host)
		elif msgsplit[3] == "f":
			msgsplit.pop(-1)
			loggerdo.log.debug("MQTTlistener-Sensor - {} is {} , in fahrenheit".format(device, msgval))
			self.house.udatesensortemp(device, msgval)
			publish.single(f"{'/'.join(msgsplit)}/parsed-F", payload=str(msgval), hostname=self.host)

		elif msgsplit[3] == "h":
			loggerdo.log.debug("MQTTlistener-Sensor - {} is {} , in humidity".format(device, msgval))
			self.house.udatesensorhumidity(device, msgval)
			

	def run(self):
		self.mqttc.loop_forever()

