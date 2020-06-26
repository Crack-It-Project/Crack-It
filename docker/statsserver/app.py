#!/bin/env python3
from flask import Flask, render_template, request, jsonify
import cracklib
import os
from zxcvbn import zxcvbn
import simplejson as json
import MySQLdb as mariadb
import threading
from datetime import datetime, timedelta
import time
import sys

dictPath="/dict/cracklib"

app = Flask(__name__)

cache= {
    "date": None,
    "hash": {
        "count": None
    },
    "password": {
        "count": None,
        "top10": None,
        "lastweek": None
    }
}


def getDB():
    success=False
    while not success:
        try:
            mariadb_connection = mariadb.connect(host='db_dict', user=os.environ['MYSQL_USER'], password=os.environ['MYSQL_PASSWORD'], database='crack_it')
            success=True
        except mariadb._exceptions.OperationalError as e:
            success=False
            print("Failed to connect to database... Retrying in 5 seconds.", file=sys.stderr)
            time.sleep(5)
    return mariadb_connection


def updateCache(cache, cacheLock):
    from datetime import datetime
    todaydate=datetime.now()
    print("Updating", file=sys.stderr)

    cursor = getDB().cursor()

    _SQL = ("""
            SELECT * FROM dict ORDER BY seen DESC LIMIT 10
            """)
    cursor.execute(_SQL)
    top10 = cursor.fetchall()

    cursor = getDB().cursor()

    _SQL = ("""
            SELECT count(*) FROM dict
            """)
    cursor.execute(_SQL)
    pcount=cursor.fetchall()

    cursor = getDB().cursor()
    _SQL = ("""
            SELECT count(*) FROM hash
            """)
    cursor.execute(_SQL)
    hcount = cursor.fetchall()

    cursor = getDB().cursor()

    _SQL = ("""
            SELECT count(dictt.id), days.lastdays, DATE(days.weekdaydate), dictt.date FROM ( select DAYOFWEEK(DATE_ADD(NOW(), INTERVAL -6 DAY)) as lastdays, DATE_ADD(NOW(), INTERVAL -6 DAY) as weekdaydate union select DAYOFWEEK(DATE_ADD(NOW(), INTERVAL -5 DAY)) as lastdays, DATE_ADD(NOW(), INTERVAL -5 DAY) as weekdaydate union select DAYOFWEEK(DATE_ADD(NOW(), INTERVAL -4 DAY)) as lastdays, DATE_ADD(NOW(), INTERVAL -4 DAY) as weekdaydate union select DAYOFWEEK(DATE_ADD(NOW(), INTERVAL -3 DAY)) as lastdays, DATE_ADD(NOW(), INTERVAL -3 DAY) as weekdaydate union select DAYOFWEEK(DATE_ADD(NOW(), INTERVAL -2 DAY)) as lastdays, DATE_ADD(NOW(), INTERVAL -2 DAY) as weekdaydate union	select DAYOFWEEK(DATE_ADD(NOW(), INTERVAL -1 DAY)) as lastdays, DATE_ADD(NOW(), INTERVAL -1 DAY) as weekdaydate union select DAYOFWEEK(DATE_ADD(NOW(), INTERVAL 0 DAY)) as lastdays, DATE_ADD(NOW(), INTERVAL 0 DAY) as weekdaydate  ) days LEFT JOIN ( SELECT date, id FROM dict WHERE date >= DATE_ADD(NOW(), INTERVAL -7 DAY) ) dictt ON DAYOFWEEK(dictt.date) = days.lastdays GROUP BY days.lastdays ORDER BY days.weekdaydate DESC
            """)
    cursor.execute(_SQL)
    lastweek = cursor.fetchall()

    cacheLock.acquire()
    print("Saving", file=sys.stderr)
    cache["password"]["count"]=pcount
    cache["password"]["top10"]=top10
    cache["password"]["lastweek"]=lastweek
    cache["hash"]["count"]=hcount
    cache["date"]=todaydate
    cacheLock.release()


cacheLock = threading.Lock()
updateThread = threading.Thread(target=updateCache, args=(cache, cacheLock)) 
updateThread.daemon = True



def scheduleUpdate():
    global updateThread, cache, cacheLock, updateCache
    delay=timedelta(hours=2)
    if cache["date"] is None or datetime.now()-cache["date"] >= delay:
        updateThread.join(timeout=0.0)
        if updateThread.is_alive():
            print("Already updating...", file=sys.stderr)
        else:
            updateThread = threading.Thread(target=updateCache, args=(cache, cacheLock)) 
            updateThread.start()



def timedeltaserialize(o):
    if isinstance(o, timedelta):
        return o.__str__()

@app.route("/api/password/check", methods=['POST']) 
def password_check():
    global dictPath
    password = request.form["password"]
    dictcheck="Ok"
    try:
        result = cracklib.VeryFascistCheck(password, None, dictPath)
    except ValueError as err:
        dictcheck=str(err)
    results = zxcvbn(password)

    return json.dumps({"overall": dictcheck.capitalize(), "details": results}, default=timedeltaserialize)

@app.route("/api/password/stats/top10", methods=['GET']) 
def password_stats_top10(): 
    global cache
    scheduleUpdate()
    return jsonify({"date": cache["date"], "data": cache["password"]["top10"]})

@app.route("/api/password/stats/count", methods=['GET']) 
def password_stats_count(): 
    global cache
    scheduleUpdate()
    return jsonify({"date": cache["date"], "data": cache["password"]["count"]})

@app.route("/api/hash/stats/count", methods=['GET'])
def hash_stats_count(): 
    global cache
    scheduleUpdate()
    return jsonify({"date": cache["date"], "data": cache["hash"]["count"]})

@app.route("/api/password/stats/lastweek", methods=['GET']) 
def password_stats_lastweek():
    global cache
    scheduleUpdate()
    return jsonify({"date": cache["date"], "data": cache["password"]["lastweek"]})


if __name__ == "__main__":
    updateThread.start()
    app.run(host='0.0.0.0')
