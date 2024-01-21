import datetime
import subprocess
import platform
import os
from libraries import loggerdo
import threading




LASTPONGMIN = 2

class occupied:
    family = {}
    inittime = datetime.datetime.now()
    lastping = None
    timegone = None


    def __init__(self, config):
        family = config["family"]
        self.lastping = datetime.datetime.now()
        self.ticktok = 0
        self.nogoodping = 0
        self.lastpong = datetime.datetime.now()
        self.laststate = True
        self.timegone = config["timegone"]
        for person in family:
            self.family[person] = 1

    def knock(self, ip):

        pr = subprocess.Popen("ping -c 1 -W 1 {}".format(ip), shell=True, stdout=subprocess.DEVNULL)
        #pr.wait()
       # if pr.poll() == 0:
        if pr.wait() == 0:

            self.family[ip] = 1
        else:

            self.family[ip] = 0



    def anyonehome(self):
        if datetime.datetime.now() < (self.lastpong + datetime.timedelta(minutes=LASTPONGMIN)):

            return self.laststate
        self.lastpong = datetime.datetime.now()

        threads = []
        for person in self.family:
            t = threading.Thread(target=self.knock, args=(person,))
            t.start()
            threads.append(t)
        for y in threads:
            y.join()

        if 1 in self.family.values():

            # reset bad counter to 0
            self.nogoodping = 0
            # update the lastping to now
            self.lastping = datetime.datetime.now()
            self.laststate = True
            loggerdo.log.debug("occupied - Found someone home")
            return True
        else:

            # inc the bad ping counter
            self.nogoodping += 1
            # if someone has only not responded for x mins
            if datetime.datetime.now() < (self.lastping + datetime.timedelta(minutes=self.timegone)):
                return True
            #no one really home
            self.laststate = False
            loggerdo.log.debug("occupied - No one home")
            return False

