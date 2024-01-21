import pymongo
import datetime


def logacrecord(mydb, zone ,state):
    col = mydb["ac_records"]
    loaddic = {'timedate': str(datetime.datetime.now()), 'zone': zone, 'state': state}
    ret = col.insert_one(loaddic)

def oldlogacrecord(mydb, onoff,laststatus,fromcache=False):
    col = mydb["ac_records"]
    loaddic = {'timedate': str(datetime.datetime.now()), 'onoff': onoff, 'laststatus': laststatus, 'fromcache': fromcache}
    ret = col.insert_one(loaddic)

def logrecords(mydb, message):
    col = mydb["log_records"]
    loaddic = {'timedate': str(datetime.datetime.now()), 'message': message}
    ret = col.insert_one(loaddic)

def logheatrecord(mydb, onoff,laststatus,fromcache=False):
    col = mydb["heat_records"]
    loaddic = {'timedate': str(datetime.datetime.now()), 'onoff': onoff, 'laststatus': laststatus, 'fromcache': fromcache}
    ret = col.insert_one(loaddic)

def logheatrecordsettime(mydb, timedate, temp, onoff, laststatus, fromcache=False):
    col = mydb["heat_records"]
    loaddic = {'timedate': str(timedate),'temp': temp, 'onoff': onoff, 'laststatus': laststatus, 'fromcache': fromcache}
    ret = col.insert_one(loaddic)

def logheatrecordwithtemp(mydb, temp, onoff,laststatus,fromcache=False):
    col = mydb["heat_records"]
    loaddic = {'timedate': str(datetime.datetime.now()), 'temp': temp, 'onoff': onoff, 'laststatus': laststatus, 'fromcache': fromcache}
    ret = col.insert_one(loaddic)

def logoccupiedrecord(mydb, ip, status):
    col = mydb["occupied_records"]
    loaddic = {'timedate': str(datetime.datetime.now()), 'ip': ip, 'status': status}
    ret = col.insert_one(loaddic)

def logschedrecord(mydb, setto, high, low):
    col = mydb["sched_records"]
    loaddic = {'timedate': str(datetime.datetime.now()), 'setto': setto, 'high': high, 'low': low}
    ret = col.insert_one(loaddic)

def loaddailysched(mydb, name, ddate, ttime, base, high, low, scheduled, default, start, end):
    col = mydb["sched_records"]
    loaddic = {'date': ddate, 'time': ttime, 'base': base, 'high': high, 'low': low, 'mode': name, 'scheduled': scheduled, 'default': default, 'start': start, 'end': end}
    ret = col.insert_one(loaddic)

#def logtemp(mydb, zone, temp, cache, weight, humidity):
#    col = mydb["zone_records"]
#   loaddic = {'timedate': str(datetime.datetime.now()), 'zone': zone, 'temp': temp, 'cache': cache, 'weight': weight, 'humidity': humidity}
#    ret = col.insert_one(loaddic)

def logtemp(mydb, nickname, temp, cache, weight, humidity):
    col = mydb["temp_records"]
    loaddic = {'timedate': str(datetime.datetime.now()), 'topic': nickname, 'weight': weight,'temp': temp, 'humidity': humidity}
    ret = col.insert_one(loaddic)

def logoutside(mydb, temp, feels, humidity):
    col = mydb["outside_records"]
    loaddic = {'timedate': str(datetime.datetime.now()), 'temp': temp, 'feels_like': feels, 'humidity': humidity}
    ret = col.insert_one(loaddic)


def updatedailysched(mydb, ddate, ttime, base, high, low, mode):
    col = mydb["sched_records"]
    query = {'$and': [{'date': ddate }, {'time': ttime }, {'mode': mode} ]}
    #query = {'date': ddate, 'time': ttime}
    update = {"$set": {'base': base, 'high': high, 'low': low}}

    col.update_one(query, update)
    for x in col.find({'date': ddate, 'time': ttime, 'mode': mode}):
        return x

def gethourinfo(mydb, ddate, ttime):
    col = mydb["sched_records"]
    query = {'$and': [{'date': ddate }, {'time': ttime }]}
    detail = col.find(query)
    return(list(detail))

def dumpdailysched(mydb, ddate):
    ret = []
    col = mydb["sched_records"]
    for x in col.find({'date':ddate}):
        ret.append(x)
    return ret

def dumpdailyac(mydb, ddate):
    ret = []
    col = mydb["ac_records"]
    for x in col.find({'timedate': { "$regex": ddate }}):
        ret.append(x)
    return ret

"""
def dumpzoneday(mydb, ddate):
     ret = []
     col = mydb["zone_records"]
     for x in col.find({'date':'/'ddate'/''}):
         ret.append(x)
     return ret

"""

def dropday(mydb, ddate):
    col = mydb["sched_records"]
    query = {'date': ddate}
    dele = col.delete_many(query)

def checkday(mydb, ddate):
    col = mydb["sched_records"]
    query = {'date': ddate}
    find = col.find({'date':ddate})
    if find.count() > 0:
        return True
    else:
        return False


def pullday(mydb, ddate, mode):
    col = mydb["sched_records"]
    datequery = {'date': ddate}
    modequery = {'mode': mode}
    find = col.find({"$and":[datequery, modequery]})
    return find

def pullhour(mydb, ddate, hour, mode):
    col = mydb["sched_records"]
    datequery = {'date': ddate}
    modequery = {'mode': mode}
    timequery = {'time': hour}
    find = col.find({"$and":[datequery, timequery, modequery]})
    return find


def getlastheatstatus(mydb):
    #if there is no records in db, this will break
    col = mydb["heat_records"]
    find = col.find().limit(1).sort([('$natural',-1)])
    return find[0]['onoff']

