import controller
import schedule
import MQTTlistener
import thermometer
import house
from libraries import loggerdo, utils
import datetime
import time
import threading
import base64
import meross


def run():

    
    while not ourhome.getinitialize():
        loggerdo.log.info("goBurrow - sensors have not yet been initalized yet, starting")
        ourhome.initializesensor()
        
    loggerdo.log.info("goBurrow - initializing sensors completed")                    
    while True:
        # update
        dayschedule.checkvalid()
        # Run eval before updates
        burrow.houseEval()
        time.sleep(3)


def runmqttlistenbroker():
    mqttlistener.run()

def runmqttthermometerbroker():
    mqttthermometer.run()

def makebase64(file):
    with open(file, 'rb') as binary_file:

        binary_file_data = binary_file.read()
        base64_encoded_data = base64.b64encode(binary_file_data)
        base64_message = base64_encoded_data.decode('utf-8')
        return base64_message

def runmeross(switches, mqttserver):
    merossswitcharray = []

    for switch in switches:
        merossswitcharray.append(meross.merossswitch(IP=switches[switch]['ip'], Name=switches[switch]['name'],
                                            mqttserver=mqttserver, managed=True,
                                            zone=0, AC=False))
    while True:
        for msw in merossswitcharray:
            ret=msw.getstate()
        time.sleep(10)

def main(importedconfig):
    global config, test
    global ourhome, dayschedule, burrow, mqttlistener, mqttthermometer

    config = importedconfig

    test = config["test"]

    myclient = None

    ourhome = house.home(config)

    dayschedule = schedule.day(config)

    burrow = controller.Burrow(ourhome, dayschedule, config)

  
    mqttlistener = MQTTlistener.broker(house=ourhome, burrow=burrow, schedule=dayschedule,
                               config=config)
    
    mqttthermometer = thermometer.broker(house=ourhome, config=config)
    #controlthread = threading.Thread(target=controlchanges)
    #controlthread.setDaemon(True)
    #controlthread.start()

    mqttlistenthread = threading.Thread(target=runmqttlistenbroker)
    mqttlistenthread.setDaemon(True)
    mqttlistenthread.start()

    mqttthermometerthread = threading.Thread(target=runmqttthermometerbroker)
    mqttthermometerthread.setDaemon(True)
    mqttthermometerthread.start()

    run()


if __name__ == "__main__":
    print('needs to be imported to run')
