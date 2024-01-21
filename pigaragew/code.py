import ipaddress
import ssl
import wifi
import socketpool
import adafruit_requests
import adafruit_minimqtt.adafruit_minimqtt as MQTT
import adafruit_hcsr04
import board
import busio
import time
from digitalio import DigitalInOut, Direction, Pull
import errno
import microcontroller
import alarm

# grab secrets file
try:
	from secrets import secrets
except ImportError:
	print("WiFi secrets are kept in secrets.py, please add them there!")
	raise

pinghost = ipaddress.ip_address(secrets['pinghost'])
BASETOPIC = 'feather/garage/'
OPENERSLEEPTIME = 1
DEFAULTDELAY = 10
OPENERPIN = board.D20
mqttconnected = False
OPEN_DIST = 30
MAX_DIST = 250
GARAGEOPENTOPIC = 'burrow/garage/set'
GARAGEOPENGETTOPIC = 'burrow/garage/get'


# make sure 2nd 3v is up
ldo2 = DigitalInOut(board.LDO2)
ldo2.direction = Direction.OUTPUT
ldo2.value = True
print('ldo2 is up')



# Reset the count if we haven't slept yet.
if not alarm.wake_alarm:
	# Use byte 5 in sleep memory. This is just an example.
	alarm.sleep_memory[5] = 0

print(f'rerun at {str(alarm.sleep_memory[5])}')
alarm.sleep_memory[5] = (alarm.sleep_memory[5] + 1) % 256


def reset():
	print('full reset in 30')
	time.sleep(10)
	print('full reset in 20')
	time.sleep(10)
	print('full reset in 10')
	time.sleep(10)
	print('full reset in 5')
	time.sleep(5)
	# full reset will clear mem
	microcontroller.reset()

def logmsg(msg, mqtt_client=None):
	if mqtt_client:
		publish(mqtt_client, topic=BASETOPIC + 'log', value=f'{time.monotonic()} - {msg}', ret=False)
	else:
		print(f'{time.monotonic()} - {msg}')

def sleepreset():
	# bump sleep reset count
	if alarm.sleep_memory[5] > 9:
		print('do a full ')
		reset()
	alarm.sleep_memory[5] = (alarm.sleep_memory[5] + 1) % 256
	print('sleep reset in 30')
	time.sleep(10)
	print('sleep reset in 20')
	time.sleep(10)
	print('sleep reset in 10')
	#al = alarm.time.TimeAlarm(monotonic_time=time.monotonic() + 20)
	#alarm.exit_and_deep_sleep_until_alarms(al)
	reset()


# start wifi
try:
	wifi.radio.connect(secrets["ssid"], secrets["password"])
except ConnectionError:
	print('wifi unavailable')
	reset()
except Exception as e:
	print(e)
	reset()

print("Connected to %s!" % secrets["ssid"])
print("My IP address is", wifi.radio.ipv4_address)

# setup socket pool
pool = socketpool.SocketPool(wifi.radio)
requests = adafruit_requests.Session(pool, ssl.create_default_context())


def truncate(n, decimals=0):
	multiplier = 10 ** decimals
	return int(n * multiplier) / multiplier

def publish(mqtt_client, topic, value, ret=False):
	try:
		mqtt_client.publish(topic, value, retain=ret)
	except Exception as e:
		if e.errno == errno.ENOTCONN:
			print("error not connected, publish")
			print('time to reset')
			reset()
		else:
			print("not sure what error, publish")


# MQTT functions -
def connect(mqtt_client, userdata, flags, rc):
	global mqttconnected
	# This function will be called when the mqtt_client is connected
	# successfully to the broker.
	print("Connected to MQTT Broker!")
	print("Flags: {0}\n RC: {1}".format(flags, rc))
	mqttconnected = True
	time.sleep(10)
	# setup the start times
	try:
		publish(mqtt_client, topic=BASETOPIC + 'connect', value=time.monotonic(), ret=True)
	except Exception as e:
		if e.errno == errno.ENOTCONN:
			print("error not connected (MQTT CONNECT)")
		else:
			print("not sure what error, wont send (MQTT CONNECT)")


def disconnect(mqtt_client, userdata, rc):
	global mqttconnected
	# This method  is called when the mqtt_client disconnects
	# from the broker.
	print("Disconnected from MQTT Broker!")
	mqttconnected = False

	while not mqttconnected:
		try:
			mqtt_client.reconnect()
		except:
			time.sleep(30)
		else:
			mqttconnected = True
			time.sleep(30)

def subscribe(mqtt_client, userdata, topic, granted_qos):
	# This method is called when the mqtt_client subscribes to a new feed.
	print("Subscribed to {0} with QOS level {1}".format(topic, granted_qos))

