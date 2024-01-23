import pymongo
import datetime
import pandas as pd
from . import loggerdo
#import loggerdo


def lastmonthtotaltime(mydb, system):
    history = []
    onhistory = []
    totaltime = 0

    if datetime.date.today().day < 15:
        # cycle for month is not complete. Looking back 2 months
        if datetime.date.today().month < 3:
            lastyear = datetime.date.today().year - 1
            billingstart = datetime.date.today().replace(year=lastyear)
            billingend = datetime.date.today().replace(year=lastyear)

            if datetime.date.today().month == 1:
                billingstart = billingstart.replace(month=12)
                billingend = billingend.replace(month=11)
            else:
                billingstart = billingstart.replace(month=11)
                billingend = billingend.replace(month=10)


        billingstart = billingstart.replace(day=15)
        billingend = billingend.replace(day=15)
        totaldays = (billingstart - billingend).days

    else:
        billingstartmonth = datetime.date.today().month
        billingendmonth = datetime.date.today().month - 1
        billingstart = datetime.date.today().replace(month=billingstartmonth)
        billingstart = billingstart.replace(day=15)
        billingend = datetime.date.today()
        thisday = datetime.date.today().day
        while True:
            try:
                billingend = billingend.replace(month=billingendmonth)
            except ValueError:
                thisday -= 1
                billingend = datetime.date.today().replace(day=thisday)
            else:
                break

        billingend = billingend.replace(day=15)
        totaldays = (billingstart - billingend).days
    bend = billingend
    while billingend < billingstart:
        #print("loop, day is {}".format(billingend))
        ddate = str(billingstart)
        hisdf = getdata(ddate, system, mydb)
        if isinstance(hisdf, pd.core.frame.DataFrame):
            #make sure that getdate return something. Sort it by time and drop the default index
            hisdf = hisdf.sort_values(["timedate"])
            hisdf = hisdf.reset_index(drop=True)
            onhistory.append(gettotalontime(hisdf))
        else:
            onhistory.append(0)

        #append to history list, this is a list of dataframes
        #print("adding {} to df".format(hisdf))
        history.append(hisdf)

        billingend = billingend + datetime.timedelta(days=1)

    for day in onhistory:
        if isinstance(day, int):
            totaltime = totaltime + day
        else:
            totaltime = totaltime + day.seconds
    totaltime = totaltime / 3600
    multiplier = 10 ** 2
    return int(totaltime * multiplier) / multiplier, totaldays, bend, billingstart


def gettotalontime(df):
    start = datetime.timedelta(0)
    onoff = None
    time = None
    accum = datetime.timedelta(0)
    y = datetime.timedelta(0)

    #right now we can only work with data when it start with on.
    #print("day is, {}".format(df.iloc[0].timedate))
    while df.iloc[0].onoff =='off':

        df = df.drop(index=0)
        df = df.reset_index(drop=True)
        if len(df) == 0:
            return 0


    #start cleaning out duplicates
    lastonoff = None

    #change this to drop new instead of old
    for index, row in df.iterrows():
        #if last s
        if row['onoff'] == lastonoff:
            df = df.drop(index)
            continue
        lastonoff = row['onoff']


    df = df.reset_index(drop=True)
    for index, row in df.iterrows():
        if row['onoff'] == 'off':
            #loggersetup.log.debug("off at {}".format(row['timedate']))
            time = row['timedate'] - start
            start = datetime.timedelta(0)
            onoff = row['onoff']
            #loggersetup.log.debug("runtime is {} to be added to {}".format(time, accum))
            accum = accum + time
        else:
            #loggersetup.log.debug("on at {}".format(row['timedate']))
            start = row['timedate']

    if df['onoff'].iloc[-1] == 'on':
        if df['timedate'].iloc[-1].day == datetime.datetime.now().day:
            time = datetime.datetime.now() - df['timedate'].iloc[-1]
            accum = accum + time
    return accum

def getdata(ddate, system, mydb):
    ret = []
    #select collection for correct system
    if system == "heat":
        col = mydb["heat_records"]
    elif system == "ac":
        col = mydb["ac_records"]
    #grab data in a dataframe
    dfret = pd.DataFrame(list(col.find({'timedate': { "$regex": ddate}})))
    #exit if I return nothing
    if len(dfret) == 0:
        return None
    #convert time into a dp datetime
    dfret["timedate"] = pd.to_datetime(dfret['timedate'], format='%Y-%m-%d %H:%M')
    return dfret


if __name__ == "__main__":
    ddate = str(datetime.date.today() - datetime.timedelta(days=1))
    myclient = pymongo.MongoClient("mongodb://192.168.5.70:27017/")
    #yclient = pymongo.MongoClient("mongodb://192.168.5.70:27017/")
    mydb = myclient["burrow"]
    print(lastmonthtotaltime(mydb, 'heat'))
