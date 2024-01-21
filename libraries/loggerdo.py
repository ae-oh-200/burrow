import logging
from logging.handlers import WatchedFileHandler
import os


mbp = False
debug = True
textfile = False



if mbp:
    current_path = os.path.dirname(os.path.realpath(__file__))
    debugfile = (os.path.join(current_path, 'burrow-debug.log'))
    logfile = (os.path.join(current_path, 'burrow.log'))
    tempmqttlog = (os.path.join(current_path, 'burrow-MQTT.log'))
    synclog = (os.path.join(current_path, 'burrow-sync.log'))
else:
    logdir = '/var/log/burrow'
    debugfile = (os.path.join(logdir, 'burrow-debug.log'))
    logfile = (os.path.join(logdir, 'burrow.log'))
    tempmqttlog = (os.path.join(logdir, 'burrow-MQTT.log'))
    synclog = (os.path.join(logdir, 'burrow-sync.log'))

#log = logging.getLogger('')
#log.setLevel(logging.DEBUG)

#logmqtt = logging.getLogger('MQTTlogs')
#logmqtt.setLevel(logging.DEBUG)

class tempfilter(logging.Filter):
    def filter(self, record):
        return record.getMessage().startswith('MQTTlistener-Sensor')

class nottempfilter(logging.Filter):
    def filter(self, record):
        return not record.getMessage().startswith('MQTTlistener-Sensor')

class syncfilter(logging.Filter):
    def filter(self, record):
        return record.getMessage().startswith('pigarage-sync')

class notsyncfilter(logging.Filter):
    def filter(self, record):
        return not record.getMessage().startswith('pigarage-sync')


class LevelFilter(logging.Filter):
    def __init__(self, level):
        self.level = level

    def filter(self, record):
        return record.levelno == self.level

log = logging.getLogger('')

if textfile:
    #log = logging.getLogger('')
    if debug:
        log.setLevel(logging.DEBUG)
        formatter = logging.Formatter("%(asctime)s:%(levelname)s: %(message)s")

        debuglog_handler = WatchedFileHandler(debugfile)
        debuglog_handler.setLevel(logging.DEBUG)
        debuglog_handler.addFilter(LevelFilter(logging.DEBUG))
        debuglog_handler.addFilter(nottempfilter())
        debuglog_handler.addFilter(notsyncfilter())
        debuglog_handler.setFormatter(formatter)

        infolog_handler = WatchedFileHandler(logfile)
        infolog_handler.setLevel(logging.INFO)
        infolog_handler.setFormatter(formatter)

        templog_handler = WatchedFileHandler(tempmqttlog)

        templog_handler.addFilter(tempfilter())
        templog_handler.setFormatter(formatter)

        synclog_handler = WatchedFileHandler(synclog)
        synclog_handler.addFilter(syncfilter())
        synclog_handler.setFormatter(formatter)

        log.addHandler(debuglog_handler)
        log.addHandler(infolog_handler)
        #logmqtt.addHandler(templog_handler)
        log.addHandler(templog_handler)
        log.addHandler(synclog_handler)
    else:
        print('not using debug')

else:
    ch = logging.StreamHandler()
    if debug:
        log.setLevel(logging.DEBUG)
        ch.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)
        ch.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s - %(levelname)s: %(message)s")
    ch.addFilter(nottempfilter())
    ch.addFilter(notsyncfilter())
    ch.setFormatter(formatter)
    log.addHandler(ch)


log.info("(info) using loggersetup.py")
log.warning("(warning) using loggersetup.py")
log.debug("(debug) using loggersetup.py")
log.error("(error) using loggersetup.py")
#logmqtt.info("(info) using loggersetup.py")


