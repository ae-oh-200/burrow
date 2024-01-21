import occupied
import datetime
from libraries import loggerdo
from libraries import utils
import time


class sensor:
    nickname = None
    houseweight = None
    zoneweight = None
    alerter = None
    alertcount = None
    zone = None
    address = None
    addresstype = None
    temperatureavail = None
    humilityavail = None
    temp = None
    humidity = None
    lasthumidity = None
    lasttemp = None
    lasttempupdate = None
    lasthumidityupdate = None




    def __init__(self, nickname, houseweight, zoneweight, topic, alerter, address, addresstype, zone, temperatureavail, humilityavail):
        self.zone = zone
        self.houseweight = houseweight
        self.zoneweight = zoneweight
        self.topic = topic
        self.alertcount = 0
        self.nickname = nickname
        self.alerter = alerter
        self.addrees = address
        self.addresstype = addresstype
        self.temperatureavail = temperatureavail
        self.humilityavail = humilityavail
        self.humidity = 0
        self.temp = 0


    def settemp(self, temp):
        # block large swings
        if (temp > (self.temp - (self.temp * 0.20))) or self.temp == 0:
            self.lasttemp = self.temp
            self.temp = temp
            self.lasttempupdate = datetime.datetime.now()
            #loggerdo.log.debug("housemqtt - sensor - setting {} temperature to {}, Time is = {}".format(self.topic, temp, time))
            return True
        #else:
            #loggerdo.log.debug('housemqtt - sensor -  - not setting temp for {} because its out of range, current: {} new: {}'.format(self.topic, self.temp, temp))
            return False

    def sethumidity(self, humidity, time=datetime.datetime.now()):
        #loggerdo.log.debug("housemqtt - sensor - Doing a set humidity inside {} for sensor {}".format(self.nickname, self.gettopic()))
        self.lasthumidity = self.humidity
        self.humidity = humidity
        self.lasthumidityupdate = time
        return True

    def gettemp(self):
        if not self.lasttempupdate:
            return None
        if self.lasttempupdate > datetime.datetime.now() - datetime.timedelta(minutes=15):
            if self.alertcount >= 1200:
                #loggerdo.log.debug("housemqtt - sensor - {} is cleared".format(self.nickname))
                self.sendclearalert()
            self.alertcount = 0
            return self.temp
        else:
            #loggerdo.log.info("housemqtt - sensor -  Data from {} is to old to use, last update was - {}".format(self.topic, self.lasttempupdate))
            #loggerdo.log.debug("housemqtt - sensor - alertcount for {} = {}".format(self.nickname, self.alertcount))
            if self.alertcount == 1200:
                self.sendfailalert(atime=self.lasttempupdate)
            self.alertcount += 1
            return None

    def gethumidity(self):
        if self.humilityavail:
            return self.humidity
        else:
            return False

    def getzone(self):
        return self.zone

    def gettopic(self):
        return self.topic

    def getnickname(self):
        return self.nickname

    def gethouseweight(self):
        return self.houseweight

    def getzoneweight(self):
        return self.zoneweight

    def sendfailalert(self, atime):
        #loggerdo.log.debug("housemqtt - sensor - sending alert for - {}".format(self.nickname))
        subject = "{} threw an error".format(self.nickname)
        message = "last update time was {}, and it is {}".format(atime, datetime.datetime.now())
        self.alerter.shout(subject, message)

    def sendclearalert(self):
        #loggerdo.log.debug("housemqtt - sensor - sending clear for - {}".format(self.nickname))
        subject = "{} is back online".format(self.nickname)
        message = "system time is {}".format(datetime.datetime.now())
        self.alerter.shout(subject, message)

