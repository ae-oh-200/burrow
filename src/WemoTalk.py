#!/usr/bin/python
from libraries import loggerdo
import re
import urllib.request
import requests

# Configuration:
# Enter the local IP address of your WeMo in the parentheses of the ip variable below.
# You may have to check your router to see what local IP is assigned to the WeMo.
# It is recommended that you assign a static local IP to the WeMo to ensure the WeMo is always at that address.
# Uncomment one of the triggers at the end of this script.

#ip = '192.168.5.110'

#MIT license
# orginal code from - https://github.com/pdumoulin/blinky
# uopdated and reworked for this project


"""
6112/tcp  filtered dtspc
49153/tcp open     unknown
49155/tcp open     unknown
49156/tcp
"""

class wemo:
	OFF_STATE = '0'
	ON_STATES = ['1', '8']
	ip = None
	#ports = [49153, 49152, 49154, 49151, 49155]
	ports = [49153,49155,49156]
	#port = 49156
	def __init__(self, switch_ip):
		self.ip = switch_ip

	def toggle(self):
		status = self.status()
		if status in self.ON_STATES:
			result = self.off()
			result = 'WeMo is now off.'
		elif status == self.OFF_STATE:
			result = self.on()
			result = 'WeMo is now on.'
		else:
			raise Exception("UnexpectedStatusResponse")
		return result

	def on(self):
		return self._send('Set', 'BinaryState', 1)

	def off(self):
		return self._send('Set', 'BinaryState', 0)

	def status(self):
		return self._send('Get', 'BinaryState')

	def name(self):
		return self._send('Get', 'FriendlyName')

	def signal(self):
		return self._send('Get', 'SignalStrength')

	def _get_header_xml(self, method, obj):
		method = method + obj
		return '"urn:Belkin:service:basicevent:1#%s"' % method

	def _get_body_xml(self, method, obj, value=0):
		method = method + obj
		return '<u:%s xmlns:u="urn:Belkin:service:basicevent:1"><%s>%s</%s></u:%s>' % (method, obj, value, obj, method)

	def _send(self, method, obj, value=None):
		body_xml = self._get_body_xml(method, obj, value)
		header_xml = self._get_header_xml(method, obj)
		for port in self.ports:
			result = self.try_send(self.ip, port, body_xml, header_xml, obj)
			if result is not None:
				self.ports = [port]
			return result
		raise Exception("TimeoutOnAllPorts")

	def _extract(self, response, name):
		exp = '<%s>(.*?)<\/%s>' % (name, name)
		g = re.search(exp, response)
		if g:
			return g.group(1)
		return response


	def _try_send(self, ip, port, body, header, data):
		for attempt in range(10):
			try:
				request_body = '<?xml version="1.0" encoding="utf-8"?>'
				request_body += '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
				request_body += '<s:Body>%s</s:Body></s:Envelope>' % body
				headers = {'Content-type': 'text/xml; charset="utf-8"', 'SOAPACTION': header}
				r = requests.post('http://%s:%s/upnp/control/basicevent1' % (ip, port), data=request_body, headers=headers,timeout=4)
				sendback = self._extract(r.text, data)
				break
			except Exception as e:
				sendback =  (str(e))
		return sendback
	def try_send(self, ip, port, body, header, data):
		for attempt in range(10):
			try:
				request_body = '<?xml version="1.0" encoding="utf-8"?>'
				request_body += '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
				request_body += '<s:Body>%s</s:Body></s:Envelope>' % body
				headers = {'Content-type': 'text/xml; charset="utf-8"', 'SOAPACTION': header}
				r = requests.post('http://%s:%s/upnp/control/basicevent1' % (ip, port), data=request_body, headers=headers,timeout=5)
				if r.ok:
					return (self._extract(r.text, data))
					break
			except requests.ConnectTimeout as e:
				loggerdo.log.warning("Connection timed out, wemo ip - {}, try attempt{}".format(ip,attempt))
			except requests.ConnectionError as e:
				loggerdo.log.warning("Connection error, wemo ip - {}, try attempt{}".format(ip,attempt))
			except requests.RequestException as e:
				loggerdo.log.warning("There was an ambiguous exception that occurred, wemo ip - {}, try attempt{}".format(ip,attempt))
			except Exception as e:
				loggerdo.log.warning("Error caught in request to wemo - {}, try attempt{}".format(ip,attempt))
		loggerdo.log.warning("Did not complete the status check")
		return None

	def _extract(self, response, name):
		exp = '<%s>(.*?)<\/%s>' % (name, name)
		g = re.search(exp, response)
		if g:
			return g.group(1)
		return response



def output(message):
	print (message)



if __name__ == "__main__":
	import sys
	ip = '192.168.5.110'
	switch = wemo(ip)

	if sys.argv[-1] == "--on":
		output(switch.status())
		output(switch.on())
		output(switch.status())
	elif sys.argv[-1] == "--off":
		output(switch.status())
		output(switch.off())
		output(switch.status())
	else:
		output(switch.status())

	#output(switch.off())
	#output(switch.off())

	#output(switch.toggle())
	#output(switch.status())
