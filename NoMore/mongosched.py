import datetime
from libraries import loggerdo
from libraries import mongo
from libraries import utils

class day:
	date = None
	config = None
	mymongo = None
	activemode = None
	override = False
	modes = []
	cal = {}
	lastupdate = None

	def __init__(self, mymongo, config):

		self.today = datetime.date.today()
		self.mydb = mymongo
		self.modes = config["modes"]
		self.purgestart = config["purgestart"]
		self.cal = {}
		self.test = config["test"]
		self.activemode = None
		self.lastupdate = datetime.datetime.now()

		# setup gettoday
		self.start()
		loggerdo.log.debug("mongosched - day object setup complete.")
		self.fanstart = config["fans"]["start"]
		self.fanend = config["fans"]["end"]

	def start(self):
		# Run when schedule is created
		# this sets up current day
		if self.purgestart and mongo.checkday(self.mydb, str(datetime.date.today())):
			loggerdo.log.debug("mongosched - {} exists in mongo, dropping day becuase purgestart is true".format(datetime.date.today()))
			mongo.dropday(self.mydb, str(datetime.date.today()))

		if not mongo.checkday(self.mydb, str(datetime.date.today())):
			loggerdo.log.debug("mongosched - No day setup for {}, building day".format(datetime.date.today()))
			for mode in self.modes:
				mode = self.modes[mode]
				self.dbload(self.mydb, mode, datetime.date.today())
		else:
			loggerdo.log.debug("mongosched - Dont do db load for {}, there is data already".format(datetime.date.today()))

		loggerdo.log.debug("mongosched - Finished setup for {}".format(datetime.date.today()))

		# build cal is done on first run and should be after db load is done.
		self.buildcal()
		# always sync
		self.synccalmode()

		# setup tomorrow now
		tomorrow = self.today + datetime.timedelta(days=1)

		if self.purgestart and mongo.checkday(self.mydb, str(tomorrow)):
			loggerdo.log.debug("mongosched - {} exists in mongo, dropping day becuase purgestart is true".format(tomorrow))
			mongo.dropday(self.mydb, str(tomorrow))

		if not mongo.checkday(self.mydb, str(tomorrow)):
			loggerdo.log.debug("mongosched - No day setup for {}, building day".format(tomorrow))
			for mode in self.modes:
				mode = self.modes[mode]
				self.dbload(self.mydb, mode, tomorrow)
		else:
			loggerdo.log.debug("mongosched - Dont do db load for today, there is data already")

		loggerdo.log.info("mongosched - Start day complete, db is configured for {} and {}".format(self.today, tomorrow))


	def startday(self):
		# gets a newday going
		loggerdo.log.info("mongosched - run time for new day setup is {}".format(str(datetime.datetime.now())))
		loggerdo.log.debug("mongosched - self.day is {}".format(self.today))
		newday = self.today + datetime.timedelta(days=1)

		loggerdo.log.debug("mongosched - newday var is, {}".format(newday))

		if self.purgestart and mongo.checkday(self.mydb, str(newday)):
			loggerdo.log.debug("mongosched - {} exists in mongo, dropping day becuase purgestart is true".format(newday))
			mongo.dropday(self.mydb, str(newday))

		if not mongo.checkday(self.mydb, str(newday)):
			loggerdo.log.debug("mongosched - No day setup for {}, building day".format(newday))
			for mode in self.modes:
				mode = self.modes[mode]
				self.dbload(self.mydb, mode, newday)
		else:
			loggerdo.log.debug("mongosched - Dont do db load for today, there is data already")

		loggerdo.log.debug("mongosched - self.day is at the end{}".format(self.today))
		# always sync
		self.synccalmode()
		loggerdo.log.info("mongosched - Start day complete, db is configured for {}".format(newday))

	# the cal is a dictonary, times to mode.
	# start with base as default
	def buildcal(self):
		loggerdo.log.debug("mongosched - Starting to build the cal")
		if len(self.cal) > 0:
			loggerdo.log.info("mongosched - self.cal has data already. Clearing it")
			self.cal.clear()

		# build cal dictonary, start of with default day
		for mode in self.modes:
			mode = self.modes[mode]
			loggerdo.log.debug("mongosched - Checking mode: {} for default".format(mode))
			if mode['default']:
				loggerdo.log.debug("mongosched - Found default, {}".format(mode['name']))
				defaultmode = mode['name']
				y = 0
				while y < 24:
					self.cal.update({y: defaultmode})
					y += 0.5
				break

		loggerdo.log.debug("mongosched - Built default mode, adding others.")
		# add schedule dictonary
		for mode in self.modes:
			mode = self.modes[mode]
			if mode['scheduled']:
				loggerdo.log.debug("mongosched - Setting up mode, {}".format(mode["name"]))
				scheduledmode = mode['name']
				start = mode['start']
				end = mode['end']
				if end - start < 0:
					# start and end cross midnight. Split up
					loggerdo.log.info("mongosched - start and end cross midnight. Splitting up {}".format(scheduledmode))
					while start < 24:
						self.cal.update({start: scheduledmode})
						start += 0.5
					z = 0
					while z < end:
						self.cal.update({z: scheduledmode})
						z += 0.5
				else:
					# start and end do not corss midnight
					loggerdo.log.info("mongosched - start and end are on same day for {}".format(scheduledmode))
					while start <= end:
						self.cal.update({start: scheduledmode})
						start += 0.5

	def dbload(self, mydb, mode, day):

		if 'scheduled' in mode:
			scheduled = mode['scheduled']
		else:
			scheduled = False

		if 'default' in mode:
			default = True
		else:
			default = False

		if 'start' in mode:
			start = mode['start']
			end = mode['end']
		else:
			start = False
			end = False

		name = mode['name']
		base = mode['temp']
		high = base + mode['up']
		low = base - mode['down']
		down = mode['down']

		x = 0
		while x < 24:
			mongo.loaddailysched(self.mydb, name, str(day), x, base, high, low, scheduled, default, start, end)
			x += 0.5

	def pullhourdetails(self, hour, mode=None):
		if not isinstance(hour, float):
			hour = utils.timefloor(hour)

		day = datetime.date.today()
		# check if I am looking for a specific mode, if not pull active mode in.

		#loggerdo.log.debug("mongosched - mode before if is: {}".format(mode))
		if not mode:
			mode = self.activemode
			loggerdo.log.debug("mongosched - mode not set for pullhourdetails, using current : {}".format(self.activemode))

		hourdetails = mongo.pullhour(self.mydb, str(day), hour, mode)

		if hourdetails.count() > 1:
			loggerdo.log.debug("mongosched - Thats pullhourdetails - returned to many items")
			loggerdo.log.debug("mongosched - pullhourdetail:")
			loggerdo.log.debug("mode = {}".format(mode))
			loggerdo.log.debug("hour = {}".format(hour))
			loggerdo.log.debug("day = {}".format(day))
			return None, None, None
		elif hourdetails.count() == 0:
			loggerdo.log.debug("mongosched - pullhourdetails - returned no items")
			loggerdo.log.debug("mongosched - pullhourdetail:")
			loggerdo.log.debug("mode = {}".format(mode))
			loggerdo.log.debug("hour = {}".format(hour))
			loggerdo.log.debug("day = {}".format(day))
			return None, None, None
		else:
			for item in hourdetails:
				if self.test:
					print(item)
				return item['base'], item['high'], item['low']

	def getmode(self):
		hourfloat = utils.timefloor(datetime.datetime.now())
		return self.cal[hourfloat]


	def synccalmode(self):
		now = datetime.datetime.now()
		hourfloat = utils.timefloor(now)
		if not self.override:
			loggerdo.log.debug("mongosched - Doing a sync Cal Mode")
			if self.activemode != self.cal[hourfloat]:
				loggerdo.log.info("mongosched - synccalmode - Changing mode from, {} to {}".format(self.activemode, self.cal[hourfloat]))
				self.activemode = self.cal[hourfloat]
				# Need to update lastupdate timestamp to notify adaio that a change occured from this end
				self.lastupdate = datetime.datetime.now()
		else:
			loggerdo.log.debug("mongosched - Skippoing eval because override is set")

	# turn override off and go back to scheduled mode
	def disableoveride(self):
		self.override = False
		self.synccalmode()

	# override schedule, or scheduled change
	def changemode(self, newmode, override=False):
		if override:
			self.override = True
			loggerdo.log.info("mongosched - Mode changing is off due to override")

		for mode in self.modes:
			mode = self.modes[mode]
			if newmode == mode['name']:
				loggerdo.log.info("mongosched - changemode -  Changing mode from, {} to {}".format(self.activemode, newmode))
				self.activemode = newmode
				# Need to update lastupdate timestamp to notify adaio that a change occured from this end
				self.lastupdate = datetime.datetime.now()


	def fantime(self):
		now = int(str(datetime.datetime.now().hour) + str(datetime.datetime.now().minute))
		if (now > self.fanstart) and (now < self.fanend):
			return True
		else:
			loggerdo.log.debug("mongosched - fantime - no time for fan")
			return False
			
	def gettoday(self):
		return self.today

	def checkvalid(self):
		now = datetime.date.today()
		if self.today >= now:
			return True
		else:
			loggerdo.log.debug("mongosched - day not valid, starting next day")
			self.today = self.today + datetime.timedelta(days=1)
			loggerdo.log.info("mongosched - self.day is now set to {}".format(self.today))
			return False

	def increment(self, now=datetime.datetime.now()):
		if not isinstance(now, float):
			now = utils.timefloor(now)

		# find mode that we should adjust based on schedule
		schedmode = self.cal[now]
		base, high, low = self.pullhourdetails(hour=now, mode=schedmode)
		ret = mongo.updatedailysched(self.mydb, str(self.today), now, base + 1, high + 1, low + 1, schedmode)
		if self.test:
			print(ret)
		self.lastupdate = datetime.datetime.now()

	def decrement(self, now=datetime.datetime.now()):
		if not isinstance(now, float):
			now = utils.timefloor(now)
		# find mode that we should adjust based on schedule
		schedmode = self.cal[now]
		base, high, low = self.pullhourdetails(hour=now, mode=schedmode)
		ret = mongo.updatedailysched(self.mydb, str(self.today), now, base - 1, high - 1, low - 1, schedmode)
		if self.test:
			print(ret)
		self.lastupdate = datetime.datetime.now()

	def updatebasetemp(self, now, temp, duration=3):
		if not isinstance(now, float):
			now = utils.timefloor(now)

		base, high, low = self.pullhourdetails(now)
		up = high - base
		down = base - low

		loggerdo.log.debug("mongosched - setting temp to {}, starting at time {}".format(temp, now))

		loggerdo.log.debug("mongosched - Base temp was, {}".format(base))

		high = (high - base) + temp
		low = temp - (base - low)
		end = now + duration

		while now < end:
			loggerdo.log.debug("mongosched - updating hour {}, setting base to {}".format(now, temp))
			if now > 23.5:
				break
			schedmode = self.cal[now]
			ret = mongo.updatedailysched(self.mydb, str(self.today), now, temp, high, low, schedmode)
			if self.test:
				print(ret)
			now += .5
		self.lastupdate = datetime.datetime.now()

	def websched(self, starthour=datetime.datetime.now(), dur=4):
		if not isinstance(starthour, float):
			now = utils.timefloor(starthour)
		else:
			now = starthour
		ret = {}
		until = now + dur
		while now < until:
			# lookup what mode we should be checking returns name
			if now > 23.5:
				break
			schedmode = self.cal[now]
			base, high, low = self.pullhourdetails(hour=now, mode=schedmode)
			ret.update({now: base})
			now += 0.5

		return ret

	# Written specifically for control.py
	def pullpartsched(self, now=datetime.datetime.now()):
		if not isinstance(now, float):
			now = utils.timefloor(now)

		msg = '\n'
		until = now + 3

		while now < until:
			if now > 23.5:
				break
			schedmode = self.cal[now]
			base, high, low = self.pullhourdetails(hour=now, mode=schedmode)
			msg = msg + ("Hour-{} has high of {} and low of {}\n".format(now, high, low))
			now += 0.5

		return msg

	def dumpsched(self):
		scheddump = {}

		start = 0
		while start < 24:
			schedmode = self.cal[start]
			scheddump.update({start: schedmode})
			start += 0.5

		return scheddump

	def getlastupdate(self):
		return self.lastupdate


if __name__ == '__main__':
	import pymongo
	from libraries import utils
	config = utils.loadconfig('config.yaml')
	myclient = pymongo.MongoClient("mongodb://localhost:27017/")
	mymongo = myclient["burrow"]
	now = datetime.datetime.now()

	today = day(mymongo, config)
	print("try to get cal")
	print(today.cal)
	print("missed cal")

	ret = today.websched()
	for key, val in ret.items():
		print(f"hour is {key}, and temp is {val}")
	today.updatebasetemp(datetime.datetime.now(), 85)
	ret = today.websched()
	for key, val in ret.items():
		print(f"hour is {key}, and temp is {val}")
	print("part sched")
	print(today.pullpartsched())
	today.increment()
	print(today.pullpartsched())
	today.decrement()
	print(today.pullpartsched())