class home:
    outsidetemp = None
    houseavgtemp = None
    outsidetemplimit = None
    family = None
    pingfamily = None
    test = None

    thermlastupdate = None
    houseavgtempfail = 0
    initializecomplete = None
    ealert = None

    #new
    burrowsensors = None



    def __init__(self, config, ealert):
        self.config = config
        self.ealert = ealert
        self.test = self.config["test"]

        # setup outside temp
        #self.outsidetemp = self.fetchoutsidetemp()
        #self.outsidetemplimit = self.config["outtemplimitf"]
        # setup family for occupied
        #self.pingfamily = occupied.occupied(self.mydb, self.config["family"])

        #self.themometers = self.setupthermometers(config["remotesensors"])

        self.burrowsensors = self.setupsensors(config['rooms'])

        self.thermlastupdate = None

        self.initializecomplete = False


    def setupsensors(self, rooms):
        loggerdo.log.info("housemqtt - house - setting up sensors")
        sensorarray = []
        totalweight = 0

        for sensors in rooms:

            sensorarray.append(sensor(nickname=rooms[sensors]['nickname'], zoneweight=rooms[sensors]['zoneweight'], houseweight=rooms[sensors]['houseweight'],
                                      topic=rooms[sensors]['topic'], address=rooms[sensors]['address'], addresstype= rooms[sensors]['address-type'],
                                      alerter=self.ealert, zone=rooms[sensors]['zone'],
                                      temperatureavail=rooms[sensors]['temperatureavail'], humilityavail=rooms[sensors]['temperatureavail']))

            houseweight = totalweight + rooms[sensors]['houseweight']
            loggerdo.log.info("housemqtt - house - Adding sensor {}".format(rooms[sensors]['nickname']))

        if houseweight > 100:
            #loggerdo.log.debug('housemqtt - house - temp houseweights are more than 100, failing')
            raise SystemExit(f"totalweight = {totalweight}")
        return sensorarray


    def initializesensor(self):
        #loggerdo.log.debug("housemqtt - house - Initialize sensors starting now")
        # need at least 1 sensor to work
        runtotal = 0
        foundtemp = False

        while not self.initializecomplete:
            loggerdo.log.info("housemqtt - house - Trying to initialize sensors. Total senors = {}".format(len(self.burrowsensors)))
            if runtotal > 30:
                raise SystemExit("Failed to initialize sensors")
            for sensor in self.burrowsensors:
                if sensor.gettemp() != None:
                    loggerdo.log.info("housemqtt - house - Initialize is checking sensors {}".format(sensor.getnickname()))
                    self.initializecomplete = True
                    break
            runtotal += 1
            time.sleep(5)

    def udatesensortemp(self,topic, ftemp):
        for themometer in self.burrowsensors:
            if themometer.gettopic() == topic:
                # Becuase of the way posting data is written I must submit something for null values.
                # Check to make sure submitted data is above 0
                tret = themometer.settemp(ftemp)
                #if tret:
                    #loggerdo.log.debug("housemqtt - setting {} temp to {} was sucessful".format(themometer.gettopic(), ftemp))
                #else:
                    #loggerdo.log.debug(
                     #   "housemqtt - setting {} temp to {} was NOT sucessful".format(themometer.gettopic(), ftemp))
                return tret
        # did not locate sensor to update
        return False

    def udatesensorhumidity(self,topic, humidity):
        for themometer in self.burrowsensors:
            if themometer.gettopic() == topic:
                # Becuase of the way posting data is written I must submit something for null values.
                # Check to make sure submitted data is above 0
                if humidity > 0:
                    tret = themometer.sethumidity(humidity)

                #if tret:
                #    loggerdo.log.debug("housemqtt - setting {} humidity to {} was sucessful".format(themometer.gettopic(), humidity))
                #else:
                #    loggerdo.log.debug(
                #        "housemqtt - setting {} humidity to {} was NOT sucessful".format(themometer.gettopic(), humidity))
                return tret
        # did not locate sensor to update
        return False


    def updatesensor(self, topic, data):
        for themometer in self.burrowsensors:
            if themometer.gettopic() == topic:
                # Becuase of the way posting data is written I must submit something for null values.
                # Check to make sure submitted data is above 0
                if data["temperature"] > 40:
                    tret = themometer.settemp(data["temperature"], data["time"])
                else:
                    loggerdo.log.debug("housemqtt - house - data for {} is very bad - {}".format(themometer.gettopic(), data["temperature"]))
                    tret = False

                if data["humidity"] > 0:
                    themometer.sethumidity(data["humidity"], data["time"])
                    #loggerdo.log.debug(
                    #    "housemqtt - house - setting {} humidity to {}".format(themometer.getnickname(), data["humidity"]))

                return tret
                # going to stop logging to mongo
                # mongo.logtemp(self.mydb, themometer.getnickname(), data["temperature"], False, themometer.getweight(), data["humidity"])

    def getweighthouseavg(self):
        return self.getweightedavg(self.burrowsensors, zone=False)

    def getzonetemp(self, zone):
        # go through sensors
        zonesensor = []
        for sensor in self.burrowsensors:
            #loggerdo.log.debug("housemqtt - house - compare {} to {}".format(sensor.getzone(), zone))
            if sensor.getzone() == zone:
                zonesensor.append(sensor)
        if len(zonesensor) > 0:
            #loggerdo.log.debug("housemqtt - house - found {} sensors in zone {}".format(len(zonesensor), zone))
            return self.getweightedavg(zonesensor, zone=True)
        #else:
            #loggerdo.log.debug("housemqtt - house - big error, unable to find any sensors in zone {}".format(zone))

    def getsenseorhealth(self):

        total = len(self.burrowsensors)
        fail = 0
        for sensor in self.burrowsensors:
            if sensor.alertcount > 10:
                fail +=1
        if fail > (total/2):
            #loggerdo.log.debug(f'housemqtt - getsenseorhealth - to many offline sensors, {fail}')
            return False

        else:
            return True

    def getweightedavg(self, sensorinput, zone=False):
        #loggerdo.log.debug("housemqtt - house - getweightedavg running with zone flag set to {}".format(zone))
        #loggerdo.log.debug("housemqtt - house - Total incoming sensors is {}".format(len(sensorinput)))
        sum = 0
        weights = 0
        # Generates weighted average assuming all sensors onlinee
        for sensor in sensorinput:
            if sensor.gettemp() != None:
                if zone:
                    sensorweight = sensor.getzoneweight()
                else:
                    sensorweight = sensor.gethouseweight()
                weights += sensorweight
                sum += sensor.gettemp() * (sensorweight / 100)
                #loggerdo.log.debug("housemqtt - house - {} returned {} - getweightedroomavg".format(sensor.getnickname(),
                #                                                        sensor.gettemp()))
        if weights == 0:
            # No sensors in zone responding, return nothing
            return False
        #loggerdo.log.debug("housemqtt - house - completed weighted average. weights at {}".format(weights))
        # check if all sensors returned data, if not rebalance
        if weights <= 99:
            loggerdo.log.debug(
                "housemqtt - house - downgrade from weighted average to rebalanced because unbalanced weight is = {}".format(
                    weights))
            oldweighttotal = weights
            weighttotal = 0
            weights = 0
            sum = 0

            for sensor in sensorinput:
                if sensor.gettemp() != None:
                    if zone:
                        sensorweight = sensor.getzoneweight()
                    else:
                        sensorweight = sensor.gethouseweight()
                    weights = (sensorweight * 100) / oldweighttotal
                    sum += sensor.gettemp() * (weights / 100)
                    weighttotal += weights
                    loggerdo.log.debug(f'housemqtt - house - getweightedavg {sensor.getnickname()} has workingweight of {weights}')
                    #loggerdo.log.debug(f'housemqtt - house - getweightedavg fixed the working sum . {sum}')

            # check the work
            if weighttotal != 100:
                #loggerdo.log.debug('housemqtt - house - weights` do not add up to 100, ignoring weights and using basic average')
                sum = 0
                size = 0
                for sensor in sensorinput:
                    if sensor.gettemp() != None:
                        sum += sensor.gettemp()
                        size += 1
                if size > 0:
                    avg = truncate(sum / size, 2)
                    #loggerdo.log.debug('housemqtt - house - returning basic average, not using weights.')
                    return avg
                else:
                    #loggerdo.log.debug('housemqtt - house - getweightedavg - out of ways to try and average temps, failing ')
                    raise SystemExit(f"weighttotal = {weighttotal}")
            else:
                return truncate(sum, 2)
        else:
            #loggerdo.log.debug("housemqtt - house - getweightedavg - weighted room avg went smooth, returning {}".format(truncate(sum, 2)))
            return truncate(sum, 2)


    def gethightemp(self):
        temp = 0
        #for themometer in self.themometers:
        for sensor in self.burrowsensors:
            if sensor.gettemp() != None:
                if (sensor.gettemp() > temp) and (sensor.houseweight > 0):
                    temp = sensor.gettemp()
        return temp

    def gethousehumidity(self):
        # returns fake temp instead of real if
        #loggerdo.log.debug("housemqtt - house - pulling whole house humidity")
        sum = 0
        size = 0
        for sensor in self.burrowsensors:
            if sensor.gethumidity():
                sum += sensor.gethumidity()
                size += 1
        if size > 0:
            avg = truncate(sum/size,2)
            return avg
        else:
            return 0

    def getlowtemp(self):
        temp = self.getweightroomavg()
        #for themometer in self.themometers:
        for sensor in self.burrowsensors:
            if sensor.gettemp() != None:
                if (sensor.gettemp() < temp) and ((temp / 1.05) < sensor.gettemp()):
                    temp = sensor.gettemp()
                    #loggerdo.log.debug("housemqtt - house - {} returned {} - getlowtemp".format(sensor.getnickname(), sensor.gettemp()))
        return temp

    def getinitialize(self):
        return self.initializecomplete

    #def checkanyonehome(self):
        # if self.pingfamily.anyonehome():
    #    if self.pingfamily.anyonehome():
    #        return True
    #    else:
    #        return False

    def getzones(self):
        zones = []
        for sensor in self.burrowsensors:
            if not sensor.getzone() in zones:
                zones.append(sensor.getzone())
        if zones == 0:
            print('issue finding list of zones')
        return zones

    def getzonename(self, zone):
        #loggerdo.log.debug("housemqtt - house - getting name for zone {}".format(zone))
        for sensor in self.burrowsensors:
            if sensor.zone == zone:
                return sensor.getnickname()



def truncate(n, decimals=0):
    multiplier = 10 ** decimals
    return int(n * multiplier) / multiplier

