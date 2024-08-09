import RPi.GPIO as GPIO
import paho.mqtt.publish as publish
import paho.mqtt.client as mqtt
import json
import datetime
import threading
import time
from libraries import loggerdo
import sys

FRONT_TRIGGER = 5
FRONT_ECHO = 6
REAR_TRIGGER = 13
REAR_ECHO = 26
ACTIVATE_OPENER = 12

SONAR_TIMEOUT = 0.5

MQTTSERVER = "192.168.5.70"
OPEN_DIST = 30
MAX_DIST = 250
OPENERSLEEPTIME = 1
SONAR_READ_DELAY = 0.5
DEFAULTDELAY = 5
GPIO_SETTLE = 1
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# setup opener pin
GPIO.setup(ACTIVATE_OPENER, GPIO.OUT)
GPIO.output(ACTIVATE_OPENER, GPIO.LOW)

GARAGEOPENTOPIC = 'burrow/garage/set'
GARAGEOPENGETTOPIC = 'burrow/garage/get'
BASETOPIC = 'burrow/garage/'

topicarray = []
topiclist = {}

topiclist.update({'GARAGEOPENTOPIC': 'burrow/garage/set'})
topiclist.update({'GARAGEOPENGETTOPIC': 'burrow/garage/get'})
topiclist.update({'sync': 'burrow/garage/sync'})


class sonarsensor:

	def __init__(self, trigger_pin, echo_pin, name):
		print(f'make sensor - {name}')
		self.trigger_pin = trigger_pin
		self.echo_pin = echo_pin
		self.timeout = SONAR_TIMEOUT

		GPIO.setup(self.trigger_pin, GPIO.OUT)
		GPIO.setup(self.echo_pin, GPIO.IN)

		self.dist = 0
		self.name = name
		self.sonarstack = []
		self.state = "good"

		self.invalidcount = 0
		self.errcount = 0
		self.measuredistance()

	def read(self):
		GPIO.output(self.trigger_pin, GPIO.LOW)
		# Waiting for sensor to settle
		time.sleep(GPIO_SETTLE)
		GPIO.output(self.trigger_pin, GPIO.HIGH)
		time.sleep(0.00001)
		GPIO.output(self.trigger_pin, GPIO.LOW)
		# x is the timeout
		x = 0
		while GPIO.input(self.echo_pin)==0 and x <= 5000:
			pulse_start_time = time.time()
			x+=1
		# If we went over x, return None.
		if x >= 5000:
			loggerdo.log.info(f"aborted read for {self.name}, x was over 5000 after pulse start")
			return None
		x = 0
		while GPIO.input(self.echo_pin)==1 and x <= 5000:
			pulse_end_time = time.time()
			x+=1
		# If we went over x, return None
		if x >= 5000:
			loggerdo.log.info(f"aborted read for {self.name}, x was over 5000 after pulse end")
			return None

		pulse_duration = pulse_end_time - pulse_start_time
		distance = round(pulse_duration * 17150, 2)
		#return it
		return distance

	def measuredistance(self):
		dist = self.read()

		# Check if the read is good.
		if dist is not None:
			# check if reading is under max
			if dist < MAX_DIST:
				# if its good then clear all errors
				# self.errcount = 0
				# self.invalidcount = 0
				# Not using average stack right now, but ported over from old code
				self.state = "good"
				self.dist = dist
			# probably bad read.
			else:
				self.invalidcount += 1
				self.state = "invalid"
				loggerdo.log.debug(f'invalid distance - {self.name}, count - {self.invalidcount}')

		else:
			self.errcount += 1
			self.state = "error"
			loggerdo.log.debug(f'inc error count on {self.name} to {self.errcount}')

		self.publish(dist)

		return self.dist

	def managestack(self, value):
		self.sonarstack.append(value)

		stacksum = 0
		for i in self.sonarstack:
			stacksum = stacksum + i

		if stacksum == 0:
			# print(f'sum is {sum}')
			# print(f'len is {len(sonar2stack)}')
			return None
		return truncate(stacksum / len(self.sonarstack))

	def publish(self, dist):
		sentmqtt(BASETOPIC + self.name + '/invalid/count', self.invalidcount, retain=True)
		sentmqtt(BASETOPIC + self.name + '/error/count', self.errcount, retain=True)

		# if self.invalidcount > 0:
		if self.state == "invalid":
			print('publish invalid')
			sentmqtt(BASETOPIC + self.name + '/invalid/time', datetime.datetime.now(), retain=True)
			sentmqtt(BASETOPIC + self.name + '/invalid/read', dist, retain=True)
		# if self.errcount > 0:
		if self.state == "error":
			print('publish error')

			sentmqtt(BASETOPIC + self.name + '/error/time', datetime.datetime.now(), retain=True)
			sentmqtt(BASETOPIC + self.name + '/error/read', dist, retain=True)

		if self.state == "good":
			sentmqtt(BASETOPIC + self.name + '/good', datetime.datetime.now(), retain=True)
		# Publish dist
		sentmqtt(BASETOPIC + self.name, dist, retain=True)

