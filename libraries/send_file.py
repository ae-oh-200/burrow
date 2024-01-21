#MIT LICENSE
#https://github.com/hjltu/file-transfer-via-mqtt
"""
    send file over MQTT hjltu@ya.ru
    payload is json:
    "timeid":       message ID
    "filename":     file name
    "filesize":     "filename" size
    "filehash":     "filename" hash (md5)
    "chunkdata":    chunk of the "filename"
    "chunksize":    size of the "chunkdata" is 99
    "chunkhash":    hash of the "chunkdata" (md5)
    "chunknumber":  number of "chunkdata", numbered from (0 - null,zero)
    "encode":       "chunkdata" encoding type (base64)
    "end":          end of message (True - end)

    Usage: send_file.py file
"""

import os
import sys
import time
import json
import threading
import hashlib
import base64
import paho.mqtt.client as mqtt
from . import loggerdo


CHUNKSIZE = 999
chunknumber = 0

lock = threading.Lock()
client = mqtt.Client()


def close():
    client.disconnect()

def my_json(msg):
    return json.dumps(msg)  # object2string


def my_md5(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def publish(msg):
    try:
        client.publish(filetopic, my_json(msg), qos=0)
        if msg["end"] is False:
            loggerdo.log.debug(f"sending via {filetopic}")
            loggerdo.log.debug(f"send chunk:{msg['chunknumber']}, time:{(int(time.time()-float(msg['timeid'])))}, secs")
    except Exception as e:
        loggerdo.log.debug("ERR: publish, {}".format(e))


def sendfile(myfile):
    """ split, send chunk and wait lock release
    """
    global chunknumber

    time.sleep(2)   # pause for mqtt subscribe
    timeid = str(int(time.time()))
    filesize = os.path.getsize(myfile)
    filehash = my_md5(myfile)

    payload = {
        "timeid": timeid,
        "filename": myfile,
        "filesize": filesize,
        "filehash": filehash,
        "encode": "base64",
        "end": False}

    with open(myfile, 'rb') as f:
        while True:
            chunk = f.read(CHUNKSIZE)
            if chunk:
                data = base64.b64encode(chunk)
                payload.update({
                    "chunkdata": data.decode(),
                    "chunknumber": chunknumber,
                    "chunkhash": hashlib.md5(data).hexdigest(),
                    "chunksize": len(chunk)})
                publish(payload)
                lock.acquire()
                chunknumber += 1
            else:
                del payload["chunknumber"]
                del payload["chunkdata"]
                del payload["chunkhash"]
                del payload["chunksize"]
                payload.update({"end": True})
                loggerdo.log.debug("END transfer file: {}".format(myfile))
                publish(payload)
                break
    time.sleep(1)
    close()

def confirmation(top, msg):
    """ receive confirmation to save chunk
    and release lock for next msg
    """
    global chunknumber

    try:
        j = json.loads(msg.decode())
    except Exception as e:
        loggerdo.log.debug("ERR: json2msg {}".format(e))
        close()
    try:
        if j['chunknumber'] == chunknumber:
            lock.release()
    except Exception as e:
        loggerdo.log.debug("ERR: in json {}".format(e))
        close()
    loggerdo.log.debug("Received confirmation for {}".format(j['chunknumber']))



def on_connect(client, userdata, flags, rc):
    loggerdo.log.debug("OK Connected with result code "+str(rc))
    client.subscribe([(confirmtopic,0)])



def on_message(client, userdata, msg):
    ev = threading.Thread(target=confirmation, args=(msg.topic, msg.payload))
    ev.daemon = True
    ev.start()


def main(host, topic, myfile):
    global filetopic, confirmtopic
    port = 1883

    filetopic = topic + "/graph"
    confirmtopic = topic + "/confirmation"


    tm = time.time()
    if not os.path.isfile(myfile):
        #print("ERR: no file", myfile)
        return 1
    loggerdo.log.debug(f"START transfer file {myfile} chunksize = {CHUNKSIZE}, bytes")

    client.connect(host, port, 60)

    client.on_connect = on_connect
    client.on_message = on_message

    my_thread = threading.Thread(target=sendfile, args=(myfile,))
    my_thread.daemon = True
    my_thread.start()
    client.loop_forever()


if __name__ == "__main__":

    ip = "192.168.5.70"
    topic = 'burrow'
    myfile = 'graph.png'
    main(ip, topic, myfile)

