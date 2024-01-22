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




    def __init__(self, nickname, houseweight, zoneweight, topic, address, debug, addresstype, zone, temperatureavail, humilityavail):
        self.zone = zone
        self.houseweight = houseweight
        self.zoneweight = zoneweight
        self.topic = topic
        self.nickname = nickname
        self.addrees = address
        self.addresstype = addresstype
        self.temperatureavail = temperatureavail
        self.humilityavail = humilityavail
        self.humidity = 0
        self.temp = 0
        self.debug = debug


    def settemp(self, temp):
        # block large swings
        if (temp > (self.temp - (self.temp * 0.20))) or self.temp == 0:
            self.lasttemp = self.temp
            self.temp = temp
            self.lasttempupdate = datetime.datetime.now()
            if self.debug:
                loggerdo.log.info("housemqtt - sensor - setting {} temperature to {}, Time is = {}".format(self.topic, temp, time))
            return True
        else:
            if self.debug:
                loggerdo.log.info('housemqtt - sensor - not setting temp for {} because its out of range, current: {} new: {}'.format(self.topic, self.temp, temp))
            return False

    def sethumidity(self, humidity):
        if self.debug:
            loggerdo.log.info("housemqtt - sensor - Doing a set humidity inside {} for sensor {}".format(self.nickname, self.gettopic()))
        self.lasthumidity = self.humidity
        self.humidity = humidity
        self.lasthumidityupdate = datetime.datetime.now()
        return True

    def gettemp(self):
        if not self.lasttempupdate:
            return None
        elif self.lasttempupdate > datetime.datetime.now() - datetime.timedelta(minutes=15):
            return self.temp
        else:
            loggerdo.log.info("housemqtt - sensor -  Data from {} is to old to use, last update was - {}".format(self.topic, self.lasttempupdate))
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


class home:
    outsidetemp = None
    houseavgtemp = None
    outsidetemplimit = None


    houseavgtempfail = 0
    initializecomplete = None

    #new
    burrowsensors = None

    debug = None



    def __init__(self, config):
        self.config = config
        self.debug = config["debug"]["house"]
        self.burrowsensors = self.setupsensors(config['rooms'])
        self.initializecomplete = False


    def setupsensors(self, rooms):
        loggerdo.log.info("housemqtt - house - setting up sensors")
        sensorarray = []
        totalweight = 0

        for sensors in rooms:

            sensorarray.append(sensor(nickname=rooms[sensors]['nickname'], zoneweight=rooms[sensors]['zoneweight'], houseweight=rooms[sensors]['houseweight'],
                                      topic=rooms[sensors]['topic'], address=rooms[sensors]['address'], addresstype= rooms[sensors]['address-type'],
                                      debug=self.debug, zone=rooms[sensors]['zone'],
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
            loggerdo.log.info("housemqtt - house - Trying to initialize sensors. Total sensors = {}".format(len(self.burrowsensors)))
            if runtotal > 30:
                raise SystemExit("Failed to initialize sensors")
            for sensor in self.burrowsensors:
                if sensor.gettemp() != None:
                    loggerdo.log.info("housemqtt - house - Initialize is complete, found temp with - {}".format(sensor.getnickname()))
                    self.initializecomplete = True
                    break
            runtotal += 1
            time.sleep(5)

    def udatesensortemp(self, topic, ftemp):
        for themometer in self.burrowsensors:
            if themometer.gettopic() == topic:
                # Becuase of the way posting data is written I must submit something for null values.
                # Check to make sure submitted data is above 0
                tret = themometer.settemp(ftemp)
                if not tret:
                    loggerdo.log.debug(
                        "housemqtt - setting {} temp to {} was NOT sucessful".format(themometer.gettopic(), ftemp))
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

                if not tret:
                    loggerdo.log.debug(
                        "housemqtt - setting {} humidity to {} was NOT sucessful".format(themometer.gettopic(), humidity))
  
                return tret
        # did not locate sensor to update
        return False

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
            if sensor.gettemp() is None:
                fail +=1
                loggerdo.log.info(f"housemqtt - house - Error in sensor {sensor.topic}")
        if fail > (total/2):
            loggerdo.log.info(f'housemqtt - getsenseorhealth - to many offline sensors, {fail}')
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