class sonarsensor:
	dist = None
	def __init__(self, trigger_pin, echo_pin, name, mqtt_client):
		print(f'make sensor - {name}')
		self.sonarsensor = adafruit_hcsr04.HCSR04(trigger_pin=trigger_pin, echo_pin=echo_pin, timeout=0.5)
		self.dist = self.sonarsensor.distance
		self.name = name
		self.sonarstack = []
		self.invalid = 0
		self.errcount = 0
		self.mqtt_client = mqtt_client

		publish(mqtt_client, topic=BASETOPIC + self.name + '/error', value=0, ret=True)
		publish(mqtt_client, topic=BASETOPIC + self.name + '/error/count', value=0, ret=True)
		publish(mqtt_client, topic=BASETOPIC + self.name +'/invalid', value=0, ret=True)
		publish(mqtt_client, topic=BASETOPIC + self.name + '/invalid/count', value=0, ret=True)
		publish(mqtt_client, topic=BASETOPIC + self.name + '/good', value=0, ret=True)

	def read(self):
		try:
			dist = self.sonarsensor.distance
			# print(dist)
			# print("Temperature: ", sonar.temperature)
			if isinstance(dist, float):
				return dist
			else:
				return None

		except RuntimeError:
			# print("Retrying!")
			logmsg(f'failed to read distance in {self.name}', self.mqtt_client)
			return None

	def getdistance(self):
		dist = self.read()

		if dist is not None:
			# check if reading is under max
			if dist < MAX_DIST:
				# Update MQTT with data
				publish(self.mqtt_client, topic=BASETOPIC + self.name, value=dist, ret=False)
				publish(self.mqtt_client, topic=BASETOPIC + self.name + '/good', value=time.monotonic(), ret=False)
				# clear errors and return dist
				self.errcount = 0
				self.invalid = 0
				# Not using average stack right now, but ported over from old code
				self.managestack(dist)
				self.dist = dist
			# probably bad read.
			else:
				publish(self.mqtt_client, topic=BASETOPIC + self.name + '/invalid/read', value=dist, ret=False)
				self.invalid += 1
				logmsg(f'invalid distance - {self.name}, count - {self.invalid}')
				if self.invalid > 6:
					publish(self.mqtt_client, topic=BASETOPIC + self.name+  '/invalid', value=time.monotonic(), ret=True)

		else:
			self.errcount += 1
			logmsg(f'inc error count on {self.name} to {self.errcount}', self.mqtt_client)
			if self.errcount > 6:
				publish(self.mqtt_client, topic=BASETOPIC + self.name + '/error', value=time.monotonic(), ret=True)

		# update the MQTT with counts
		publish(self.mqtt_client, topic=BASETOPIC + self.name + '/error/count', value=self.errcount, ret=True)
		publish(self.mqtt_client, topic=BASETOPIC + self.name + '/invalid/count', value=self.invalid, ret=True)

		# if invaild is greater than 1 and a multiple of 25 reset the sensor
		if ((self.invalid % 25) == 0) and self.invalid > 1:
			logmsg('going to reset sensor, to many invalids - sonar 1', self.mqtt_client)
			resetsensors(self.mqtt_client)
		# if error is greater than 1 and a multiple of 25 reset the sensor
		elif ((self.errcount % 25) == 0) and self.errcount > 1:
			logmsg('going to reset sensor, to many errors - sonar 1', self.mqtt_client)
			resetsensors(self.mqtt_client)
		# if either invalid or err is greater than 100, reset the device sensor with sleep
		elif (self.invalid > 100) or (self.errcount > 100):
			logmsg('to many read/invalids - sonar 2 - system reset requested', self.mqtt_client)
			sleepreset()

		# return time.

		# if failed is 3 or less than just return last value
		if self.errcount < 4 or self.invalid < 4:
			return self.dist
		else:
			logmsg(f'read error on {self.name}, return None', self.mqtt_client)
			return None


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

class garageopener:

	def __init__(self, pin):
		self.opener = DigitalInOut(pin)
		self.opener.direction = Direction.OUTPUT
		self.opener.value = False

	def activateopener(self):
		self.opener.value = True
		time.sleep(OPENERSLEEPTIME)
		self.opener.value = False
		return True