class door:

	def __init__(self):
		self.pos = 0
		self.front = sonarsensor(trigger_pin=FRONT_TRIGGER, echo_pin=FRONT_ECHO, name='sonar-front')
		self.rear = sonarsensor(trigger_pin=REAR_TRIGGER, echo_pin=REAR_ECHO, name='sonar-rear')

	def CheckPosition(self):
		distfront = self.front.measuredistance()
		if distfront is None:
			loggerdo.log.info('ERROR reading distfront')
		else:
			loggerdo.log.debug(f'distfront {distfront}')

		time.sleep(SONAR_READ_DELAY)

		distrear = self.rear.measuredistance()
		if distrear is None:
			loggerdo.log.info('ERROR reading distrear')
		else:
			loggerdo.log.debug(f'distrear {distrear}')


		if distrear and distrear:

			avg = (distfront + distrear) / 2
			if (distfront < OPEN_DIST) and (distrear > OPEN_DIST):
				# print('garage is half')
				sentmqtt(BASETOPIC + 'pos', 50, retain=False)
				self.pos = 50

			elif avg > OPEN_DIST:
				# garage is closed
				sentmqtt(BASETOPIC + 'pos', 0, retain=False)
				self.pos = 0
			else:
				# garage is open
				sentmqtt(BASETOPIC + 'pos', 100, retain=False)
				self.pos = 100

		elif distfront:
			loggerdo.log.debug('run with only dist 1')

			if distfront > OPEN_DIST:
				# garage is closed
				sentmqtt(BASETOPIC + 'pos', 0, retain=False)
				self.pos = 0
			else:
				# garage is open
				sentmqtt(BASETOPIC + 'pos', 100, retain=False)
				self.pos = 100

		elif distrear:
			loggerdo.log.debug('run with only dist 2')
			if distrear > OPEN_DIST:
				# garage is closed
				sentmqtt(BASETOPIC + 'pos', 0, retain=False)
				self.pos = 0
			else:
				# garage is open
				sentmqtt(BASETOPIC + 'pos', 100, retain=False)
				self.pos = 100

		else:
			loggerdo.log.debug('unable to calc pos because both sensors are not available')
			sentmqtt(BASETOPIC + 'pos', 'unable to calc pos because both sensors are not available', retain=False)

	def close(self):
		delay = DEFAULTDELAY
		if self.pos == 0:
			loggerdo.log.debug('garage is already closed')
			return
		activateopener()
		time.sleep(delay)
		self.CheckPosition()
		x = 0
		while self.pos > 51:
			if x < 3:
				loggerdo.log.debug('close failed, retrying to open')
				activateopener()
				loggerdo.log.debug(f'close delay is now {delay}')
				time.sleep(delay)
				self.CheckPosition()
				x += 1
				delay = delay + 5
			else:
				loggerdo.log.debug(f'pigarage-close - garage would not close')
				sentmqtt(BASETOPIC + 'ACTIVATE/FAIL', datetime.datetime.now(), retain=True)
				sentmqtt(topiclist['GARAGEOPENGETTOPIC'], "stopped", retain=False)
				return

		sentmqtt(topiclist['GARAGEOPENGETTOPIC'], "close", retain=False)
		sentmqtt(BASETOPIC + 'ACTIVATE/GOOD', datetime.datetime.now(), retain=False)

		return

	def open(self):
		delay = DEFAULTDELAY
		if self.pos > 0:
			loggerdo.log.debug('garage is already open')
			return

		activateopener()
		time.sleep(delay)
		self.CheckPosition()

		x = 0
		while self.pos == 0:
			loggerdo.log.debug('open failed, retrying to open')
			if x < 3:
				activateopener()
				loggerdo.log.debug(f'open delay is now {delay},')
				time.sleep(delay)
				self.CheckPosition()
				delay = delay + 5
				x += 1
			else:
				loggerdo.log.debug(f'pigarage-open - garage would not open')

				sentmqtt(topiclist['GARAGEOPENGETTOPIC'], "stopped", retain=False)
				sentmqtt(BASETOPIC + 'ACTIVATE/FAI', datetime.datetime.now(), retain=True)
				return

		sentmqtt(topiclist['GARAGEOPENGETTOPIC'], "open", retain=False)
		sentmqtt(BASETOPIC + 'ACTIVATE/GOOD', datetime.datetime.now(), retain=False)


