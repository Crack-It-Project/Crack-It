#!/usr/bin/python3
import requests
import MySQLdb as mariadb
import pika
import sys
import json
#========================================================================
#MODULE DELCARATION AND CONFIGURATION SECTION

def crawler_pastebin(url):
    #fetch url and parse json
    scraping = requests.get(url).json()
    returns = []
    #get the scrape_url for each item returned by the API
    for item in scraping:
        returns.append(item.get('scrape_url'))
    return returns

def crawler_github(url):
    returns = []
    data_json = requests.get(url).json()
    for item in data_json["items"]:
        returns.append(item["html_url"])
    return returns

def crawler_git(url):
    returns = [url]
    return returns

#add your crawler in this dict to register it, the key is the one the DB should use
crawlers = {
  "pastebin": crawler_pastebin,
  "github": crawler_github,
  "git": crawler_git
}

#========================================================================
#SETUP PHASE

#connecting to rabbitMQ
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='localhost'))
channel = connection.channel()
#connecting to mariadb
mariadb_connection = mariadb.connect(user='python', password='pythonpython', database='crack_it')


#create the exchange if it does not exist already
channel.exchange_declare(exchange='urls', exchange_type='fanout')

#========================================================================

#QUERY INIT
cursor = mariadb_connection.cursor()
_SQL = (""" 
        SELECT * FROM source
        """)
#QUERY EXECUTE
cursor.execute(_SQL)
result = cursor.fetchall()

for row in result:
    #We call the module the row is aksing for (value: row[2]) in the crawler dict, which is a registry of all modules. We then pass it the url from the DB row 
    #the result is an array of urls
    result=crawlers[row[2]](row[1])
    for value in result:
        #assemble a json message to easely combine the two values, m=> module to use, v => url
        message=json.dumps({"m": row[2], "v": value})
        #send the message through rabbbitMQ using the urls exchange
        channel.basic_publish(exchange='urls', routing_key='', body=message)

#closing connection to rabbitMQ
connection.close()