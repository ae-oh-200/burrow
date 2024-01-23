import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.ticker import FuncFormatter, AutoMinorLocator
import numpy as np
import pymongo
import datetime
import pandas as pd

import sys
from . import loggerdo, getruntime
#import loggerdo, getruntime


def bargraph(mydb, history, output, system):

    ttime, tdays, bend, bstart = getruntime.lastmonthtotaltime(mydb, system)


    histup = []
    for his in history:
        if isinstance(his, int):
            histup.append(his)
        else:
            histup.append(his.seconds)

    #check to see if time should be reported in hours or minnutes

    #get average run time
    totaltime = 0
    for i in histup:
        totaltime = totaltime + i
    i = i /len(histup)

    #if averge usage over 2 hours go with hours otherwise minutes
    if i > 90:
        #print("use hours")
        formatter = FuncFormatter(format_func_hours)
        yMlocator = 3600

        ylabel = "Hours"
    else:
        #print("use minutes")
        formatter = FuncFormatter(format_func_minutes)
        yMlocator = 3600//60
        ylabel = "Minutes"

    x=0
    days = []
    while x < len(history):
        today = datetime.datetime.now()
        othday = today - datetime.timedelta(days=x)
        days.append(othday.strftime("%a"))
        x +=1

    #invert so today is on right of graph
    days.reverse()
    histup.reverse()

    f = plt.figure()
    ax = f.add_subplot(1,1,1)

    ax.bar(days,histup)
    ax.yaxis.set_major_formatter(formatter)
    # this locates y-ticks at the hours

    ax.yaxis.set_major_locator(ticker.MultipleLocator(base=yMlocator))
    ax.yaxis.set_minor_locator(AutoMinorLocator())
    # this ensures each bar has a 'date' label

    ax.xaxis.set_major_locator(ticker.MultipleLocator(base=1))

    plt.title("Billing cycle({}), {} - {}, Total House:{}".format(str(tdays), str(bstart), str(bend), str(ttime)))
    #plt.xlabel('Days')
    plt.ylabel(ylabel)

    #untested function -

    # add 15% margin on top (since ax.margins seems to not work here)
    ylim = ax.get_ylim()
    ax.set_ylim(None, ylim[1]+0.15*np.diff(ylim))
    #ax.set_ylim(None, ylim[1]+0.1*np.diff(ylim))

    #plt.show()
    plt.savefig(output)
    plt.close('all')

def format_func_hours(x, pos):
    hours = float(x // 3600)
    minutes = int((x % 3600) // 60)
    seconds = int(x % 60)
    # return "{:d}".format(hours)
    return (x // 3600)


def format_func_minutes(x, pos):
    hours = (x // 3600)
    minutes = int((x % 3600) // 60)
    seconds = int(x % 60)
    return "{:d}".format(minutes)
    # return "{:d}:{:02d}".format(hours, minutes)


if __name__ == "__main__":

    #output = '/etc/burrow/Web/acgraph.png'

    output = 'graph.png'
    ddate = str(datetime.date.today() - datetime.timedelta(days=1))
    myclient = pymongo.MongoClient("mongodb://192.168.5.70:27017/")
    #yclient = pymongo.MongoClient("mongodb://192.168.5.70:27017/")
    mydb = myclient["burrow"]
    #ddate = str(datetime.date.today())
    #ddate = str(datetime.date.today())
    #getsinglehistory(1)

    if sys.argv[-1] == "--ac":
        history = getruntime.gethistory(7, "ac", mydb)
        bargraph(mydb, history, output, "ac")
    elif sys.argv[-1] == "--heat":
        history = getruntime.gethistory(7, "heat", mydb)
        bargraph(mydb, history, output, "heat")
    elif sys.argv[-1] == "--total":
        print(monthltime(mydb, "heat"))



