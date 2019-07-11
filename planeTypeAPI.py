import os
import random
import math
from datetime import datetime, timedelta, date
import time
import db
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from db import session_factory
import requests
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException
import json

dirpath = os.getcwd()


def reinit():
    db.reinit()
    a = routedb()
    a.loaddata()
    a = airportdb()
    a.loaddata()
    a = planetypedb()
    a.loaddata()

def load_tzutc():
    session = session_factory()
    with open('./rawdata/timezone/tz.txt') as fp:
        for line in fp:
            print(line)
            tmp = line.split()
            print(tmp)
            session.execute("insert into Timezone (timezone, utcdiff) VALUES( '%s' , '%s' )" % (tmp[0],tmp[2]))
    session.commit()
    session.close()

def convertTimeZone(datestr,_time,timezone):
    datestr = [i for i in datestr.split('-')]
    _time = _time.split(':')
    if len(_time) < 2:
        return None
    dates = []
    timezone = timezone.replace("'",'')
    if timezone[0].isalpha():
        try:
            session = session_factory()
            local_tz = session.execute(f"select utcdiff from Timezone where timezone = '{timezone}'")
        except:
            session.close()
            return None
        if not local_tz:
            return None
    else:
        local_tz = [[timezone]]
    
    for x in local_tz:
        timezone = x[0]
        tmptime = str(_time[0])+ ':' +_time[1]
        tlocal_tz = datetime.strptime(tmptime, "%I:%M%p") 
        # add or substract hours to UTC 
        if timezone[0] == '+':
            tlocal_tz -=  timedelta(hours=int(timezone[1:]))
        elif timezone[0] == '-':
            tlocal_tz +=  timedelta(hours=int(timezone[1:]))
        tlocal_tz = datetime.strftime(tlocal_tz, "%H:%M")
        month = time.strptime(datestr[1],'%b').tm_mon
        if len(str(month)) == 1:
            month = '0'+ str(month)
        date = datestr[2] + month + datestr[0]   + tlocal_tz.replace(':','') 
        if len(date) == 12:
            date += '00'
        print('date: ' ,date)
        dates.append(date)
    return dates

