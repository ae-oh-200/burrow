import sys
from libraries import loggerdo
import time
import yaml
import os
from os import path
import RPi.GPIO as GPIO
import paho.mqtt.publish as publish
import paho.mqtt.client as mqtt
import json
import datetime
import threading


topicarray = []
topiclist = {}

COOLget = 'burrow/HVAC/COOL/get'
HEATget = 'burrow/HVAC/HEAT/get'
FANget = 'burrow/HVAC/FAN/get'


# Setup GPI Pins
FURNACEpin=11
ACpin=15
BLOWERpin=13

#mqtt server
MQTTSERVER = '192.168.5.70'

BlowerCoolDown = 5
FurnaceCoolDown = 5
ACCOOLDOWN = 5

FurnaceOnTime = 10
MAXFANRUN = 30
FURNACEMAX = 90

topiclist.update({'COOLset': 'burrow/HVAC/COOL/set'})
topiclist.update({'HEATset': 'burrow/HVAC/HEAT/set'})
topiclist.update({'FANset': 'burrow/HVAC/FAN/set'})
topiclist.update({'sync': 'burrow/HVAC/sync'})
topiclist.update({'lastreconnect': 'burrow/HVAC/lastreconnect'})
topiclist.update({'ask': 'burrow/HVAC/ask'})
topiclist.update({'drop': 'burrow/HVAC/dropped'})



#Pulled from utils
def loadconfig():
	if path.exists("config.yaml"):
		configfile = 'config.yaml'
	else:
		configfile = '/etc/burrow/config.yaml'
	loggerdo.log.debug(f"Using config {configfile}")
	with open(configfile, 'r') as file:
		config = yaml.load(file, Loader=yaml.FullLoader)
	return config

def parsejsonmsg(messagestring):
	message = json.loads(messagestring)
	loggerdo.log.debug("json after convert to dict {}".format(messagestring))
	#if there is a time key, update it to be a datetime object from string
	if 'time' in message:
		try:
			# Try time with micro seconds
			message["time"] = datetime.datetime.strptime(message["time"], "%m-%d-%Y, %H:%M:%S.%f")
		except ValueError:
			# fall back to time format without microseconds
			message["time"] = datetime.datetime.strptime(message["time"], "%m-%d-%Y, %H:%M:%S")
	return message

def truncate(n, decimals=0):
	multiplier = 10 ** decimals
	return int(n * multiplier) / multiplier

class HVAC:
	FURNACEpin = None
	ACpin = None
	BLOWERpin = None

	lastupdateON_FURNACE = datetime.datetime.now() - datetime.timedelta(minutes=1)
	lastupdateOFF_FURNACE = datetime.datetime.now() - datetime.timedelta(minutes=1)
	lastupdateON_AC = datetime.datetime.now() - datetime.timedelta(minutes=1)
	lastupdateOFF_AC = datetime.datetime.now() - datetime.timedelta(minutes=1)
	lastupdateON_FAN = datetime.datetime.now() - datetime.timedelta(minutes=1)
	lastupdateOFF_FAN = datetime.datetime.now() - datetime.timedelta(minutes=1)

