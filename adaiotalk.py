from libraries import loggerdo, getruntime
import datetime
from Adafruit_IO import Client, errors

class iotalk:
	mydb= None
	home = None
	burrow = None
	schedule = None
	config = None
	aio = None
	heatbump = None
	burrowfeedaio = None
	heaterfeedaio = None
	tempfeedio = None
	textfeedio = None
	housefeedio = None
	historyio = None
	timerfeedio = None

	#specific onand off keepers
	burrowadaconnect = None
	heateradaconnect = None
	tempadaconnect = None
	highlowconnect = None
	houseconnect = None
	historyconenct = None
	textconnect = None
	timerconnect = None

	#random toggle stuff
	heatersetup = None

	#time stuff
	tempupdatetime = None


	def __init__(self, home, schedule, burrow, config, mydb, heatbump):
		self.home = home
		self.burrow = burrow
		self.schedule = schedule
		self.config = config["adafruitio"]
		self.mydb = mydb
		self.heatbump = heatbump

		self.aio = Client(self.config['username'], self.config['key'])

	def setup(self):

		if self.config["burrow"]["enabled"]:
			loggerdo.log.info("start adafruit burrow thread")
			# setup and assign feed
			self.burrowfeedaio = self.aio.feeds(self.config["burrow"]["key"])

			# send first data
			loggerdo.log.debug("Send first state to adaIO, then update statelastupdate to + 5 secs")
			self.sendtoada(self.burrowfeedaio, self.burrow.getburrowstatus())

			self.burrow.statelasteupdate = datetime.datetime.now() + datetime.timedelta(seconds=5)
			# assign funciton to thread

			self.burrowadaconnect = True

		if self.config["heater"]["enabled"]:
			loggerdo.log.info("start adafruit heater thread")
			self.heaterfeedaio = self.aio.feeds(self.config["heater"]["key"])

			#check to see if heater was setup yet by the mqttbroker
			if self.burrow.getheaterlastupdate():
				loggerdo.log.debug("adaiotalk - Send first state of {} to adaIO for heater, then update statelastupdate to + 5 secs".format(self.burrow.getheatstatus()))

				self.sendtoada(self.heaterfeedaio, self.burrow.getheatstatus())
				self.burrow.heaterlastupdate = datetime.datetime.now() + datetime.timedelta(seconds=5)
				self.heatersetup = True
			else:
				loggerdo.log.debug("adaiotalk - getheaterlastupdate is now set, so skipping")

			self.heateradaconnect = True

		if self.config['temp']['enabled']:

			loggerdo.log.info("start adafruit temp update thread")
			self.tempfeedio = self.aio.feeds(self.config["temp"]["key"])
			#get first data
			base, schedhigh, schedlow = self.schedule.pullhourdetails(datetime.datetime.now())
			#send first value
			self.aio.send_data(self.tempfeedio.key, base)
			self.tempupdatetime = datetime.datetime.now() + datetime.timedelta(seconds=5)

			self.tempadaconnect = True

		if self.config['text']['enabled']:

			#setup text

			self.textfeedio = self.aio.feeds(self.config["text"]["key"])
			self.textconnect = True

			self.sendtext()



		if self.config["house"]["enabled"]:
			self.housefeedio = self.aio.feeds(self.config["house"]["key"])
			self.houseavg()

		if self.config["history"]['enabled']:
			self.historyio = self.aio.feeds(self.config["history"]["key"])


		if self.config['timer']['enabled']:
			self.timerfeedio = self.aio.feeds(self.config['timer']['key'])

	def burrowupdater(self):
		# what feedname

		aiostate = None
		loggerdo.log.info("adaiotalk - Pulling data from adaIO -  burrow")

		# grab data
		try:
			data = self.aio.receive(self.burrowfeedaio.key)
		except errors.RequestError:
			loggerdo.log.debug("adaiotalk - ERROR inside heaterupdater. RequestError triggered", exc_info=True)
			pass
		except ConnectionError:
			loggerdo.log.debug("adaiotalk - ConnectionError inside heaterupdater.", exc_info=True)
			pass
		except OSError:
			loggerdo.log.debug("adaiotalk - OSError inside heaterupdater.", exc_info=True)
			pass
		except Exception:
			loggerdo.log.debug("adaiotalk - Exception inside heaterupdater.", exc_info=True)
			pass

		else:
			if data.value == 'ON':
				aiostate = True
			else:
				aiostate = False

			if aiostate != self.burrow.getburrowstatus():
				# change detected, looking for source.

				dt = datetime.datetime.strptime(data.updated_at, "%Y-%m-%dT%H:%M:%S%z")
				dt = dt.replace(tzinfo=datetime.timezone.utc).astimezone(tz=None)
				dt = dt.replace(tzinfo=None)
				if self.burrow.statelasteupdate < dt:
					# change from adaio is newer
					loggerdo.log.debug("adatalk - change to burrow from adaio. change state to {}".format(aiostate))
					self.burrow.burrowstatus(aiostate)
				else:
					loggerdo.log.debug("adatalk - change from Burrow to adaio - set burrow to {}".format(self.burrow.getburrowstatus()))
					self.sendtoada(key=self.burrowfeedaio, value=self.burrow.getburrowstatus())
				# unsure if this needs to done
				# self.statelasteupdate = datetime.datetime.now() + datetime.timedelta(seconds=5)

	def heatupdater(self):
		# what feedname
		if self.heatersetup:
			aiostate = None
			loggerdo.log.info("adaiotalk - Pulling data from adaIO -  heater")

			# grab data
			try:
				data = self.aio.receive(self.heaterfeedaio.key)
			except errors.RequestError:
				loggerdo.log.debug("adaiotalk - ERROR inside heaterupdater. RequestError triggered", exc_info=True)
				pass
			except ConnectionError:
				loggerdo.log.debug("adaiotalk - ConnectionError inside heaterupdater.", exc_info=True)
				pass
			except OSError:
				loggerdo.log.debug("adaiotalk - OSError inside heaterupdater.", exc_info=True)
				pass
			except Exception:
				loggerdo.log.debug("adaiotalk - Exception inside heaterupdater.", exc_info=True)
				pass

			else:
				if data.value == 'ON' or data.value == 1:
					aiostate = True
				else:
					aiostate = False

				dt = datetime.datetime.strptime(data.updated_at, "%Y-%m-%dT%H:%M:%S%z")
				dt = dt.replace(tzinfo=datetime.timezone.utc).astimezone(tz=None)
				dt = dt.replace(tzinfo=None)
				if aiostate != self.burrow.getheatstatus():
					loggerdo.log.debug("adatalk - aio heat and burrow are out of sync")
					if self.burrow.heaterlastupdate < dt:
						# change from adaio is newer
						if aiostate:
							#self.burrow.heaton(force=True)
							loggerdo.log.debug("adatalk - change from adaio, heat on")
							self.schedule.updatebasetemp(now=datetime.datetime.now(), temp=self.heatbump, duration=1)
							if not self.burrow.eval():
								loggerdo.log.debug("adatalk - set heat back to off because heatbump not enough")
								self.sendtoada(key=self.heaterfeedaio, value=self.burrow.getheatstatus())
						else:
							loggerdo.log.debug("adatalk - change from adaio, heat off")
							self.burrow.heatoff(force=True)
							# Do a timer to prevent auto restart, currently set for 45 minutes
							loggerdo.log.debug("adatalk - setting a 45 minute timer")
							self.burrow.starttimer(45)
					else:
						#change came from local
						loggerdo.log.info("adatalk - change from burrow to adaio, heat {}".format(self.burrow.getheatstatus()))
						self.sendtoada(key=self.heaterfeedaio, value=self.burrow.getheatstatus())
						#if self.burrow.getheatstatus():
							#self.sendtoada(key=self.heaterfeedaio, value=1)
						#else:
							#self.sendtoada(key=self.heaterfeedaio, value=0)

				# unsure if this needs to done
				# self.statelasteupdate = datetime.datetime.now() + datetime.timedelta(seconds=5)

		elif self.burrow.getheaterlastupdate():
			#check to see if heater was setup yet by the mqttbroker
			loggerdo.log.debug("adaiotalk - not in setup - Send first state of {} to adaIO for heater, then update statelastupdate to + 5 secs".format(self.burrow.getheatstatus()))
			self.sendtoada(self.heaterfeedaio, self.burrow.getheatstatus())
			self.burrow.heaterlastupdate = datetime.datetime.now() + datetime.timedelta(seconds=5)
			self.heatersetup = True
		else:
			loggerdo.log.debug("adaiotalk - getheaterlastupdate is stil not set, so skipping")

	def tempupdater(self):

		loggerdo.log.info("adaiotalk - Pulling data from adaIO -  temps")
		#pull schedule data
		base, schedhigh, schedlow = self.schedule.pullhourdetails(datetime.datetime.now())
		# grab data on the iodash
		try:
			data = self.aio.receive(self.tempfeedio.key)
		except errors.RequestError:
			loggerdo.log.debug("adaiotalk - ERROR inside heaterupdater. RequestError triggered", exc_info=True)
			pass
		except ConnectionError:
			loggerdo.log.debug("adaiotalk - ConnectionError inside heaterupdater.", exc_info=True)
			pass
		except OSError:
			loggerdo.log.debug("adaiotalk - OSError inside heaterupdater.", exc_info=True)
			pass
		except Exception:
			loggerdo.log.debug("adaiotalk - Exception inside heaterupdater.", exc_info=True)
			pass
		else:
			#fix time
			dt = datetime.datetime.strptime(data.updated_at, "%Y-%m-%dT%H:%M:%S%z")
			dt = dt.replace(tzinfo=datetime.timezone.utc).astimezone(tz=None)
			dt = dt.replace(tzinfo=None)
			# if conflict exists, find source
			if base != float(data.value):
				# Check if schedule date is older than adaio date
				if self.schedule.getlastupdate() < dt:
				#if self.burrow.heaterlastupdate < dt:
				# change from adaio is newer
					loggerdo.log.debug("adaiotalk - change detected from dashboard for temp")
					loggerdo.log.debug("adaiotalk - would update base to {}".format(data.value))
					self.schedule.updatebasetemp(now=datetime.datetime.now(), temp=float(data.value), duration=1)
					self.tempupdatetime = datetime.datetime.now() + datetime.timedelta(seconds=5)
					self.sendtext()
				else:
					# change appears to happen locally, update adaio
					loggerdo.log.info("adaiotalk - change from burrow to adaio, set temp to {}".format(base))
					try:
						self.aio.send_data(self.tempfeedio.key, base)
					except errors.RequestError:
						loggerdo.log.debug("adaiotalk - ERROR inside heaterupdater. RequestError triggered",
						                   exc_info=True)
						pass
					except ConnectionError:
						loggerdo.log.debug("adaiotalk - ConnectionError inside heaterupdater.", exc_info=True)
						pass
					except OSError:
						loggerdo.log.debug("adaiotalk - OSError inside heaterupdater.", exc_info=True)
						pass
					except Exception:
						loggerdo.log.debug("adaiotalk - Exception inside heaterupdater.", exc_info=True)
						pass
					self.tempupdatetime = datetime.datetime.now() + datetime.timedelta(seconds=5)
					self.sendtext()

	def houseavg(self):
		try:
			self.aio.send_data(self.housefeedio.key, self.home.getweightroomavg())
		except errors.RequestError:
			loggerdo.log.debug("adaiotalk - ERROR inside heaterupdater. RequestError triggered", exc_info=True)
			pass
		except ConnectionError:
			loggerdo.log.debug("adaiotalk - ConnectionError inside heaterupdater.", exc_info=True)
			pass
		except OSError:
			loggerdo.log.debug("adaiotalk - OSError inside heaterupdater.", exc_info=True)
			pass
		except Exception:
			loggerdo.log.debug("adaiotalk - Exception inside heaterupdater.", exc_info=True)
			pass

	def sendtoada(self, key, value):
		loggerdo.log.debug("sending {}, to {}".format(key, value))
		if value:
			# update local state timer to prevent endless feedback loop
			# adding time incase clocks dont match
			try:
				self.aio.send_data(key.key, 'ON')
			except errors.RequestError:
				loggerdo.log.debug("adaiotalk - ERROR inside heaterupdater. RequestError triggered", exc_info=True)
				pass
			except ConnectionError:
				loggerdo.log.debug("adaiotalk - ConnectionError inside heaterupdater.", exc_info=True)
				pass
			except OSError:
				loggerdo.log.debug("adaiotalk - OSError inside heaterupdater.", exc_info=True)
				pass
			except Exception:
				loggerdo.log.debug("adaiotalk - Exception inside heaterupdater.", exc_info=True)
				pass

		else:
			try:
				self.aio.send_data(key.key, 'OFF')
			except errors.RequestError:
				loggerdo.log.debug("adaiotalk - ERROR inside heaterupdater. RequestError triggered", exc_info=True)
				pass
			except ConnectionError:
				loggerdo.log.debug("adaiotalk - ConnectionError inside heaterupdater.", exc_info=True)
				pass
			except OSError:
				loggerdo.log.debug("adaiotalk - OSError inside heaterupdater.", exc_info=True)
				pass
			except Exception:
				loggerdo.log.debug("adaiotalk - Exception inside heaterupdater.", exc_info=True)
				pass
		# update local state timer to prevent endless feedback loop

	def printschd(self):
		msg = ""
		# sched output format is {hourfloat:x.getbase()}
		scheddata = self.schedule.websched(datetime.datetime.now(), dur=4)

		now = datetime.datetime.now()

		for key, val in scheddata.items():

			if (key % 1) > 0:
				splited = str(key).split(".")
				dt = "{}:30".format(splited[0])
				dt = (datetime.datetime.strptime(dt, '%H:%M'))
				dt = dt.strftime("%-I:%M%p")
			else:
				key = int(key)
				dt = (datetime.datetime.strptime(str(key), '%H'))
				dt = dt.strftime("%-I:%M%p")

			msg = msg + "{},  {}\n".format(dt, val)

			now = now + datetime.timedelta(minutes=30)

		tothours, totdays = getruntime.monthltime(self.mydb, self.burrow.getmode())
		msg = msg + 'Total Usage, {}\nhours over {} days'.format(tothours, totdays)

		return msg

	def sendtext(self):
		loggerdo.log.info("adaiotalk - Sending text to adaio")
		msg = 'Current Mode: {}\n'.format(self.schedule.activemode)
		base, schedhigh, schedlow = self.schedule.pullhourdetails(datetime.datetime.now())
		msg = msg + "High - {}, Low - {}\n".format(str(schedhigh), str(schedlow))
		msg = msg + self.printschd()

		try:
			self.aio.send_data(self.textfeedio.key, msg)
		except errors.RequestError:
			loggerdo.log.debug("adaiotalk - ERROR inside heaterupdater. RequestError triggered", exc_info=True)
			pass
		except ConnectionError:
			loggerdo.log.debug("adaiotalk - ConnectionError inside heaterupdater.", exc_info=True)
			pass
		except OSError:
			loggerdo.log.debug("adaiotalk - OSError inside heaterupdater.", exc_info=True)
			pass
		except Exception:
			loggerdo.log.debug("adaiotalk - Exception inside heaterupdater.", exc_info=True)
			pass

	def sendhistory(self, data):
		try:
			self.aio.send_data(self.historyio.key, data)
		except errors.RequestError:
			loggerdo.log.debug("adaiotalk - ERROR inside heaterupdater. RequestError triggered", exc_info=True)
			pass
		except ConnectionError:
			loggerdo.log.debug("adaiotalk - ConnectionError inside heaterupdater.", exc_info=True)
			pass
		except OSError:
			loggerdo.log.debug("adaiotalk - OSError inside heaterupdater.", exc_info=True)
			pass
		except Exception:
			loggerdo.log.debug("adaiotalk - Exception inside heaterupdater.", exc_info=True)
			pass

	def publishtimer(self):
		loggerdo.log.info("adaiotalk - Pushing data to adaIO -  timer")
		# Burrow timer is dumb, if try then it will be off
		if self.burrow.timercheck():
			loggerdo.log.debug("adaiotalk - publishtimer is posting timer is off")
			self.sendtoada(key=self.timerfeedio, value=0)
		else:
			loggerdo.log.debug("adaiotalk - publishtimer is posting timer is on")
			self.sendtoada(key=self.timerfeedio, value=1)