def diffdistance(long1, lat1, long2, lat2):
    ph1 = math.radians(lat1)
    ph2 = math.radians(lat2)
    r = 6371e3
    latdiff = math.radians(lat1-lat2)
    longdiff = math.radians(long1-long2)
    a = math.sin(latdiff/2) * math.sin(latdiff/2) + math.cos(ph1) * math.cos(ph2) *  \
        math.sin(longdiff / 2) * math.sin(longdiff/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return (r * c)/1000


def toepoch(_date):   # input format 20190501173500
    year = _date[:4]
    month = _date[4:6]
    day = _date[6:8]
    hour = _date[8:10]
    minute = _date[10:12]
    seconds = _date[12:]
    return int((datetime(int(year), int(month), int(day), int(hour), int(minute), int(seconds)) - datetime(1970, 1, 1)).total_seconds())


class flightawareAPI():
    
    def __init__(self,username,apiKey):
        self.username = username
        self.apiKey = apiKey
        self.fxmlUrl = "https://flightxml.flightaware.com/json/FlightXML2/"

    def SearchBirdseyePositions(self,latitiude, longtitude):

        #altitude = (altitude * 3.28084) / 100
        payload = {'query':f'{{range lat {latitiude-2} {latitiude+2}}}  {{range lon {longtitude -2} {longtitude + 2}}}  }}', 'howMany':'15', 'uniqueFlights':'true', 'offset':'0'}
        response = requests.get(self.fxmlUrl + "SearchBirdseyePositions",
        params=payload, auth=(self.username, self.apiKey))
        ret = []
        if response.status_code == 200:
            res = response.json()
            print(res)
            tmp = res['SearchBirdseyePositionsResult']
            res = tmp['data']
            for x in tmp:
                ret.append(x['faFlightID'].split('-')[0])
            return ret
        else:
            print("Error executing request")

class api():
    def __init__(self, chrome_path=os.getcwd() +"/chromedriver/chromedriver"):
        chrome_options = Options()
        self.chrome_driver = chrome_path
        user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.50 Safari/537.36'
        chrome_options.add_argument('user-agent='+user_agent)
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920x1080")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument('--disable-dev-shm-usage')
        # chrome_options.add_argument("--disable-javascript")
        self.driver = webdriver.Chrome(options=chrome_options, executable_path=self.chrome_driver)
        self.wait = WebDriverWait(self.driver, 10)
        self.rotate = random.randint(4,10)
        self.session = session_factory()

    def close(self):
        self.driver.close()

    def _getTypeByID(self, flightID, epochtime, option=1):
       # first try flightradar24
        s = random.uniform(1.0,1.5)
        if option == 0:
            self.driver.get("https://www.flightradar24.com/data/flights/"+flightID)
            print('sleeping for %f seconds'%s)
            time.sleep(s)
            try:
                self.wait.until(lambda driver: self.driver.find_element_by_css_selector('tr[class=" data-row"]').is_displayed())
            except:
                return 'del'
            datarow = self.driver.find_elements_by_css_selector('tr[class=" data-row"]')
            for i in range(len(datarow)):
                try:
                    sta = int(datarow[i].find_elements_by_css_selector('td[class="hidden-xs hidden-sm"]')[5].get_attribute("data-timestamp"))
                    std = int(datarow[i].get_attribute("data-timestamp"))
                except:
                    continue
                for ep in epochtime:    
                    if toepoch(ep) >= std and toepoch(ep) <= sta:
                        planeType = datarow[i].find_elements_by_css_selector('td[class="hidden-xs hidden-sm"]')[1].text
                        return planeType
        elif option == 1:
            try:
                self.driver.get("https://flightaware.com/live/flight/%s" % flightID)
                print('sleeping for %f seconds'%s)
                time.sleep(s)
                table = self.driver.find_element_by_css_selector('div[id="flightPageActivityLog"]')
                table = table.find_elements_by_css_selector('div[class="flightPageDataTable"]')

            except:
                return 'del'
            
            datas = []
            t  = 0
            while t < 3:
                try:
                    if len(table) == 2:
                        first = table[1].find_element_by_css_selector('div[class="flightPageDataRowTall flightPageDataRowActive"]')
                        ptype = first.find_elements_by_css_selector('div[class="flightPageActivityLogData optional"]')[0].text
                        date = first.find_elements_by_css_selector('div[class="flightPageActivityLogData flightPageActivityLogDate"]')[0].text
                        datas.append([ptype,date])
                    break
                except NoSuchElementException:
                    break
                    
                except StaleElementReferenceException:
                    table = self.driver.find_element_by_css_selector('div[id="flightPageActivityLog"]')
                    table = table.find_elements_by_css_selector('div[class="flightPageDataTable"]')
                    t+= 1
            for x in range(len(table)):
                rows = None
                t  = 0
                while t < 3:
                    try:
                        rows = table[x].find_elements_by_css_selector('div[class="flightPageDataRowTall "]')
                        break
                    except StaleElementReferenceException:
                        table = self.driver.find_element_by_css_selector('div[id="flightPageActivityLog"]')
                        table = table.find_elements_by_css_selector('div[class="flightPageDataTable"]')
                        t += 1
                if not rows:
                    table = self.driver.find_element_by_css_selector('div[id="flightPageActivityLog"]')
                    table = table.find_elements_by_css_selector('div[class="flightPageDataTable"]')
                    rows = table[x].find_elements_by_css_selector('div[class="flightPageDataRowTall "]')
                
                for i in range(len(rows)):
                    # plane type
                    t  = 0
                    while t < 3:
                        try:
                            table = self.driver.find_element_by_css_selector('div[id="flightPageActivityLog"]')
                            table = table.find_elements_by_css_selector('div[class="flightPageDataTable"]')
                            rows = table[x].find_elements_by_css_selector('div[class="flightPageDataRowTall "]')
                            ptype = rows[i].find_elements_by_css_selector('div[class="flightPageActivityLogData optional"]')[0].text
                            date = rows[i].find_elements_by_css_selector('div[class="flightPageActivityLogData flightPageActivityLogDate"]')[0].text
                            datas.append([ptype,date])
                            break
                        except StaleElementReferenceException:
                            table = self.driver.find_element_by_css_selector('div[id="flightPageActivityLog"]')
                            table = table.find_elements_by_css_selector('div[class="flightPageDataTable"]')
                            rows = table[x].find_elements_by_css_selector('div[class="flightPageDataRowTall "]')
                            t += 1
            t  = 0
            while t < 3:
                try:
                    table = self.driver.find_element_by_css_selector('div[id="flightPageActivityLog"]')
                    table = table.find_elements_by_css_selector('div[class="flightPageDataTable"]')
                    if len(table) == 2:
                        first = table[1].find_element_by_css_selector('div[class="flightPageDataRowTall flightPageDataRowActive"]')
                        tmptime = first.find_elements_by_css_selector('div[class="flightPageActivityLogData"]')
                        datas[0].append(tmptime[0].text)
                        datas[0].append(tmptime[1].text)
                    break
                except NoSuchElementException:
                    break
                except StaleElementReferenceException: 
                    table = self.driver.find_element_by_css_selector('div[id="flightPageActivityLog"]')
                    table = table.find_elements_by_css_selector('div[class="flightPageDataTable"]')
                    t += 1
            
            for x in range(len(table)):
                rows = None
                t  = 0
                while t < 3:
                    try:
                        table = self.driver.find_element_by_css_selector('div[id="flightPageActivityLog"]')
                        table = table.find_elements_by_css_selector('div[class="flightPageDataTable"]')
                        rows = table[x].find_elements_by_css_selector('div[class="flightPageDataRowTall "]')
                        break
                    except StaleElementReferenceException:
                        table = self.driver.find_element_by_css_selector('div[id="flightPageActivityLog"]')
                        table = table.find_elements_by_css_selector('div[class="flightPageDataTable"]')
                        rows = table[x].find_elements_by_css_selector('div[class="flightPageDataRowTall "]')
                        t += 1
                

                for i in range(len(rows)):
                    t = 0
                    while t < 3:
                        try:
                            tmptime = rows[i].find_elements_by_css_selector('div[class="flightPageActivityLogData"]')   
                            datas[i].append(tmptime[0].text)
                            datas[i].append(tmptime[1].text)
                            break
                        except StaleElementReferenceException:
                            table = self.driver.find_element_by_css_selector('div[id="flightPageActivityLog"]')
                            table = table.find_elements_by_css_selector('div[class="flightPageDataTable"]')
                            rows = table[x].find_elements_by_css_selector('div[class="flightPageDataRowTall "]')
                            t += 1
            print(len(datas))
            print(datas)
            for row in datas:
                date = row[1]
                date = date.split('\n')[1]
                # to do check if date is the same if there is no time
                if len(row) < 4:
                    continue
                deptime = row[2].split('\n')[0]
                arrtime = row[3].split('\n')[0]
                print('arr and dep time',arrtime,deptime)
                if not deptime or not arrtime:
                    print('cannot convert deptime or arrtime')
                    continue
                try:
                    deptz = deptime.split()[1]
                    arrtz = arrtime.split()[1]
                    deptime = convertTimeZone(date,deptime.split()[0],deptz) 
                    arrtime = convertTimeZone(date,arrtime.split()[0],arrtz) 
                except:
                    continue
                print('arr and dep time2',arrtime,deptime)
                if not deptime or not arrtime:
                    print('cannot convert deptime or arrtime')
                    continue
                for dept in deptime:
                    for arrt in arrtime:
                        for ep in epochtime:   
                            edept = toepoch(dept)
                            earrt = toepoch(arrt)
                            if edept < earrt: 
                                if toepoch(ep) >= edept and toepoch(ep) <= earrt:
                                    dep = row[2].split('-')[1].replace(' ','')
                                    arr = row[3].split('-')[1].replace(' ','')
                                    return [row[0],dep,arr]
                                else:
                                    print(f'time {toepoch(ep)} not between deptime {edept} and arrtime {earrt}')
        return None

    def get_airport(self, lat1, long1, range=4, international=False, distance_range= 100):
        arange = [ int(long1-range), int(long1+range), int(lat1 - range) , int(lat1+range) ]
        inter = ''
        if international:
            inter = "and international = 1"
        cur = self.session.execute("select icao, latitude, longitude from Airport where longitude  between %d and %d and latitude between %d and %d %s"% (arange[0],arange[1],arange[2],arange[3],inter))
        res = []
        for row in cur:
            tmp = diffdistance(long1,lat1,row[2],row[1])
            if  tmp < distance_range:
                res.append(row[0])
        return res

    def distance_diff_airport(self,airport1, airport2, code='icao'):
        airport1 = self.session.execute(f"select latitude,longitude from Airport where {code} = '{airport1}'").fetchone()
        airport2 = self.session.execute(f"select latitude,longitude from Airport where {code} = '{airport2}'").fetchone()
        if not airport1 or not airport2:
            return 0

        return diffdistance(airport1[1],airport1[0],airport2[1],airport2[0])

    
    def get_international_airport_wiki(self):
        self.driver.get("https://en.wikipedia.org/wiki/List_of_international_airports_by_country")
        table = self.driver.find_elements_by_css_selector('table[class="wikitable"]')
        res = []

        for x in table:
            p = x.find_elements_by_css_selector('tr')
            for l in range(1,len(p)):
                tr = p[l].find_elements_by_css_selector('td')
                res.append(tr[2].text)
        return res



    def getRoutebyPort(self,dep,arr):
        res = self.session.execute("select flightid from route where arr='%s' and dep = '%s'"% (arr,dep))
        return [i[0] for i in res]

    def getRoutebyAware(self,dep,arr):  #ICAO
        self.driver.get("https://flightaware.com/live/findflight?origin=%s&destination=%s" % (dep,arr))
        datarow = self.driver.find_elements_by_css_selector('td[class="ffinder-results-ident text_align_left"]')
        routes = set()
        for row in datarow:
            flightID = row.find_element_by_css_selector('a').text
            if len(flightID) > 3:
                routes.add(flightID.replace(' ',''))
        return list(routes)

    def getRoutebyStat(self,dep,arr,_date): # for hour 0 - 0-6, 6 - 6-12, 12 -12-18, 18 - 0 
        if type(_date) != str:
            _date = str(_date)
        year = int(_date[:4])
        month = int(_date[4:6])
        day = int(_date[6:8])
        hour = int(_date[8:10])
        if hour < 6:
            hour = 0
        elif hour < 12:
            hour = 6
        elif hour < 18:
            hour = 12
        else:
            hour = 18
        _path = "https://www.flightstats.com/v2/flight-tracker/route/%s/%s/?year=%s&month=%s&date=%s&hour=%s"% (dep,arr,year,month,day,hour)
        self.driver.get(_path)
        try:
            self.wait.until(lambda driver: self.driver.find_element_by_css_selector('div[class="table__Table-s1x7nv9w-6 iiiADv"]').is_displayed())
        except:
            return []
        table = self.driver.find_element_by_css_selector('div[class="table__Table-s1x7nv9w-6 iiiADv"]')
        datarow = table.find_elements_by_css_selector('div[class="table__TableRowWrapper-s1x7nv9w-9 ggDItd"]')
        routes = set()
        for row in datarow:
            route = row.find_element_by_css_selector('h2[class="table__CellText-s1x7nv9w-15 KlAnq"]').text
            routes.add(route.replace(' ',''))
        return list(routes)


class routedb():
    def loaddata(self):
        count = 0
        session = session_factory()
        with open('./rawdata/routes.tsv') as fp:
            next(fp)
            for line in fp:
                tmp = line.split('\t')
                if len(tmp[2]) > 2 and len(tmp[4]) > 2:
                    session.execute("insert into Route (flightid, dep,arr) VALUES( '%s' , '%s' , '%s' )" % (tmp[0],tmp[2].replace("'",''),tmp[4].replace("'",'')))
                    count += 1
                    if count % 1000 == 0:
                        try:
                            session.commit()
                            print('successfully inserted 1000 row, total inserted: %d'% count)
                        except:
                            print('error')
                            session.rollback()
                            session.flush()
            session.commit()


class airportdb():
    def loaddata(self):
        count = 0
        session = session_factory()
        with open('./rawdata/airports.txt') as fp:
            for line in fp:
                tmp = line.split(',')
                if tmp[4] != "\\N":
                    session.execute("insert into Airport ( iata, icao, latitude,longitude, altitude)\
                                    VALUES( '%s' , '%s', %f , %f, %f)"
                                    %(tmp[4].replace('"', ''),tmp[5].replace('"', ''),
                                    float(tmp[6]),float(tmp[7]),float(tmp[8]))) 
                    count += 1
        try:
            session.commit()
            print('successfully inserted %d row'% count)
        except:
            print('error')
            session.rollback()
            session.flush()

    def loadlonghaul(self):
        session = session_factory()
        a = api()
        airports = a.get_international_airport_wiki()
        for x in airports:
            session.execute("UPDATE Airport SET international = 1 where iata = '%s'" %(x))
        session.commit()
        a.close()
    
        


class planetypedb():

    def __init__(self):
        self.session = session_factory()
        self.api = api()

    def loaddata(self, international = False, distance_diff=250):
        filelist = os.listdir('./rawdata/amdw')
        filelist.sort(key=lambda x: int(x.split('.')[1]))
        dict1 = {}
        timedict = {}
        flightIDs = set()

        with open('./statistic/airportMatchResult.txt','a') as statairport:
            for file in filelist:
                lwa = 0
                numair = 0
                statairport.write(f'airport matching statistic for file {file} \n')
                with open('./rawdata/amdw/'+file) as fp:
                    for line in fp:
                        tmp = line.split()
                        if tmp[0] not in dict1:
                            dict1[tmp[0]] = {}  
                        if tmp[0] not in timedict:
                            timedict[tmp[0]] = [tmp[1]+tmp[2]]
                        else:
                            timedict[tmp[0]].append(tmp[1]+tmp[2])
                            if len(timedict[tmp[0]]) >= 50:
                                #timedict[tmp[0]].pop(random.randrange(len(timedict[tmp[0]])))
                                timedict[tmp[0]].pop(50//2)

                            if file[:5] == 'AIREP' and tmp[0][:3].isalpha() and tmp[0][3:].isdigit():
                                flightIDs.add(tmp[0]) 
                            else:      
                                if file[:5] != 'AIREP':
                                    try: 
                                        if tmp[7] != '???' and tmp[8] != '???':
                                            if tmp[7] not in dict1[tmp[0]]:
                                                dict1[tmp[0]][tmp[7]] = 1
                                            else:
                                                dict1[tmp[0]][tmp[7]] += 1
                                            if tmp[8] not in dict1[tmp[0]]:
                                                dict1[tmp[0]][tmp[8]] = 1
                                            else:
                                                dict1[tmp[0]][tmp[8]] += 1
                                            continue
                                    except:
                                        print('File format not the same')
                                        continue
                                lwa += 1 
                            

                                match = self.api.get_airport(float(tmp[3].replace('*','')),float(tmp[4].replace('*','')),international = international)
                                if match != None:
                                    for port in match:
                                        numair += 1
                                        tmatch = '*' + port
                                        if tmatch not in dict1[tmp[0]]:
                                            dict1[tmp[0]][tmatch] = 1
                                        else:
                                            dict1[tmp[0]][tmatch] += 1
                statairport.write(f"total line : {lwa} , total number of both airport matched: {numair} \n")
        
        for i in list(flightIDs):
            indb = self.session.execute("select * from planetype where amdarid = '%s'" %i).fetchone()
            if not indb:
                ptype = self.api._getTypeByID(i,timedict[i],option=1)
                if ptype:
                    self.session.execute("insert into Planetype ( amdarid, flightid,planetype) VALUES( '%s' , '%s' , '%s')"
                                %(i,i,ptype)) 
                    print(f'inserted {ptype} for  flight {i}')
                    self.session.commit()
        totalunique = len(dict1)
        matchedRoute = 0
        matchedType = 0
        less2air = 0
        for i in dict1:
            indb = self.session.execute("select * from planetype where amdarid = '%s'" %i).fetchone()
            val = list(dict1[i].keys())
            val.sort(key=lambda x: dict1[i][x],reverse=True)
            if len(val) < 2:
                print('less than 2 airport')
                less2air += 1
                continue

            if not indb:
                #try:
                for dep in val:
                    for arr in val:
                        if dep != arr:
                            if dep[0] == '*':
                                deport = dep[1:]
                            else:
                                deport = dep
                            if arr[0] == '*':
                                arrport = arr[1:] 
                            else:
                                arrport = arr
                            if self.api.distance_diff_airport(arrport,deport) < distance_diff:
                                print(f'distance between 2 airport is less than {distance_diff}')
                                continue
                            b = self.get_route(deport,arrport,timedict[i][0])
                            if b:
                                print(b)
                                matchedRoute += 1
                            for x in b:
                                print('testing for %s'%x)
                                planetype = self.api._getTypeByID(x,timedict[i],option=1)
                                
                                if planetype and planetype != 'del':
                                    dep = planetype[1]
                                    arr = planetype[2]
                                    planetype = planetype[0]
                                    matchedType+= 1
                                    if dep not in dict1[i]:
                                        dict1[i][dep] = 1
                                    if arr not in dict1[i]:
                                        dict1[i][arr] = 1
                                    self.session.execute("insert into Planetype ( amdarid, flightid,planetype, dep,arr,depcount,  arrcount,datasource) VALUES( '%s' , '%s' , '%s', '%s' , '%s', %d, %d, %s)"
                                            %(i,x,planetype,dep,arr, dict1[i][dep],dict1[i][arr],"'flightaware'")) 
                                    countdb = self.session.execute("select * from Planetypematch where amdarid = '%s'" %i).fetchone()
                                    if countdb:
                                        if planetype in [countdb[2],countdb[5],countdb[8]]:
                                            dbc = [countdb[2],countdb[5],countdb[8]].index(planetype) + 1
                                            self.session.execute("UPDATE Planetypematch SET matchcount%s = matchcount%s + 1 where amdarid = '%s'" %(dbc,dbc,i))
                                        elif None in [countdb[2],countdb[5],countdb[8]]:
                                            dbc = [countdb[2],countdb[5],countdb[8]].index(None) + 1
                                            self.session.execute(f"UPDATE Planetypematch SET matchcount{dbc} = 1, flightid{dbc} = '{x}', Planetype{dbc} = '{planetype}' where amdarid = '{i}'")                     
                                    else:
                                        self.session.execute("insert into Planetypematch ( amdarid, flightid1,Planetype1, matchcount1) VALUES( '%s' , '%s', '%s', %d)"
                                            %(i,x,planetype,1))   
                                    if matchedType%5 == 0:
                                        self.session.commit()
                                    print('\n planetype %s matched for %s and %s'%(planetype,x,i))
                                    break
                                elif planetype == 'del':
                                    self.session.execute(f"delete from Route where flightid = '{x}'") 
                                    self.session.commit()
                            else:
                            # Continue if the inner loop wasn't broken.
                                continue
                                # Inner loop was broken, break the outer.
                            break
                    else:
                        continue
                    break

            #elif dict1[i][val[0]] > indb[6] and dict1[i][val[1]] > indb[8]:
            else:
                if val[0][0] == '*':
                    deport = val[0][1:]
                else:
                    deport = val[0]
                if val[1][0] == '*':
                    arrport = val[1][1:] 
                else:
                    arrport = val[1]
                if self.api.distance_diff_airport(arrport,deport) < distance_diff:
                    print(f'distance between 2 airport is less than {distance_diff}')
                    continue
                if arrport == deport:
                    continue
                b = self.api.getRoutebyPort(deport,arrport)
                if b:
                    matchedRoute += 1
                    for x in b:
                        print('testing for %s'%x)
                        planetype = self.api._getTypeByID(x,timedict[i] ,option=1) # don't convert time to epoch first
                        if planetype and planetype != 'del':
                            dep = planetype[1]
                            arr = planetype[2]
                            planetype = planetype[0]
                            if dep not in dict1[i]:
                                dict1[i][dep] = 1
                            if arr not in dict1[i]:
                                dict1[i][arr] = 1
                            matchedType+= 1
                            if indb[2] != planetype:
                                self.session.execute("UPDATE Planetype SET flightid = '%s', planetype = '%s', dep = '%s', arr = '%s', depcount = %d, arrcount = %d WHERE amdarid = '%s'"
                                                %(x,planetype,val[1],val[0],dict1[i][val[1]],dict1[i][val[0]],i))
                            countdb = self.session.execute("select * from Planetypematch where amdarid = '%s'" %i).fetchone()
                            if countdb:
                                if planetype in [countdb[2],countdb[5],countdb[8]]:
                                    dbc = [countdb[2],countdb[5],countdb[8]].index(planetype) + 1
                                    self.session.execute("UPDATE Planetypematch SET matchcount%s = matchcount%s + 1 where amdarid = '%s'" %(dbc,dbc,i))
                                elif None in [countdb[2],countdb[5],countdb[8]]:
                                    dbc = [countdb[2],countdb[5],countdb[8]].index(None) + 1
                                    self.session.execute(f"UPDATE Planetypematch SET matchcount{dbc} = 1, flightid{dbc} = '{x}', Planetype{dbc} = '{planetype}' where amdarid = '{i}'")  
                            if matchedType%5 == 0:
                                self.session.commit()
                            print('\n update planetype %s matched for %s and %s'%(planetype,x,i))
                            break    
                        elif planetype == 'del':
                            self.session.execute(f"delete from Route where flightid = '{x}'") 
                            self.session.commit()
        self.session.commit()
        with open('./statistic/RouteTypeMatchResult.txt','a') as RRstat:    
            RRstat.write(f"total unique ID : {totalunique} , total number of matched route: {matchedRoute}, total number of matched type : {matchedType} ")

    def get_route(self,dep,arr,_date):   
        b = self.api.getRoutebyPort(dep,arr)
        b += self.api.getRoutebyStat(dep,arr,_date) + self.api.getRoutebyAware(dep,arr)
        if not b:
            return []
        for x in b:
            indb = self.session.execute("select * from Route where flightid = '%s'" %x).fetchone()
            if not indb:
                self.session.execute("insert into Route ( flightid, dep,arr) VALUES( '%s' , '%s' , '%s')"
                                %(x,dep,arr)) 
                self.session.commit()
        return b
    

    def remove_firstline_arep(self):
        for file in os.listdir('./rawdata/amdw'):
            if file[:5] == 'AIREP':
                with open('./rawdata/amdw/'+file,'r') as fin:
                    data = fin.read().splitlines(True)
                with open('./rawdata/amdw/'+file,'w') as fout:
                    fout.writelines(data[1:])

    def filterDataByaltitude(self,alt=3000, amdarid =[]):
        dict1 = {}
        with open('./filterResult.txt','a') as stat:
            for file in os.listdir('./rawdata/amdw'):
                unfiltered = 0
                filtered = 0
                stat.write(f'filter statistic for file {file} \n')
                with open('./rawdata/amdw/'+file,'r') as fin:
                    data = fin.read().splitlines(True)
                    unfiltered = len(data)
                
                for x in data:
                    tmp = x.split()
                    try:
                        if tmp[0] not in dict1:
                            dict1[tmp[0]] = float(tmp[5])
                        else:
                            dict1[tmp[0]] = max(dict1[tmp[0]],float(tmp[5]))
                    except:
                        pass

                with open('./rawdata/amdw/'+file,'w') as fout:
                    for x in data:
                        tmp = x.split()
                        try:
                            if amdarid:
                                if float(tmp[5]) <  alt and tmp[0] in amdarid:
                                    fout.write(x)
                                    filtered += 1
                            else:
                                if float(tmp[5]) < alt:
                                    fout.write(x)
                                    filtered += 1
                        except:
                            continue
                stat.write(f'unfiltered record for this file is {unfiltered} \n')
                stat.write(f'after filter by altitude below {alt}, number of records is {filtered}\n')

    def writePlanetypedate(self,day = 0):
        today = date.today() 
        lastweek = today - timedelta(days=day)
        f = open(f"aircrafttype_{str(today).replace('-','')}_{str(lastweek).replace('-','')}.txt", "a")
        res = self.session.execute("select * from planetype")
        f.write("amdar    flightid  planetype  dep    depcount  arr  arrcount  datasource \n")
        for row in res:
            f.write(f"{row[0]}  {row[1]}   {row[2]}      {row[5]}     {row[6]}       {row[7]}  {row[8]}       {row[9]} \n")
        f.close()

    def writeMatchPlanetypedate(self):
        today = date.today() 
        lastweek = today - timedelta(days=7)
        f = open(f"aircrafttype_{str(today).replace('-','')}_{str(lastweek).replace('-','')}_matchtype.txt", "a")
        res = self.session.execute("select * from planetypematch")
        f.write("amdar    flightid1    planetype1     matchcount1      flightid2     planetype2      matchcount2      flightid3      planetype3      matchcount3 \n")
        for row in res:
            f.write(f"{row[0]}  {row[1]}        {row[2]}            {row[3]}                {row[4]}            {row[5]}            {row[6]}            {row[7]}            {row[8]}            {row[9]} \n")
        f.close()

    def loaddata_statistic(self,amdarids,alt_filter):
        dict2 = {i : 0 for i in amdarids}
        dictfilter = {i: 0 for i in amdarids}
        dict1 = {}

        for file in os.listdir('./rawdata/amdw'):
            with open('./rawdata/amdw/'+file,'r') as fin:
                data = fin.read().splitlines(True)
                for x in data:
                    tmp = x.split()
                    if tmp[0] in amdarids:
                        dict2[tmp[0]] += 1
                        try:
                            if tmp[0] not in dict1:
                                dict1[tmp[0]] = float(tmp[5])
                            else:
                                dict1[tmp[0]] = min(dict1[tmp[0]],float(tmp[5]))
                        except:
                            pass
                for x in data:
                    tmp = x.split()
                    try:
                        if float(tmp[5]) <  alt_filter and tmp[0] in t:
                            dictfilter[tmp[0]] += 1
                    except:
                        pass

        f = open(f"statistic_{alt_filter}_alldata.txt", "a")
        f.write(" \n amdarid      unfiltered record       filtered record \n")
        for x in amdarids:
            f.write(f'{x}          {dict2[x]}                        {dictfilter[x]} \n')
        
        dict1 = {i: {} for i in amdarids}
        f.write('\n ************************ airport *********** \n')
        f.write("amdar    flightid  planetype  dep    depcount  arr  arrcount  datasource \n")
        apis = api()

        for file in os.listdir('./rawdata/amdw'):
            with open('./rawdata/amdw/'+file,'r') as fin:
                data = fin.read().splitlines(True)
                for x in data:
                    tmp = x.split()
                    match = apis.get_airport(float(tmp[3]),float(tmp[4]))
                    if match != None:
                        match = '*' + match
                        if match not in dict1[tmp[0]]:
                            dict1[tmp[0]][match] = 1
                        else:
                            dict1[tmp[0]][match] += 1
        for x in dict1:
            f.write(f'\n for amdarid {x} \n')
            for j in dict1[x].keys():
                f.write(f' {j}        {dict1[x][j]} \n')
        f.close()
        apis.close()

class airlinedb():
    def loaddata(self):
        session = session_factory()
        count = 0
        with open('./rawdata/airlines.dat') as fp:
            for line in fp:
                tmp = line.split(',')
                tmp = [i.replace('"','').replace("'","").replace('\n','') for i in tmp]
                if tmp[7] == 'Y':
                    session.execute(f"insert into Airline (iata, icao, name) values ('{tmp[3]}', '{tmp[4]}', '{tmp[1]}')")
                    count += 1
        try:
            session.commit()
            print('successfully inserted %d row'% count)
        except:
            print('error')
            session.rollback()
            session.flush()
