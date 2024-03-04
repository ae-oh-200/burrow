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

        #self.debug = config["debug"]["mqttlistener"]
        self.mqttc.on_message = self.on_message

        self.mqttc.connect(server)
        self.mqttc.subscribe(maketopics())
        self.idLookup = {}
        self.firstseenLoopup = {}
        self.scoreLookup = {}
        self.isMoving = {}
        self.runcount = 0
        self.motionAlert = {}
        self.motionActive = datetime.datetime.now() - datetime.timedelta(minutes=1)


        self.scoreLookup["car"] = 0.7
        self.scoreLookup["person"] = 0.2

    def manageAlert(self):
        removeList = []
        
        for thing in removeList:
            del self.motionAlert[thing]
        removeList = []
        for thing in self.isMoving:
            if self.isMoving[thing] < (datetime.datetime.now() - datetime.timedelta(minutes=2)):
                print(f'{thing} has not moved, removing')
                removeList.append(thing)
        for thing in removeList:
            del self.isMoving[thing]

        removeList = []
        for obj in self.idLookup:
            if "lastSeenMotion" in self.idLookup[obj]:
                #if no motion for 2 mins
                #if self.idLookup[obj]["lastSeenMotion"] < (datetime.datetime.now() - datetime.timedelta(minutes=2)):
                    # if no history updates in 30 mins
                if self.idLookup[obj]["lastSeen"] < (datetime.datetime.now() - datetime.timedelta(minutes=30)):
                    print(f'{obj} can be removed, no motion or history in 30 mins')
                    removeList.append(obj)
                elif self.idLookup[obj]["lastSeenMotion"] > (datetime.datetime.now() - datetime.timedelta(minutes=1)):
                    self.motionActive = self.idLookup[obj]["lastSeenMotion"]
        
        for thing in removeList:
            del self.idLookup[thing]

            #else:
            #    print(f'{self.idLookup[obj]} no lastseen movement to check')

                
        if self.motionActive > (datetime.datetime.now() - datetime.timedelta(minutes=1)):
            print('motion')




    def on_message(self, mqttc, obj, msg):
        requiredScore = 0
        device = msg.topic.split("/")
        msgsplit = msg.topic.split("/")
        msgjson = json.loads(msg.payload.decode("utf-8"))
        #self.manageAlert()
        if isinstance(msgjson, dict):
            if len(msgjson["detections"]) > 0:
                for trackedObject in msgjson["detections"]:
                    firstDetect = False
                    # keep log of how often we look at objects
                    self.runcount +=1
                    #check for required fields
                    if True:
                        if "id" not in trackedObject and "className" in trackedObject:
                            if trackedObject["className"] != "motion":
                                print('pass on no id, its not motion')
                                print(trackedObject)
                                continue
                            else:
                                print('pass on no id')
                                print(trackedObject)
                                continue
                        
                        if "score" in trackedObject and "className" in trackedObject and "id" in trackedObject and "zones" in trackedObject:
                            objdict = {}
                            id = trackedObject['id']
                            # tracking with id and firstseen
                            if trackedObject["id"] in self.idLookup:
                                objdict = self.idLookup[trackedObject["id"]]
                                objdict["count"] = objdict["count"] + 1
                            else:
                                print(f'found new {trackedObject["className"]} with id {trackedObject["id"]}. zones {trackedObject["zones"]}')
                                objdict["count"] = 1
                                objdict["className"] = trackedObject["className"]
                                objdict["firstSeen"] = datetime.datetime.fromtimestamp(trackedObject["history"]["firstSeen"]/1000)
                                objdict["lastSeen"] = datetime.datetime.fromtimestamp(trackedObject["history"]["lastSeen"]/1000)
                                objdict["zones"] = trackedObject["zones"]

                                firstDetect = True  
                            # update zones

                            if trackedObject["zones"] != objdict["zones"]:
                                objdict["zones"] = trackedObject["zones"]
                            # check for movement
                            if len(trackedObject["movement"])> 0:
                                objdict["movement"] = trackedObject["movement"]
                            
                            #save objdict
                            self.idLookup[trackedObject["id"]] = objdict

                               

                            if "history" in trackedObject:
                                if trackedObject["history"]["firstSeen"] in self.firstseenLoopup:
                                    self.firstseenLoopup[trackedObject["history"]["firstSeen"]] = self.firstseenLoopup[trackedObject["history"]["firstSeen"]] +1
                                else:
                                    self.firstseenLoopup[trackedObject["history"]["firstSeen"]] = 1 
                            else:
                                print('ERROR - no history')     
                                print(trackedObject)


                            # if there is movement update lastSeen
                            if len(trackedObject["movement"]) > 0:              
                                self.idLookup[trackedObject["id"]]["lastSeenMotion"] = datetime.datetime.fromtimestamp(trackedObject["movement"]["lastSeen"]/1000)
                                self.isMoving[trackedObject['id']] = datetime.datetime.fromtimestamp(trackedObject["movement"]["lastSeen"]/1000)

                            

                            # property should be for someone coming home
                            if "Property" in objdict["zones"]:
 
                                    historyFirstSeen = datetime.datetime.fromtimestamp(trackedObject["history"]["firstSeen"]/1000)

                                    # this is a new object, so someone pulling into driveway?
                                    if historyFirstSeen > (datetime.datetime.now() - datetime.timedelta(minutes=5)):
                                        self.motionAlert[trackedObject["className"]] = datetime.datetime.fromtimestamp(trackedObject["movement"]["lastSeen"]/1000)
                                        print(f"property {trackedObject['className']} {trackedObject['id']}, with movement. first seen is greater than now - 5 mins {trackedObject['id']}. Was first seen {historyFirstSeen}")
                                   
                        

    def old(self):

    # if there is data in movement it moved
            
        if len(trackedObject["movement"])> 0:
            self.idLookup[trackedObject["id"]]["lastSeen"] = datetime.datetime.fromtimestamp(trackedObject["movement"]["lastSeen"]/1000)

            if trackedObject["className"] not in self.motionAlert:
                print('motion')
            #update last moved
            self.isMoving[trackedObject['id']] = datetime.datetime.fromtimestamp(trackedObject["movement"]["lastSeen"]/1000)

            #track last motion for object type
            self.motionAlert[trackedObject["className"]] = datetime.datetime.fromtimestamp(trackedObject["movement"]["lastSeen"]/1000)
            
            #if "lastSeen" in trackedObject["movement"] and "firstSeen" in trackedObject["movement"]:
            firstSeen = datetime.datetime.fromtimestamp(trackedObject["movement"]["firstSeen"]/1000)
            lastSeen = datetime.datetime.fromtimestamp(trackedObject["movement"]["lastSeen"]/1000)
            
            self.idLookup[trackedObject["id"]]["lastSeen"] = datetime.datetime.fromtimestamp(trackedObject["movement"]["lastSeen"]/1000)
            
                

            # print(f'{trackedObject["id"]} - {trackedObject["className"]} has movement, firstseen - {firstSeen}, now - {datetime.datetime.now()}')
                #if self.isMoving[trackedObject['id']] < (datetime.timedelta(seconds=5) - datetime.datetime.now()):
                #    print(f'{trackedObject["id"]} - {trackedObject["className"]} has movement, firstseen - {firstSeen}, now - {datetime.datetime.now()}')


            #else:

                
                #historyFirstSeen = datetime.datetime.fromtimestamp(trackedObject["history"]["firstSeen"]/1000)
                # no movement, check firstseen
                #if historyFirstSeen > (datetime.timedelta(minutes=5) - datetime.datetime.now()):
                #    print(f"first seen is greater than now - 5 mins {trackedObject['id']} has no movement. Was first seen {historyFirstSeen}")
                #else:
                #    print(f"first seen is not greater than now - 5 mins {trackedObject['id']} has no movement. Was first seen {historyFirstSeen}")


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
                    print(item, self.idLookup[item]["count"])
                #print(self.idLookup)
            self.manageAlert()
            time.sleep(1)
            runCount +=1



#(self.fanStateLastChange + datetime.timedelta(minutes=self.fanStartDelay) < datetime.datetime.now()) 
if __name__ == "__main__":
    print('needs to be imported to run')
    runner = broker()
    runner.run()
    idLookup = {}
    idLookup.update({"72":1})
    idLookup["34"] = 1
    
    
    if "72" in idLookup:
        idLookup["72"] = idLookup["72"] +1

    print(idLookup)