#use furnace pin 11


	def __init__(self):
		self.furnace = False
		self.ac = False
		self.blower = False
		self.FURNACEpin = FURNACEpin
		self.ACpin = ACpin
		self.BLOWERpin = BLOWERpin

		GPIO.setwarnings(False)
		GPIO.setmode(GPIO.BOARD)

		GPIO.setup(self.ACpin, GPIO.OUT)
		GPIO.setup(self.FURNACEpin, GPIO.OUT)
		GPIO.setup(self.BLOWERpin, GPIO.OUT)
		# Drop pins to make sure relay is off
		GPIO.output(self.ACpin, GPIO.HIGH)
		GPIO.output(self.FURNACEpin, GPIO.HIGH)
		GPIO.output(self.BLOWERpin, GPIO.HIGH)
		time.sleep(30)

	def furnaceON(self):
		self.mutually_exclusive()
		GPIO.output(self.FURNACEpin, GPIO.LOW)
		self.lastupdateON_FURNACE = datetime.datetime.now()
		self.furnace = True

	def furnaceOFF(self):
		GPIO.output(self.FURNACEpin, GPIO.HIGH)
		self.lastupdateOFF_FURNACE = datetime.datetime.now()
		self.furnace = False

	def acON(self):
		self.mutually_exclusive()
		GPIO.output(self.ACpin, GPIO.LOW)
		self.lastupdateON_AC = datetime.datetime.now()
		self.ac = True

	def acOFF(self):
		GPIO.output(self.ACpin, GPIO.HIGH)
		self.lastupdateOFF_AC = datetime.datetime.now()
		self.ac = False

	def blowerON(self):
		GPIO.output(self.BLOWERpin, GPIO.LOW)
		self.lastupdateON_FAN = datetime.datetime.now()
		self.blower = True

	def blowerOFF(self):
		GPIO.output(self.BLOWERpin, GPIO.HIGH)
		self.lastupdateOFF_FAN = datetime.datetime.now()
		self.blower = False

	def setuptimers(self):
		self.lastupdateON_FURNACE = datetime.datetime.now() - datetime.timedelta(minutes=16)
		self.lastupdateOFF_FURNACE = datetime.datetime.now() - datetime.timedelta(minutes=16)
		self.lastupdateON_AC = datetime.datetime.now() - datetime.timedelta(minutes=16)
		self.lastupdateOFF_AC = datetime.datetime.now() - datetime.timedelta(minutes=16)
		self.lastupdateON_FAN = datetime.datetime.now() - datetime.timedelta(minutes=16)
		self.lastupdateOFF_FAN = datetime.datetime.now() - datetime.timedelta(minutes=16)

	def mutually_exclusive(self):
		if self.furnace and self.ac:
			print("big problem, should not have both")
			self.shutitdown(term=False)
			raise RuntimeError ("Mutually Exclusive Fail")


	def shutitdown(self, term = False):

		print('HVAC  - kill all systems?')
		self.acOFF()
		self.furnaceOFF()
		self.blowerOFF()

		if term:
			print('try and exit program')
		else:
			return True



