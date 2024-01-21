from libraries import loggerdo
import paho.mqtt.publish as publish
import json
import datetime

def buildmessage(system, state):
    data = {"system": system, "state": state, "time": datetime.datetime.now().strftime("%m-%d-%Y, %H:%M:%S")}
    return json.dumps(data)

class heater():
    status = None
    lastupdate = None
    topic = None

    def __init__(self, config):
        self.status = False
        self.topic = "{}/system/{}/update".format(config["topicroot"], "heater")
        loggerdo.log.debug("setting up heatertalk with topic {}".format(self.topic))
        self.ip = config["mqttserver"]

    def on(self):
        loggerdo.log.debug("turning heater on")
        jsonmsg = buildmessage("heater", True)
        loggerdo.log.debug("heatertalk on - Topic is {}".format(self.topic))
        loggerdo.log.debug("heatertalk on - payload is {}".format(jsonmsg))
        publish.single(self.topic, payload=jsonmsg, retain=False, hostname=self.ip, keepalive=60)

    def off(self):
        loggerdo.log.debug("turning heater off")
        jsonmsg = buildmessage("heater", False)
        loggerdo.log.debug("heatertalk off - Topic is {}".format(self.topic))
        loggerdo.log.debug("heatertalk off - payload is {}".format(jsonmsg))
        publish.single(self.topic, payload=jsonmsg, retain=False, hostname=self.ip, keepalive=60)