class door:

	def __init__(self, mqtt_client):
		self.mqtt_client = mqtt_client
		self.pos = 0
		self.sensor1 = sonarsensor(trigger_pin=board.D18, echo_pin=board.D6, name = 'sonar1', mqtt_client=self.mqtt_client)
		self.sensor2 = sonarsensor(trigger_pin=board.D12, echo_pin=board.D13, name = 'sonar2', mqtt_client=self.mqtt_client)

		self.opener = garageopener(pin=OPENERPIN)
		print('door setup')


	def CheckPosition(self):
		dist1 = self.sensor1.getdistance()
		time.sleep(0.5)
		dist2 = self.sensor2.getdistance()
		if dist1 and dist2:

			avg = (dist1 + dist2) / 2
			if (dist1 < OPEN_DIST) and (dist2 > OPEN_DIST):
				# print('garage is half')
				publish(self.mqtt_client, topic=BASETOPIC + 'pos', value=50, ret=False)
				self.pos = 50

			elif avg > OPEN_DIST:
				# garage is closed
				publish(self.mqtt_client, topic=BASETOPIC + 'pos', value=0, ret=False)
				self.pos = 0
			else:
				# garage is open
				publish(self.mqtt_client, topic=BASETOPIC + 'pos', value=100, ret=False)
				self.pos = 100

		elif dist1:
			logmsg('only dist1 is good', self.mqtt_client)
		elif dist2:
			logmsg('only dist2 is good', self.mqtt_client)
		else:
			logmsg('unable to calc pos because both sensors are not available', self.mqtt_client)

	def close(self):
		delay = DEFAULTDELAY
		if self.pos == 0:
			print('garage is already closed')
			return
		self.opener.activateopener()
		time.sleep(delay)
		self.CheckPosition()
		x = 0
		while self.pos > 51:
			if x < 3:
				logmsg('close failed, retrying to open',self.mqtt_client)
				self.opener.activateopener()
				logmsg(f'close delay is now {delay}')
				time.sleep(delay)
				self.CheckPosition()
				x += 1
				delay = delay + 5
			else:
				logmsg(f'pigarage-close - garage would not close',self.mqtt_client)
				publish(self.mqtt_client, topic=BASETOPIC + 'ACTIVATE/FAIL', value=time.monotonic(), ret=True)
				publish(self.mqtt_client, topic=GARAGEOPENGETTOPIC, value="stopped")
				return
		publish(self.mqtt_client, topic=GARAGEOPENGETTOPIC, value="close")
		publish(self.mqtt_client, topic=BASETOPIC + 'ACTIVATE/GOOD', value=time.monotonic(), ret=True)
		return

	def open(self):
		delay = DEFAULTDELAY
		if self.pos > 0:
			return

		self.opener.activateopener()
		time.sleep(delay)
		self.CheckPosition()

		x = 0
		while self.pos == 0:
			logmsg('open failed, retrying to open',self.mqtt_client)
			if x < 3:
				self.opener.activateopener()
				logmsg(f'open delay is now {delay},')
				time.sleep(delay)
				self.CheckPosition()
				delay = delay + 5
				x += 1
			else:
				print(f'pigarage-open - garage would not open')
				publish(self.mqtt_client, topic=BASETOPIC + 'ACTIVATE/FAIL', value=time.monotonic(), ret=True)
				publish(self.mqtt_client, topic=GARAGEOPENGETTOPIC, value="stopped")
				return

		publish(self.mqtt_client, topic=GARAGEOPENGETTOPIC, value="open")
		publish(self.mqtt_client, topic=BASETOPIC + 'ACTIVATE/GOOD', value=time.monotonic(), ret=True)


def resetsensors(mqtt_client):
	time.sleep(1)
	# mqtt_client.publish(BASETOPIC + 'ResetSensorPower', time.monotonic())
	publish(mqtt_client, topic=BASETOPIC + 'ResetSensorPower', value=time.monotonic(), ret=True)
	ldo2.value = False
	print('power off ldo2')
	time.sleep(10)
	ldo2.value = True
	time.sleep(5)


def run():

	print(f'run count = {alarm.sleep_memory[5]}')
	print(f'alarm is = {alarm.wake_alarm}')

	print('starting run')
	# Create a socket pool and MQTT client
	pool = socketpool.SocketPool(wifi.radio)
	mqtt_client = MQTT.MQTT(
		broker=secrets["broker"],
		port=secrets["port"],
		socket_pool=pool
	)

	def message(client, topic, message):
		# Method callled when a client's subscribed feed has a new value.
		print("New message on topic {0}: {1}".format(topic, message))
		if message == '1' or message =='0':
			if message == "0":
				mydoor.close()
			elif message == "1":
				mydoor.open()
		else:
			logmsg('unrecognized message from topic', mqtt_client)


	# setup MQTT stuff
	mqtt_client.on_connect = connect
	mqtt_client.on_disconnect = disconnect
	mqtt_client.on_subscribe = subscribe
	mqtt_client.on_message = message

	mqtt_client.connect()
	time.sleep(1)
	# setup the start times
	#print("Subscribing to %s" % GARAGEOPENTOPIC)
	mqtt_client.subscribe(GARAGEOPENTOPIC)
	#
	#
	mydoor = door(mqtt_client)
	print("set up the door")
	logmsg("set up the door",mqtt_client)

	publish(mqtt_client, topic=BASETOPIC + 'start', value=time.monotonic(), ret=True)
	# print rerun
	publish(mqtt_client, topic=BASETOPIC + 'rerun', value=str(alarm.sleep_memory[5]), ret=False)

	while True:
		publish(mqtt_client, topic=BASETOPIC + 'running', value=time.monotonic(), ret=True)
		mydoor.CheckPosition()
		# Poll the message queue
		try:
			mqtt_client.loop()
		except (ValueError, RuntimeError, MQTT.MMQTTException) as e:
			# print("Failed to get data, retrying\n", e)
			try:
				mqtt_client.reconnect()
			except:
				reset()

		# continue
		time.sleep(0.5)



# main function.
# run()

try:
	run()
except Exception:
	print("run crashed.")
	reset()