class broker():
	lastupdate = None
	lastsync = None
	COOL = None
	HEAT = None
	FAN = None
	mqttconnected = False
	mqttc = None
	mqttserver = None
	updateflag = None
	shutitdown = None

	topicarray = []

	def __init__(self):

		self.mqttserver = MQTTSERVER
		self.updateflag = False
		self.COOL = False
		self.HEAT = False
		self.FAN = False
		self.lastsync = datetime.datetime.now() - datetime.timedelta(minutes=1)
		self.lastupdate = None

		self.mqttc = mqtt.Client()

		for topic in topiclist:
			self.topicarray.append((topiclist[topic], 0))

		self.mqttc.on_message = self.on_message
		self.mqttc.on_connect = self.on_connect
		#self.mqttc.on_disconnect = self.on_disconnect
		self.mqttc.on_subscribe = self.on_subscribe

		loggerdo.log.debug("HVAC - MQTT - Starting the mqtt connect")
		#self.mqttc.connect(self.mqttserver, keepalive=30)
		self.mqttc.connect(self.mqttserver)
		#self.mqttc.loop_start()
		#
		time.sleep(2)
		loggerdo.log.debug("HVAC - MQTT - MQTT connect done")
		publish.single(topiclist['sync'], payload=(str(datetime.datetime.now())), hostname=self.mqttserver)


	def on_message(self, mqttc, obj, msg):

		loggerdo.log.debug("HVAC - MQTT - Message received")
		loggerdo.log.debug(f"{str(msg.topic)} {str(msg.qos)} {str(msg.payload)}.")

		topics = msg.topic.split("/")
		msg = msg.payload.decode("utf-8")

		# topic[2] should contain important
		if topics[2] == "COOL":
			if msg == 'True':
				loggerdo.log.debug('HVAC - MQTT - Message to turn COOL on')
				self.COOL = True
				self.lastupdate = datetime.datetime.now()

			elif msg == 'False':
				loggerdo.log.debug("HVAC - MQTT - Message to turn COOL off ")
				self.COOL = False
				self.lastupdate = datetime.datetime.now()
			else:
				loggerdo.log.debug("HVAC - MQTT - could not read COOL message")

		elif topics[2] == "HEAT":
			if msg == 'True':
				loggerdo.log.debug('HVAC - MQTT - Message to turn HEAT on')
				self.HEAT = True
				self.lastupdate = datetime.datetime.now()

			elif msg == 'False':
				loggerdo.log.debug('HVAC - MQTT - Message to turn HEAT off')
				self.HEAT = False
				self.lastupdate = datetime.datetime.now()

			else:
				loggerdo.log.debug("HVAC - MQTT - could not read HEAT message")

		elif topics[2] == "FAN":
			if msg == 'True':
				loggerdo.log.debug('HVAC - MQTT - Message to turn FAN on')
				self.FAN = True
				self.lastupdate = datetime.datetime.now()

			elif msg == 'False':
				loggerdo.log.debug('HVAC - MQTT - Message to turn FAN off')
				self.FAN = False
				self.lastupdate = datetime.datetime.now()

			else:
				loggerdo.log.debug("HVAC - MQTT - could not read FAN message")

		elif topics[2] == "sync":
			print("HVAC - MQTT - sync message in")
			# convert msg to datetime
			try:
				msg = datetime.datetime.strptime(msg, '%Y-%m-%d %H:%M:%S.%f')
				self.lastsync = msg
				print('HVAC - MQTT - sync msg recevied and sync updated')
			except:
				print('HVAC - MQTT - could not convert sync msg to datetime')

		elif topics[2] == 'ask':
			print('HVAC - MQTT - ask message in')
			publish.single(topiclist['sync'], payload=(str(datetime.datetime.now())), hostname=self.mqttserver, keepalive=60)

		else:
			print('HVAC - MQTT - message with unknown in {}'.format(topics))

	def on_subscribe(self, mqttc, obj, mid, granted_qos):
		print("Subscribed: " + str(mid) + " " + str(granted_qos))

	def on_connect(self, mqttc, obj, flags, rc):
		#loggerdo.log.info("MQTT - on_connect - Connected with result code " + str(rc))
		loggerdo.log.debug("MQTT - on_connect - Connected to %s:%s" % (mqttc._host, mqttc._port))
		# check if reconnect sucessful.
		if rc==0:
			self.mqttconnected = True
		else:
			loggerdo.log.info("MQTT - on_connect - connect failed")
		# Pause for 30 seconds to prevent immediate reconnect
		time.sleep(3)
		self.mqttc.subscribe(self.topicarray)

	#def on_disconnect(self, mqttc, obj, rc):
	#	loggerdo.log.info('MQTT - on_disconnect - MQTT disconnected')

	def sendsync(self):
		try:
			publish.single(topiclist['sync'], payload=(str(datetime.datetime.now())), hostname=self.mqttserver, keepalive=60)
		except ConnectionRefusedError:
			loggerdo.log.debug('MQTT - sendsync - Connection Refused error')
		except OSError as e:
			loggerdo.log.debug('MQTT - sendsync - OS Error, {}'.format(str(e)))

	def sendupdate(self, heat, ac, fan):
		self.FAN = fan
		self.HEAT = heat
		self.COOL = ac
		try:
			publish.single(HEATget, payload=str(heat), hostname=self.mqttserver, keepalive=60)
			publish.single(FANget, payload=str(fan), hostname=self.mqttserver, keepalive=60)
			publish.single(COOLget, payload=str(ac), hostname=self.mqttserver, keepalive=60)

		except ConnectionRefusedError:
			loggerdo.log.debug('MQTT - sendupdate - Connection refused error')

		except OSError as e:
			loggerdo.log.debug('MQTT - sendupdate - OS Error, {}'.format(str(e)))

	def run(self):
		self.mqttc.loop_forever()

def runmqttbroker(mqtt):
    mqtt.run()




