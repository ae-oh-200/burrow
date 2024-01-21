import paho  # Ensures paho is in PYTHONPATH
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
import yaml, json, datetime
from os import path
from libraries import loggerdo, utils





class broker():
    mqttc = None
    config = None



    def __init__(self, mqttconfig):
        self.mqttc = mqtt.Client()
        self.config = mqttconfig
        self.topicroot = self.config["topicroot"]
        self.host = self.config["mqttserver"]
        self.mqttc.on_message = self.on_message
        #self.mqttc.on_connect = self.on_connect
        self.mqttc.on_publish = self.on_publish
        #self.mqttc.on_subscribe = self.on_subscribe


    def on_publish(self, mqttc, obj, mid):
        print("on publish")
        #print("mid: " + str(mid))
        pass

    def on_connect(self,mqttc, obj, flags, rc):
        print("rc: " + str(rc))

    def on_subscribe(self, mqttc, obj, mid, granted_qos):
        loggerdo.log.debug("Subscribed: " + str(mid) + " " + str(granted_qos))


    def on_message(self, mqttc, obj, msg):

        device = msg.topic.split("/")

        if device[1] == "system":
            self.systemmessagein(device[2], msg.payload.decode("utf-8"))


    def publishtemph(self, temp, humidity ):
        temp = utils.truncate((temp-32) * 5/9,2)
        topic = self.topicroot + "/system/burrow/temph"
        loggerdo.log.debug("Publish t/h {}/{} to {}".format(temp,humidity, topic ))

        jsonmsg = json.dumps({"temp" : temp, "humidity": humidity, "time": datetime.datetime.now().strftime("%m-%d-%Y, %H:%M:%S")})
        publish.single(topic, payload=jsonmsg, retain=True, hostname=self.host, keepalive=60)

    def publishburrow(self, status):
        topic = self.topicroot + "/system/burrow/status"
        
        def tojson(update):
            return json.dumps({"system":update, "time": datetime.datetime.now().strftime("%m-%d-%Y, %H:%M:%S")})

        if status:
            publish.single(topic, payload=tojson(True), retain=True, hostname=self.host, keepalive=60)
        else:
            publish.single(topic, payload=tojson(False), retain=True, hostname=self.host, keepalive=60)


    def publishsystem(self, system, status):
        topic = self.topicroot + "/system/burrow/system"

        def tojson(update):
            return json.dumps({"system":update, "time": datetime.datetime.now().strftime("%m-%d-%Y, %H:%M:%S")})
        if system == "heat" and status == True:
            loggerdo.log.debug("Publish heat to homebridge mqttthing")
            publish.single(topic, payload=tojson("HEAT"), retain=True, hostname=self.host, keepalive=60)
        elif system == "heat" and status == False:
            loggerdo.log.debug("Publish off to homebridge mqttthing")
            publish.single(topic, payload=tojson("OFF"), retain=True, hostname=self.host, keepalive=60)
        elif system == "ac" and status == True:
            loggerdo.log.debug("Publish ac on to homebridge mqttthing")
            publish.single(topic, payload=tojson("AC"), retain=True, hostname=self.host, keepalive=60)
        elif system == "ac" and status == False:
            loggerdo.log.debug("Publish off to homebridge mqttthing")
            publish.single(topic, payload=tojson("OFF"), retain=True, hostname=self.host, keepalive=60)

    def publishtarget(self, temp):
        topic = self.topicroot + "/system/target/get"
        temp = utils.truncate((temp-32) * 5/9,2)

        def tojson(update):
            return json.dumps({"temp": update, "time": datetime.datetime.now().strftime("%m-%d-%Y, %H:%M:%S")})

        loggerdo.log.debug("publish target temp - {} to {}".format(temp,topic))
        publish.single(topic, payload=tojson(temp), retain=True, hostname=self.host, keepalive=60)

