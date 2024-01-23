
import meross
from libraries import loggerdo, utils
import time
from os import path


def configload():
	#pull config
	if path.exists("config.yaml"):
		config = utils.loadconfig('config.yaml')
	else:
		config = utils.loadconfig('/etc/burrow/config.yaml')
	return config



def run():
	config = configload()
	merossswitcharray = []
	switches = config["merossswitch"]
	for switch in switches:
		merossswitcharray.append(meross.merossswitch(IP=switches[switch]['ip'], Name=switches[switch]['name'],
											mqttserver=config["MQTT"]["mqttserver"], managed=True,
											zone=0, AC=False))

	while True:
		for msw in merossswitcharray:
			ret=msw.getstate()

		time.sleep(5)

if __name__ == "__main__":

	run()