def run():
	print('loop starting')
	FANONLY = False

	mqttbroker = broker()
	myHVAC = HVAC()
	justblower = False
	cooldownblower = False



	JustBlowerTimer = datetime.datetime.now() - datetime.timedelta(minutes=16)

	FurnaceOffTimer = datetime.datetime.now() - datetime.timedelta(minutes=16)
	ACOffTimer = datetime.datetime.now() - datetime.timedelta(minutes=16)



	mqttthread = threading.Thread(target=runmqttbroker, args=(mqttbroker,))
	mqttthread.setDaemon(True)
	mqttthread.start()

	#mqttbroker.run()

	while True:
		lastsync = mqttbroker.lastsync


		#Check for sync message, if older than 5 minutes notify
		if lastsync < datetime.datetime.now() - datetime.timedelta(minutes=2):
			mqttbroker.sendsync()
		elif lastsync < datetime.datetime.now() - datetime.timedelta(minutes=5):
			loggerdo.log.info("lastsync shouldnt be more than 6 minutes old, last sync - {}".format(
				str(lastsync)))


		# Check to see if blower was on and now heat or ac is turned on.
		# Keep fan from being started if already on
		if justblower is True and (mqttbroker.HEAT is True or mqttbroker.COOL is True):
			# Force turn fan off
			loggerdo.log.info('HVAC - RUN - Fan is manually on while cool or heat is requested.')
			if mqttbroker.COOL is True:
				justblower = False
				myHVAC.blowerOFF()
				myHVAC.acON()
				ACOffTimer = datetime.datetime.now()

			elif mqttbroker.HEAT:
				justblower = False
				myHVAC.blowerOFF()
				myHVAC.furnaceON()
				FurnaceOffTimer = datetime.datetime.now()

		# this is going from heat/cool to fan
		if mqttbroker.FAN is True and (myHVAC.furnace is True or myHVAC.ac is True):
			if mqttbroker.COOL is True:
				myHVAC.acOFF()
				myHVAC.blowerON()
				justblower = True
				JustBlowerTimer = datetime.datetime.now() + datetime.timedelta(minutes=MAXFANRUN)
			elif mqttbroker.HEAT:
				myHVAC.furnaceOFF()
				myHVAC.blowerON()
				justblower = True
				JustBlowerTimer = datetime.datetime.now() + datetime.timedelta(minutes=MAXFANRUN)


		# check blower is off but requested on
		elif mqttbroker.FAN is True and justblower is False:
			loggerdo.log.debug('HVAC - RUN - Fan On was requested by MQTT')
			justblower = True
			myHVAC.blowerON()
			JustBlowerTimer = datetime.datetime.now() + datetime.timedelta(minutes=MAXFANRUN)

		# check if blower is on but requested off
		elif justblower is True and mqttbroker.FAN is False:
			loggerdo.log.debug('HVAC - RUN - Fan Off was requested by MQTT')
			justblower = False
			myHVAC.blowerOFF()

		# check heat status
		elif myHVAC.furnace != mqttbroker.HEAT:
			# Heat is off, requested to turn on
			if myHVAC.furnace is False and mqttbroker.HEAT is True:
				loggerdo.log.debug("heat was off, time to turn on")
				myHVAC.furnaceON()
				FurnaceOffTimer = datetime.datetime.now()
			# Heat is on, requested to turn off
			elif mqttbroker.HEAT is False and myHVAC.furnace is True:
				loggerdo.log.debug('HVAC - RUN - Heat should turn off, but fan should run')
				myHVAC.furnaceOFF()
				cooldownblower = True
				myHVAC.blowerON()
				JustBlowerTimer = datetime.datetime.now() + datetime.timedelta(minutes=FurnaceCoolDown)


			elif mqttbroker.HEAT is False and myHVAC.furnace is False and myHVAC.blower is True:
				loggerdo.log.debug('HVAC - RUN - heat on, furnace off, fan running. Not doing anything')


		elif myHVAC.ac != mqttbroker.COOL:
			loggerdo.log.debug('HVAC - RUN - making cool changes')
			loggerdo.log.debug('HVAC - RUN - myhvac ac is {}'.format(myHVAC.ac))
			loggerdo.log.debug('HVAC - RUN - broker hvac is {}'.format(mqttbroker.COOL))

			if myHVAC.ac is False and mqttbroker.COOL is True:
				loggerdo.log.debug('HVAC - RUN - AC was off, turning it on.')
				myHVAC.acON()
				ACOffTimer = datetime.datetime.now()

			elif myHVAC.ac is True and mqttbroker.COOL is False:
				loggerdo.log.debug('HVAC - RUN - AC was on, turning if off.')
				myHVAC.acOFF()
				cooldownblower = True
				myHVAC.blowerON()
				JustBlowerTimer = datetime.datetime.now() + datetime.timedelta(minutes=ACCOOLDOWN)


		# make sure furnace doesnt run to long
		if datetime.datetime.now() > FurnaceOffTimer + datetime.timedelta(minutes=FURNACEMAX) and myHVAC.furnace is True:
			loggerdo.log.debug(f'HVAC - RUN - HVAC is running for {FURNACEMAX} minutes, turning it off.')
			myHVAC.furnaceOFF()
			cooldownblower = True
			myHVAC.blowerON()
			JustBlowerTimer = datetime.datetime.now() + datetime.timedelta(minutes=FurnaceCoolDown)



		if datetime.datetime.now() > JustBlowerTimer and cooldownblower is True:
			loggerdo.log.debug(f'HVAC - RUN - blower itself running for {FurnaceCoolDown} minutes. Time to turn off')
			cooldownblower = False
			myHVAC.blowerOFF()


		#if myHVAC.furnace != mqttbroker.HEAT and myHVAC.ac != mqttbroker.COOL and myHVAC.blower != mqttbroker.FAN:
		if myHVAC.furnace != mqttbroker.HEAT and myHVAC.ac != mqttbroker.COOL and myHVAC.blower != mqttbroker.FAN:
			loggerdo.log.info('HVAC - RUN - out of sync in run')
			raise RuntimeError ("DIE")


		#mqttbroker.sendupdate(heat=myHVAC.furnace, ac=myHVAC.ac, fan=myHVAC.blower)
		mqttbroker.sendupdate(heat=myHVAC.furnace, ac=myHVAC.ac, fan=justblower)
		time.sleep(2)



