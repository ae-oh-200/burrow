import sys
from libraries import utils
from os import path
#I want this to be the gloabl run file, passing it what to launch via command line.

#This makes it easier to spin up dockers and simply the run script





def configload():
    #pull config
    if path.exists("config.yaml"):
        config = utils.loadconfig('config.yaml')
    else:
        config = utils.loadconfig('/etc/burrow/config.yaml')
    return config



def receivefile(config):
    from libraries import receive_file
    receive_file.main(config["mqttserver"], config["topicroot"],  config["graphwebpath"])


if __name__ == "__main__":
    config = configload()

    if sys.argv[-1] == "--hvac" or config["module"] == "hvacr":
        print("HVAC mode")
        import HVAC
        HVAC.run()

    elif sys.argv[-1] == "--bme" or config["module"] == "bme":
        print("bme mode")
        from libraries import readsensorMQTT
        readsensorMQTT.main(config)

    elif sys.argv[-1] == "--screen" or config["module"] == "screen":
        print("screen mode")
        from libraries import readsensorMQTT

        import threading
        mqttgraph = threading.Thread(target=receivefile, args=(config["MQTT"],))
        mqttgraph.setDaemon(True)
        mqttgraph.start()
        readsensorMQTT.main(config)

    elif sys.argv[-1] == "--burrow" or config["module"] == "burrow":
        import goBurrow
        goBurrow.main(config)
    else:
        print("No module or flag passed")

