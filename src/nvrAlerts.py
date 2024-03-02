from libraries import loggerdo
from libraries import utils
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import json
import datetime
import time


server = "192.168.5.70"


def maketopics():
    listtopic = []
    listtopic.append(("nvr/driveway/ObjectDetector", 0))
    #listtopic.append(("nvr/driveway/motionDetected", 0))
    return listtopic

class broker:
    mqttc = None


    def __init__(self):
        self.mqttc = mqtt.Client()

        #self.debug = config["debug"]["mqttlistener"]
        self.mqttc.on_message = self.on_message

        self.mqttc.connect(server)
        self.mqttc.subscribe(maketopics())



    def on_message(self, mqttc, obj, msg):
        device = msg.topic.split("/")
        msgsplit = msg.topic.split("/")
        msgjson = json.loads(msg.payload.decode("utf-8"))
        if isinstance(msgjson, dict):
            if len(msgjson["detections"]) > 0:
                print()
                for trackedObject in msgjson["detections"]:
                    print("loop")
                    if "score" in trackedObject: 
                        if trackedObject["score"] > .7:
                            # looks solid
                            if "className" in trackedObject and "id" in trackedObject:
                                print(trackedObject["className"],trackedObject["id"])
                            if "zones" in trackedObject:
                                if "Property" in trackedObject["zones"]:
                                    print('property thing')
                                    continue
                                else:
                                    print('not property thing')

                            if "history" in trackedObject:
                                firstSeen = datetime.datetime.fromtimestamp(trackedObject["history"]["firstSeen"]/1000)
                                lastSeen = datetime.datetime.fromtimestamp(trackedObject["history"]["lastSeen"]/1000)
                                print(f"firstseen - {firstSeen}")
                                print(f"lastSeen - {lastSeen}")
                       
                  
                            if "movement" in trackedObject:
                                print("movement")
                                print(trackedObject["movement"])
                            print(trackedObject)
                print('loop done')
                print(msgjson["detections"])

    
    def run(self):
        self.mqttc.loop_forever()



if __name__ == "__main__":
    print('needs to be imported to run')
    runner = broker()
    runner.run()