if sys.argv[-1] == "on":
	FURNACEpin = 11
	ACpin = 15
	BLOWERpin = 13

	GPIO.setwarnings(False)
	GPIO.setmode(GPIO.BOARD)
	GPIO.setup(ACpin, GPIO.OUT)
	GPIO.setup(FURNACEpin, GPIO.OUT)
	GPIO.setup(BLOWERpin, GPIO.OUT)
	print("turn all on")
	GPIO.output(ACpin, GPIO.LOW)
	GPIO.output(BLOWERpin, GPIO.LOW)
	GPIO.output(FURNACEpin, GPIO.LOW)

elif sys.argv[-1] == "off":
	FURNACEpin = 11
	ACpin = 15
	BLOWERpin = 13

	GPIO.setwarnings(False)
	GPIO.setmode(GPIO.BOARD)
	GPIO.setup(ACpin, GPIO.OUT)
	GPIO.setup(FURNACEpin, GPIO.OUT)
	GPIO.setup(BLOWERpin, GPIO.OUT)
	print("turn all off")
	GPIO.output(ACpin, GPIO.HIGH)
	GPIO.output(BLOWERpin, GPIO.HIGH)
	GPIO.output(FURNACEpin, GPIO.HIGH)

elif sys.argv[-1] == "ac":
	FURNACEpin = 11
	ACpin = 15
	BLOWERpin = 13

	GPIO.setwarnings(False)
	GPIO.setmode(GPIO.BOARD)
	GPIO.setup(ACpin, GPIO.OUT)
	print('off')
	GPIO.output(ACpin, GPIO.HIGH)
	time.sleep(4)
	print('on')
	GPIO.output(ACpin, GPIO.LOW)
	time.sleep(30)
	print("off")
	GPIO.output(ACpin, GPIO.HIGH)

elif sys.argv[-1] == "heat":
	FURNACEpin = 11
	ACpin = 15
	BLOWERpin = 13
	GPIO.setwarnings(False)
	GPIO.setmode(GPIO.BOARD)
	GPIO.setup(FURNACEpin, GPIO.OUT)
	print('off')
	GPIO.output(FURNACEpin, GPIO.HIGH)
	time.sleep(8)
	print('on')
	GPIO.output(FURNACEpin, GPIO.LOW)
	time.sleep(80)
	print('off')
	GPIO.output(FURNACEpin, GPIO.HIGH)

elif sys.argv[-1] == "fan":
	FURNACEpin = 11
	ACpin = 15
	BLOWERpin = 13
	GPIO.setwarnings(False)
	GPIO.setmode(GPIO.BOARD)
	GPIO.setup(BLOWERpin, GPIO.OUT)
	print('off')
	GPIO.output(BLOWERpin, GPIO.HIGH)
	time.sleep(8)
	print('on')
	GPIO.output(BLOWERpin, GPIO.LOW)
	time.sleep(8)
	print('off')
	GPIO.output(BLOWERpin, GPIO.HIGH)

else:
		run()


# done