class broker:
	lastupdate = None
	mqttconnected = False
	mqttc = None
	updateflag = None
	shutitdown = None

	def __init__(self, garagedoor):
		self.lastsync = datetime.datetime.now() - datetime.timedelta(minutes=1)
		self.lastupdate = None
		self.topicarray = []
		self.mqttc = mqtt.Client()
		self.garagedoor = garagedoor

		for topic in topiclist:
			self.topicarray.append((topiclist[topic], 0))

		self.mqttc.on_message = self.on_message
		self.mqttc.on_connect = self.on_connect
		self.mqttc.on_disconnect = self.on_disconnect
		self.mqttc.on_subscribe = self.on_subscribe

		loggerdo.log.debug("GARAGE - MQTT - Starting the mqtt connect")
		self.mqttc.connect(MQTTSERVER, keepalive=30)
		# self.mqttc.loop_start()
		#
		time.sleep(0.5)
		loggerdo.log.debug("GARAGE - MQTT - MQTT connect done")
		sentmqtt(topiclist['sync'], datetime.datetime.now(), retain=False)

	def on_message(self, mqttc, obj, msg):

		loggerdo.log.debug("GARAGE - MQTT - Message received")
		loggerdo.log.debug(f"{str(msg.topic)} {str(msg.qos)} {str(msg.payload)}.")

		topics = msg.topic.split("/")
		msg = msg.payload.decode("utf-8")

		# topic[2] should contain important
		if topics[2] == "set":
			if msg == '1':
				print('open')
				self.garagedoor.open()
			elif msg == "0":
				print('close')
				self.garagedoor.close()

		elif topics[2] == "sync":
			print("HVAC - MQTT - sync message in")
			# convert msg to datetime
			try:
				msg = datetime.datetime.strptime(msg, '%Y-%m-%d %H:%M:%S.%f')
				self.lastsync = msg
				print('HVAC - MQTT - sync msg recevied and sync updated')
			except:
				print('HVAC - MQTT - could not convert sync msg to datetime')

	def on_subscribe(self, mqttc, obj, mid, granted_qos):
		print("Subscribed: " + str(mid) + " " + str(granted_qos))

	def on_connect(self, mqttc, obj, flags, rc):
		loggerdo.log.info("MQTT - on_connect - Connected with result code " + str(rc))
		loggerdo.log.debug("MQTT - on_connect - Connected to %s:%s" % (mqttc._host, mqttc._port))
		# check if reconnect sucessfulL.
		if rc == 0:
			self.mqttconnected = True
		else:
			print("GARAGE - MQTT - on_connect - connect failed")
		# Pause for 30 seconds to prevent immediate reconnect
		time.sleep(3)
		self.mqttc.subscribe(self.topicarray)

	def on_disconnect(self, mqttc, obj, rc):
		loggerdo.log.info('GARAGE - MQTT - on_disconnect - MQTT disconnected')

	def sendsync(self):
		try:
			sentmqtt(topiclist['sync'], datetime.datetime.now(), retain=False)
		except ConnectionRefusedError:
			print('GARAGE - MQTT - sendsync - Connection Refused error')
		except OSError as e:
			print('GARAGE - MQTT - sendsync - OS Error, {}'.format(str(e)))

	def run(self):
		self.mqttc.loop_forever()


def sentmqtt(topic, msg, retain=False):
	try:
		publish.single(topic, payload=str(msg), hostname=MQTTSERVER, retain=retain,keepalive=60)
	except ConnectionRefusedError:
		print('GARAGE - MQTT - sendsync - Connection Refused error')
	except OSError as e:
		print('GARAGE - MQTT - sendsync - OS Error, {}'.format(str(e)))

def activateopener():
	GPIO.output(ACTIVATE_OPENER, GPIO.HIGH)
	time.sleep(OPENERSLEEPTIME)
	GPIO.output(ACTIVATE_OPENER, GPIO.LOW)


def truncate(n, decimals=0):
	multiplier = 10 ** decimals
	return int(n * multiplier) / multiplier


def runmqttbroker(mqtt):
	mqtt.run()


def run():
	print('loop starting')
	garagedoor = door()
	mqttbroker = broker(garagedoor)

	mqttthread = threading.Thread(target=runmqttbroker, args=(mqttbroker,))
	mqttthread.setDaemon(True)
	mqttthread.start()

	# mqttbroker.run()

	while True:
		# Every 5 mins or so
		# look for response
		# print("last sync is {}".format(lastsync))
		loggerdo.log.debug('GARAGE - RUN - start loop')
		lastsync = mqttbroker.lastsync


		# Check for sync messge, if older than 5 minutes notify
		if lastsync < datetime.datetime.now() - datetime.timedelta(minutes=2):
			mqttbroker.sendsync()
		elif lastsync < datetime.datetime.now() - datetime.timedelta(minutes=5):
			print("lastsync shouldnt be more than 6 minutes old, last sync - {}".format(
				str(lastsync)))
		garagedoor.CheckPosition()

		sentmqtt(BASETOPIC + 'running', datetime.datetime.now(), retain=True)


		time.sleep(15)


if sys.argv[-1] == "--up":
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

elif sys.argv[-1] == "--down":
	activateopener()

elif sys.argv[-1] == "--front":
	frontsonar = sonarsensor(trigger_pin=FRONT_TRIGGER, echo_pin=FRONT_ECHO, name='sonar-front')
	x = 0
	while x < 11:
		print(frontsonar.measuredistance())

		#print("Distance:", distance, "cm")
		time.sleep(3)
		x += 1


elif sys.argv[-1] == "--rear":
	rearsonar = sonarsensor(trigger_pin=REAR_TRIGGER, echo_pin=REAR_ECHO, name='sonar-rear')
	x = 0
	while x < 11:
		print(rearsonar.measuredistance())

		time.sleep(3)
		x += 1

else:
	print('run')
	time.sleep(39)
	run()
