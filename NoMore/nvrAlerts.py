from libraries import loggerdo
from libraries import utils
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import json
import datetime
import time
import threading


server = "192.168.5.70"


def maketopics():
    listtopic = []
    listtopic.append(("nvr/driveway/ObjectDetector", 0))
    #listtopic.append(("nvr/driveway/motionDetected", 0))
    return listtopic

class broker:
    mqttc = None
    idLookup = None


    def __init__(self):
        self.mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        #self.mqttc = mqtt.Client()

        #self.debug = config["debug"]["mqttlistener"]
        self.mqttc.on_message = self.on_message

        self.mqttc.connect(server)
        self.mqttc.subscribe(maketopics())
        self.idLookup = {}
        self.scoreLookup = {}
        self.runcount = 0
        self.motionAlert = False
        self.motionActive = datetime.datetime.now() - datetime.timedelta(minutes=1)


        self.scoreLookup["car"] = 0.7
        self.scoreLookup["person"] = 0.2

    def manageAlert(self):
        removeList = []
        for obj in self.idLookup:
              
             # if no history updates in 30 mins, forget object
            if self.idLookup[obj]["lastSeen"] < (datetime.datetime.now() - datetime.timedelta(minutes=30)):
                removeList.append(obj)

        #clean up
        for thing in removeList:
            #print(f'remove {thing}')
            del self.idLookup[thing]

        if self.motionActive > (datetime.datetime.now() - datetime.timedelta(minutes=1)):
            if self.motionAlert == False:
                print(f'{datetime.datetime.now()} - found motion')
                self.motionAlert = True
        else:
            if self.motionAlert == True:
                print(f'{datetime.datetime.now()} - motion clear')
                self.motionAlert = False




    def on_message(self, mqttc, obj, msg):
        msgjson = json.loads(msg.payload.decode("utf-8"))
        #self.manageAlert()
        if isinstance(msgjson, dict):
            if len(msgjson["detections"]) > 0:
                for trackedObject in msgjson["detections"]:
                    # keep log of how often we look at objects
                    objdict = {}
                    #check for required fields
                    if True:
                        if "id" not in trackedObject and "className" in trackedObject:
                            if trackedObject["className"] != "motion":
                                print(f'{datetime.datetime.now()} - pass on no id, its not motion')
                                print(trackedObject)
                            continue

                        if "score" in trackedObject and "className" in trackedObject and "id" in trackedObject and "zones" in trackedObject and len(trackedObject["movement"])> 0:
                            
                            # tracking with id and firstseen
                            if trackedObject["id"] in self.idLookup:
                                objdict = self.idLookup[trackedObject["id"]]
                                objdict["count"] = objdict["count"] + 1
                                objdict["lastSeen"] = datetime.datetime.fromtimestamp(trackedObject["history"]["lastSeen"]/1000)
                                objdict["movement"].append(datetime.datetime.fromtimestamp(trackedObject["movement"]["lastSeen"]/1000))
                                objdict["zoneLog"].append(trackedObject["zones"])
                                
                            else:
                                #print(f'found new {trackedObject["className"]} with id {trackedObject["id"]}. zones {trackedObject["zones"]}, box {trackedObject["boundingBox"]}. Its - {datetime.datetime.now()}')
                                objdict["count"] = 1
                                objdict["className"] = trackedObject["className"]
                                objdict["firstSeen"] = datetime.datetime.fromtimestamp(trackedObject["history"]["firstSeen"]/1000)
                                objdict["lastSeen"] = datetime.datetime.fromtimestamp(trackedObject["history"]["lastSeen"]/1000)
                                objdict["zone"] = trackedObject["zones"]
                                objdict["zoneLog"] = [trackedObject["zones"]]
                                objdict["movement"] = [datetime.datetime.fromtimestamp(trackedObject["movement"]["lastSeen"]/1000)]
                                #log it
                                print(f'{datetime.datetime.now()} - {objdict["className"]}/{trackedObject["id"]} - new in {trackedObject["zones"]}.')

                            #bypass if zone is only all
                            if len(trackedObject["zones"]) == 1 and "All" in trackedObject["zones"]:
                                print(f'{datetime.datetime.now()} - {objdict["className"]}/{trackedObject["id"]} - skip for zone All')
                            else:
                                # update zones
                                if trackedObject["zones"] != objdict["zone"]:
                                    # see if object moved from all to property
                                    if "Property" in trackedObject["zones"] and "Property" not in objdict["zone"]:
                                        print(f'{datetime.datetime.now()} - {objdict["className"]}/{trackedObject["id"]} - moved to property.')
                                        # turn on motion if something moved from all to property
                                        self.motionActive = datetime.datetime.fromtimestamp(trackedObject["movement"]["lastSeen"]/1000)
                                        objdict["alerted"] = True
                                    else:
                                        print(f'{datetime.datetime.now()} - {objdict["className"]}/{trackedObject["id"]} - different zone change,  was {objdict["zone"]} is {trackedObject["zones"]}.')
                                    # reset object zones
                                    objdict["zone"] = trackedObject["zones"]


                                
        
                                # property should be for someone coming home
                                if "Property" in objdict["zone"]:
    
                                        historyFirstSeen = datetime.datetime.fromtimestamp(trackedObject["history"]["firstSeen"]/1000)

                                        # this is a new object, so someone pulling into driveway?
                                        if historyFirstSeen > (datetime.datetime.now() - datetime.timedelta(minutes=5)):
                                            # turn on motion if new thing is found in property
                                            print(f'{datetime.datetime.now()} - {objdict["className"]}/{trackedObject["id"]} - First seen was {historyFirstSeen} and is greater than now - 5 mins.')
                                            #turn on motion for someone new on property
                                            if trackedObject["className"] == "person":
                                                self.motionActive = datetime.datetime.fromtimestamp(trackedObject["movement"]["lastSeen"]/1000)
                                                objdict["alerted"] = True
                                       # else:
                                           # print(f'{datetime.datetime.now()} - {objdict["className"]}/{trackedObject["id"]} - First seen was {historyFirstSeen} and is less than now - 5 mins.')
        
                            #save objdict
                            self.idLookup[trackedObject["id"]] = objdict


#print(msgjson["detections"])
    def mqttrunner(self):
        self.mqttc.loop_forever()


    def run(self):
        #self.mqttc.loop_forever()
        mqttlistenthread = threading.Thread(target=self.mqttrunner)
        #mqttlistenthread.setDaemon(True)
        mqttlistenthread.daemon = True
        mqttlistenthread.start()

        runCount = 0
        while True:
            if runCount%120 == 0:
                for item in self.idLookup:
                    pass
                    #print(item, self.idLookup[item]["count"])
                #print(self.idLookup)
            self.manageAlert()
            time.sleep(1)
            runCount +=1



#(self.fanStateLastChange + datetime.timedelta(minutes=self.fanStartDelay) < datetime.datetime.now()) 
if __name__ == "__main__":
    print('needs to be imported to run')
    runner = broker()
    runner.run()

