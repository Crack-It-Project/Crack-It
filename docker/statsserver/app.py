#!/bin/env python3
from flask import Flask, render_template, request, jsonify
import cracklib
import os
from zxcvbn import zxcvbn
import simplejson as json
import MySQLdb as mariadb
from datetime import timedelta

app = Flask(__name__)
dictPath="/dict/cracklib"
#dictPath="/usr/lib/cracklib_dict"
# defining a route

def timedeltaser(o):
    if isinstance(o, timedelta):
        return o.__str__()

def getDB():
    success=False
    while not success:
        try:
            mariadb_connection = mariadb.connect(host='db_dict', user=os.environ['MYSQL_USER'], password=os.environ['MYSQL_PASSWORD'], database='crack_it')
            success=True
        except mariadb._exceptions.OperationalError as e:
            success=False
            print("Failed to connect to database... Retrying in 5 seconds.")
            time.sleep(5)
    return mariadb_connection

@app.route("/api/password/check", methods=['POST']) # decorator
def password_check(): # route handler function
    # returning a response
    password = request.form["password"]
    dictcheck="Ok"
    try:
        result = cracklib.VeryFascistCheck(password, None, dictPath)
    except ValueError as err:
        dictcheck=str(err)
    results = zxcvbn(password)

    return json.dumps({"overall": dictcheck.capitalize(), "details": results}, default=timedeltaser)

@app.route("/api/password/stats/top10", methods=['GET']) # decorator
def password_stats_top10(): # route handler function
    cursor = getDB().cursor()

    _SQL = (""" 
            SELECT * FROM dict ORDER BY seen DESC LIMIT 10
            """)
    cursor.execute(_SQL)
    result = cursor.fetchall()
    return jsonify(result)

@app.route("/api/password/stats/count", methods=['GET']) # decorator
def password_stats_count(): # route handler function
    cursor = getDB().cursor()

    _SQL = (""" 
            SELECT count(*) FROM dict
            """)
    cursor.execute(_SQL)
    result = cursor.fetchall()
    return jsonify(result)

@app.route("/api/hash/stats/count", methods=['GET']) # decorator
def hash_stats_count(): # route handler function
    cursor = getDB().cursor()
    _SQL = (""" 
            SELECT count(*) FROM hash
            """)
    cursor.execute(_SQL)
    result = cursor.fetchall()
    return jsonify(result)

@app.route("/api/password/stats/lastweek", methods=['GET']) # decorator
def password_stats_lastweek(): # route handler function
    cursor = getDB().cursor()

    _SQL = (""" 
            SELECT count(*) FROM dict WHERE date >= DATE_ADD(NOW(), INTERVAL -7 DAY) GROUP BY DAYOFWEEK(date) ORDER BY date DESC
            """)
    cursor.execute(_SQL)
    result = cursor.fetchall()
    return jsonify(result)

if __name__ == "__main__":
    app.run(host='0.0.0.0') 
