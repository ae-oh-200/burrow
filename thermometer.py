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


	def __init__(self, mqttconfig, house, config):
		self.mqttc = mqtt.Client()
		self.mqttc.on_message = self.on_message

		self.house = house
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
			publish.single(f"{'/'.join(msgsplit)}/parsed-F", payload=str(ftemp), hostname=self.mqttconfig["mqttserver"])
		elif msgsplit[3] == "f":
			msgsplit.pop(-1)
			loggerdo.log.debug("MQTTlistener-Sensor - {} is {} , in fahrenheit".format(device, msgval))
			self.house.udatesensortemp(device, msgval)
			publish.single(f"{'/'.join(msgsplit)}/parsed-F", payload=str(msgval), hostname=self.mqttconfig["mqttserver"])

		elif msgsplit[3] == "h":
			loggerdo.log.debug("MQTTlistener-Sensor - {} is {} , in humidity".format(device, msgval))
			self.house.udatesensorhumidity(device, msgval)
			


if __name__ == "__main__":
    temp = thermometer(local=False, zone = 1, ip='192.168.5.52', port='6969', weight=25)
    print(temp.getremotetemp())
    print(temp.getzone())
    temp = thermometer(local=False, zone = 1, ip='192.168.5.52', port='6969', weight = 75)
    print(temp.getremotetemp())
    print(temp.getzone())
    print(temp.gethumidity())

