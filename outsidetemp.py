import requests
import json
import libraries
from libraries import loggerdo


def truncate(n, decimals=0):
    multiplier = 10 ** decimals
    return int(n * multiplier) / multiplier

def gettemp():
    url = 'http://api.openweathermap.org/data/2.5/weather'
    params ={'dataset':'daily-summaries',
        'zip':openweatherzip,
        'appid':openweatherappid,
        }

    r = requests.get(url,params=params)
    if r.ok:
        jsondata = r.json()
        #df = pd.read_csv(io.StringIO(data))
        return truncate(((jsondata["main"]["feels_like"]) - 273.15),2)
    else:
        print("uh oh")

def gettempinf(openweatherzip, openweatherappid):
    url = 'http://api.openweathermap.org/data/2.5/weather'
    params ={'dataset':'daily-summaries',
        'zip':openweatherzip,
        'appid':openweatherappid,
        }
    try:
        r = requests.get(url,params=params)
        if r.ok:
            jsondata = r.json()
            #df = pd.read_csv(io.StringIO(data))
            #'Yes' if fruit == 'Apple' else 'No'
            return truncate((((jsondata["main"]["feels_like"]) - 273.15) * 1.8+32),2) \
            if jsondata["main"]["feels_like"] > jsondata["main"]["temp"] \
            else truncate((((jsondata["main"]["temp"]) - 273.15) * 1.8+32),2)
            return truncate((((jsondata["main"]["feels_like"]) - 273.15) * 1.8+32),2)
        else:
            print("uh oh, r not ok")
            return 0
    except requests.ConnectTimeout as e:
        loggerdo.log.warning("Connection timed out - outsidetemp")
        return 0
    except requests.ConnectionError as e:
        loggerdo.log.warning("Connection error - outsidetemp")
        return 0
    except requests.RequestException as e:
        loggerdo.log.warning("There was an ambiguous exception that occurred - outsidetemp")
        return 0


def fullreturn(openweatherzip, openweatherappid):
    url = 'http://api.openweathermap.org/data/2.5/weather'
    params ={'dataset':'daily-summaries',
        'zip':openweatherzip,
        'appid':openweatherappid,
        }
    try:
        r = requests.get(url,params=params)
        if r.ok:
            jsondata = r.json()
            #df = pd.read_csv(io.StringIO(data))
            return jsondata
    except requests.exceptions.ConnectionError as e:
        print ("Error Connecting:",e)

    except requests.exceptions.RequestException as e:
        print ("OOps: Something Else",e)

    except Exception as e:
        print("fuck ", e)

    else:
        print("uh oh")

def pulldata(openweatherzip, openweatherappid):
    data = {}
    url = 'http://api.openweathermap.org/data/2.5/weather'
    params ={'dataset':'daily-summaries',
        'zip':openweatherzip,
        'appid':openweatherappid,
        }
    try:
        r = requests.get(url,params=params)
        if r.ok:
            jsondata = r.json()
            data.update({'temp' : truncate(((jsondata["main"]["temp"] - 273.15) * 1.8+32),2)})
            data.update({'feels' : truncate(((jsondata["main"]["feels_like"]- 273.15) * 1.8+32),2)})
            data.update({'humidity' : jsondata["main"]["humidity"]})
            #data.update({'description' : jsondata["weather"]["description"]})
            return data

    except requests.exceptions.ConnectionError as e:
        print ("Error Connecting:",e)

    except requests.exceptions.RequestException as e:
        print ("OOps: Something Else",e)

    except Exception as e:
        print("fuck ", e)

    else:
        print("uh oh")



if __name__ == "__main__":

    #ret = pulldata(openweatherzip, openweatherappid)
    #print(fullreturn(openweatherzip, openweatherappid))
    #for key, data in ret:
        #print("{} = {}".format(key,data))


    js = pulldata(openweatherzip,openweatherappid)
    print(type(js))
    #jsdata = json.loads(js)
    print(json.dumps(js,indent=1))
