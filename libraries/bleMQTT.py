from adafruit_ble import BLERadio
from adafruit_ble.advertising import Advertisement
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
import struct
import blablable
import paho.mqtt.publish as publish
import datetime
#from . import loggerdo
import loggerdo
import json
import sys
import time

ble = BLERadio()
macs = {}
topic = f"burrow/sensor/"
mqtt = '192.168.5.70'

def sendmqtt(device, temperature, humidity):
	data = {"sensor": device, "temperature": temperature, "humidity": humidity,
	        'unit': 'celsius', "time": datetime.datetime.now().strftime("%m-%d-%Y, %H:%M:%S")}
	payload = json.dumps(data)
	try:
		#publish.single(topic + device, payload=payload, retain=True, hostname=mqtt, keepalive=60)
		publish.single(topic + device +"/c", payload=str(temperature), hostname=mqtt)
		publish.single(topic + device + "/h", payload=str(humidity), hostname=mqtt)
	except:
		loggerdo.log.debug("bleMQTT - Unexpected error: {}".format(sys.exc_info()[0]))
	#else:
		#loggerdo.log.debug(f'bleMQTT - Sucessful publish - {topic}{device}')
	#try:
		#publish.single(topic + device + '/c', payload=data['temperature'], retain=True, hostname=mqtt, keepalive=60)
	#except:
		#loggerdo.log.debug("bleMQTT - Unexpected error: {}".format(sys.exc_info()[0]))
	#else:
		#loggerdo.log.debug(f'bleMQTT - Sucessful publish - {topic}{device}')

def truncate(n, decimals=0):
	multiplier = 10 ** decimals
	return int(n * multiplier) / multiplier

def to_bytes_literal(seq):
	"""Prints a byte sequence as a Python bytes literal that only uses hex encoding."""
	return 'b"' + "".join("\\x{:02x}".format(v) for v in seq) + '"'

def compute_length(data_dict, *, key_encoding="B"):
	"""Computes the length of the encoded data dictionary."""
	value_size = 0
	for value in data_dict.values():
		if isinstance(value, list):
			for subv in value:
				value_size += len(subv)
		else:
			value_size += len(value)
	return len(data_dict) + len(data_dict) * struct.calcsize(key_encoding) + value_size


def encode_data(data_dict, *, key_encoding="B"):
	"""Helper which encodes dictionaries into length encoded structures with the given key
	encoding."""
	length = compute_length(data_dict, key_encoding=key_encoding)
	data = bytearray(length)
	key_size = struct.calcsize(key_encoding)
	i = 0
	for key, value in data_dict.items():
		if isinstance(value, list):
			value = b"".join(value)
		item_length = key_size + len(value)
		struct.pack_into("B", data, i, item_length)
		struct.pack_into(key_encoding, data, i + 1, key)
		data[i + 1 + key_size : i + 1 + item_length] = bytes(value)
		i += 1 + item_length
	return bytes(data)

def fixbytearray(bytestring):
	cleanlist = []
	# convert to list
	adv_data = bytestring.split('\\')
	# Remove 'b'
	adv_data.pop(0)
	# remove 'x'
	for byt in adv_data:
		cleanlist.append(byt.replace('x',''))
	return cleanlist

def parsedata(adv_data):
	humidity = int(adv_data[12], 16)
	temperature = adv_data[10] + adv_data[11]
	temperature = int(temperature, 16)
	if temperature > 1000:
		temperature = temperature / 100
	elif temperature > 100:
		temperature = temperature / 10
	return humidity, temperature


def main():
	macs.update({'a4:c1:38:19:47:e9': 'sensors.kitchen'})
	macs.update({'a4:c1:38:39:6c:db': 'sensors.playroom'})
	macs.update({'a4:c1:38:5f:ce:ed': 'sensors.bella'})
	#macs.update({'d4:0b:b0:6d:c3:48': 'sensors.bedroom'})
	macs.update({'a4:c1:38:33:14:c7': 'sensors.bedroom'})
	macs.update({'a4:c1:38:7a:4e:fb': 'sensors.boysroom'})
	macs.update({'a4:c1:38:df:7f:39': 'sensors.livingroom'})


	print("scanning")
	x = 0
	# for advertisement in:
	for advertisement in ble.start_scan(ProvideServicesAdvertisement, Advertisement, blablable.bleSensorData,):

		addr = advertisement.address.string
		# if addr.string == 'a4:c1:38:19:47:e9' or addr.string == 'a4:c1:38:39:6c:db':

		adv_data = to_bytes_literal(encode_data(advertisement.data_dict))
		adv_data = fixbytearray(adv_data)
		if adv_data[2] == '1a' and adv_data[3] == '18' and adv_data[1] == '16' and adv_data[0] == '10':
			#print(macs[addr].split('.')[1])
			humidity, temperature = parsedata(adv_data)
			log = "{} - rh{}, t{}".format(macs[addr].split('.')[1], humidity, temperature)
			#print(log)
			loggerdo.log.debug(log)
			if addr in macs:
				sendmqtt(macs[addr].split('.')[1], truncate(temperature, 2), humidity)
			#else:
				#print('addr not in macs')
		elif adv_data[0] == '16' and adv_data[1] == 'ff':
			#print(macs[addr].split('.')[1])
			try:
				log = "{} - rh{}, t{}".format(macs[addr].split('.')[1], advertisement.relative_humidity,
					                              truncate(advertisement.temperature, 2))
			except KeyError:
				#print(f'bad lookup for {addr}')
				pass
			else:
				#print(log)
				loggerdo.log.debug(log)
				if addr in macs:
					sendmqtt(macs[addr].split('.')[1], truncate(advertisement.temperature, 2),
					         advertisement.relative_humidity)
				#else:
					#print('addr not in macs')
		#else:
		#	loggerdo.log.debug('Message from {} invalid'.format(addr))
		#	loggerdo.log.debug('Message: {} '.format(adv_data))
		#else:
			#print('skip')
	x += 1

def run():
	while True:
		main()
		time.sleep(10)
		print('reset')


run()