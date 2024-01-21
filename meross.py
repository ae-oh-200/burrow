import requests
from requests import exceptions
import json
from libraries import loggerdo
import paho.mqtt.publish as publish
import time
import datetime
import paho.mqtt.client as mqtt
import uuid
import hashlib
import logging


logging.getLogger("requests").setLevel(logging.WARNING)

def truncate(n, decimals=0):
	multiplier = 10 ** decimals
	return int(n * multiplier) / multiplier

class merossswitch():
	IP = None
	name = None
	url = None
	topic = None
	state = None
	lastupdate = None
	online = None
	manualupdatetime = None
	mqttserver = None

	def __init__(self, IP, Name, mqttserver, managed, zone, AC=True):
		self.IP = IP
		self.name = Name
		self.managed = managed
		if AC:
			self.gettopic = 'burrow/meross/AC/' + Name +'/get'
		else:
			self.gettopic = 'burrow/meross/' + Name + '/get'
		self.url = 'http://' + IP + '/config'
		self.online = False
		self.zone = zone
		self.manualupdatetime = (datetime.datetime.now() - datetime.timedelta(seconds=5))
		self.mqttserver = mqttserver
		mqttc = mqtt.Client()
		mqttc.on_message = self.on_message
		mqttc.connect(self.mqttserver, 1883, 60)
		self.state = self.pollstate()
		mqttc.loop_start()
		if AC:
			mqttc.subscribe('burrow/meross/AC/' + Name +'/set')
		else:
			mqttc.subscribe('burrow/meross/' + Name + '/set')
		if self.state is not None:
			self.pubstatemqtt(self.state)
		else:
			loggerdo.log.debug(
				"meross - error in init for {}. did not return state to punlish to mqtt".format(self.name))

	def pollstate(self):
		switchstate = None
		headers = {"Content-Type": "application/json"}
		epochtime, msgidmd5, signmd5 = getmsgid()
		data = {
			"payload": {},
			"header": {
				"messageId": msgidmd5,
				"method": "GET",
				"from": self.url,
				"namespace": "Appliance.System.All",
				"timestamp": epochtime,
				"sign": signmd5,
				"payloadVersion": 1
			}
		}
		try:
			r = requests.post(self.url, data=json.dumps(data), headers=headers, timeout=6)
		except exceptions.ConnectionError:
			loggerdo.log.debug('meross - pollstate - Connection error while trying to connect to {}'.format(self.name))
			self.online = False
		except Exception as e:
			loggerdo.log.debug('meross - pollstate - general exception in pollstate for {}'.format(self.name))
			print(e)
			self.online = False
		else:
			self.online = True
			try:
				data = json.loads(r.text)
			except json.decoder.JSONDecodeError:
				loggerdo.log.debug(f"meross - {self.name} json decode issue")
				return None
			for t in data:
				if t == 'payload':
					for idea in data[t]['all']['digest']['togglex']:
						switchstate = idea

			if switchstate['onoff'] == 1:
				return True
			elif switchstate['onoff'] == 0:
				return False
			else:
				loggerdo.log.debug(f"meross - {self.name} failed to return a valid state")
				return None

	def updateswitch(self, state, force=False):
		if self.checkmanualtimer() or force:
			boolstate = state
			if state is True:
				state = 1
			else:
				state = 0
			headers = {"Content-Type": "application/json"}
			epochtime, msgidmd5, signmd5 = getmsgid()
			data = {
				"payload": {
					"togglex": {
						"onoff": state,
						"channel": 0
					}
				},
				"header": {
					"messageId": msgidmd5,
					"method": "SET",
					"from": self.url,
					"namespace": "Appliance.Control.ToggleX",
					"timestamp": epochtime,
					"sign": signmd5,
					"payloadVersion": 1
				}
			}
			try:
				r = requests.post(self.url, data=json.dumps(data), headers=headers, timeout=4)
			except exceptions.ConnectionError:
				loggerdo.log.debug('meross - updateswitch - Connection error while trying to connect to {}'.format(self.name))
				self.online = False
				return False
			except Exception as e:
				loggerdo.log.debug('meross - updateswitch - general exception in updatestate for {}'.format(self.name))
				print(e)
				self.online = False
				return False

			if boolstate != self.pollstate():
				loggerdo.log.debug("meross - updateswitch - Update did not work for {}".format(self.name))
				return False
			else:
				self.online = True
				self.state = boolstate
				self.pubstatemqtt(boolstate)
				return True
		else:
			loggerdo.log.debug(f"meross - did not update {self.name} to {str(state)}, because Force is {force} and manualtimercehck is {self.checkmanualtimer()}")
			return False

	def pubstatemqtt(self, state):
		try:
			publish.single(self.gettopic, payload=state, retain=False, hostname=self.mqttserver, keepalive=60)
		except Exception as e:
			loggerdo.log.debug('meross - pubstatemqtt - general exception in pubstatemqtt for {}'.format(self.name))
			loggerdo.log.debug('meross - pubstatemqtt - {}}'.format(str(e)))
			print(e)

	def on_message(self,mqttc, obj, msg):
		state = msg.payload.decode("utf-8")
		if state == 'True':
			switchstate = True
			time = 30
		#print('msg update true')
		else:
			switchstate = False
			time = 15
			#print('msg update false')
		if switchstate != self.state:
			# Check to see if incoming state is different then current
			loggerdo.log.debug(f'meross - update switch from mqtt - {self.name} state to {switchstate}')
			update = self.updateswitch(switchstate, force=True)
			if update is False:
				# update was not sucessfull
				loggerdo.log.debug('meross - mqtt - Switch {} did not update.'.format(self.name))
				if self.online is False:
					loggerdo.log.debug('meross - mqtt - Switch {} is offline.'.format(self.name))
			else:
				self.manualupdatetime = datetime.datetime.now() + datetime.timedelta(minutes=time)
				loggerdo.log.debug(
					'meross - manual update set for {} on {} during on_message'.format(str(self.manualupdatetime), self.name))
				loggerdo.log.debug('meross - mqtt - Switch {} update was sucessfull.'.format(self.name))

		self.state = self.pollstate()
		self.pubstatemqtt(self.state)


	def checkmanualtimer(self):
		if datetime.datetime.now() > self.manualupdatetime:
			# now is later then manual timer
			return True
		else:
			loggerdo.log.debug("meross - {} has active manual override".format(self.name))
			return False


	def check(self):
		switchstate = self.pollstate()
		if switchstate is not None:
			# is known state is different then what it currently is
			if self.state != switchstate:
				loggerdo.log.debug('meross - {} state is physically different then what is stored'.format(self.name))
				loggerdo.log.debug('meross - {} returned {} while we think its {}'.format(self.name, switchstate, self.state))
				# update manual change timer
				self.manualupdatetime = datetime.datetime.now() + datetime.timedelta(minutes=15)
				loggerdo.log.debug('meross - check - manual update set for {} on {} during check'.format(str(self.manualupdatetime),self.name))
				# set state to new state
				self.state = switchstate
			# Publish state
			self.pubstatemqtt(switchstate)
			return self.state
		# state returned nothing, so sending back false
		else:
			loggerdo.log.debug('meross - could not get status update')
			if self.online is False:
				loggerdo.log.debug('meross - switch offline - {}'.format(self.name))
			return False

	def ismanaged(self):
		return self.managed

	def getzone(self):
		return self.zone

	def retstate(self):
		return self.state

	def getstate(self):
		loggerdo.log.info('meross - check state for {}'.format(self.name))
		stateupdate = self.check()
		# Check if the "check" worked
		if stateupdate is True:
			# done set state
			# self.state = stateupdate
			self.lastupdate = datetime.datetime.now()
			return self.state
		else:
			# print('get state returned False, which should mean failed - {}'.format(self.name))
			return False

	def setmanualtimer(self, minutes):
		self.manualupdatetime = datetime.datetime.now() + datetime.timedelta(minutes=minutes)


def getmsgid():
	epochtime = int(time.time())
	msgidst = str(uuid.uuid4())
	msgidmd5 = hashlib.md5(msgidst.encode()).hexdigest()
	sign = f"{msgidmd5}666{epochtime}"
	signmd5 = hashlib.md5(sign.encode()).hexdigest()

	return epochtime, msgidmd5, signmd5



