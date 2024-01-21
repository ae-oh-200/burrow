from libraries import loggerdo
import libraries
import requests
import datetime




#Would like humidity and temperature to return as 1 get request


class thermometer:
    zone = None
    temp = None
    lasttemp = None
    humidity = None
    lasthumidity = None
    lastupdate = None
    weight = None
    test = None

    def __init__(self, zone, weight, topic, test = False):
        self.zone = zone
        self.weight = weight
        self.topic = topic
        self.test = test
        self.lastupdate = datetime.datetime.now()

    def settemp(self, temp):
        self.lasttemp = self.temp
        self.temp = temp
        self.lastupdate = datetime.datetime.now()

    def sethumidity(self, humidity):
        self.lasthumidity = self.humidity
        self.humidity = humidity
        self.lastupdate = datetime.datetime.now()

    def gettemp(self):
        return self.temp

    def gethumidity(self):
        return self.humidity

    def getzone(self):
        return self.zone

    def gettopic(self):
        return self.topic

    def getweight(self):
        return self.weight

if __name__ == "__main__":
    temp = thermometer(local=False, zone = 1, ip='192.168.5.52', port='6969', weight=25)
    print(temp.getremotetemp())
    print(temp.getzone())
    temp = thermometer(local=False, zone = 1, ip='192.168.5.52', port='6969', weight = 75)
    print(temp.getremotetemp())
    print(temp.getzone())
    print(temp.gethumidity())

