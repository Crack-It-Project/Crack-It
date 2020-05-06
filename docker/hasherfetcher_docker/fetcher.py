#!/usr/bin/python3
import requests
import MySQLdb as mariadb
import pika
import sys
import json
import time

#========================================================================
#SETUP PHASE


#connecting to rabbitMQ

success=False
while not success:
    try:
        #connecting to mariadb
        mariadb_connection = mariadb.connect(host='db', user='python', password='pythonpython', database='crack_it')
        success=True
    except mariadb._exceptions.OperationalError as e:
        success=False
        print("Failed to connect to database... Retrying in 5 seconds.")
        time.sleep(5)

success=False
while not success:
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq'))
        channel = connection.channel()
        success=True
    except (pika.exceptions.AMQPConnectionError) as e:
        success=False
        print("Failed to connect to rabbitMQ ... Retrying in 5 seconds.")
        time.sleep(5)


#create the exchange if it does not exist already
channel.exchange_declare(exchange='hashes', exchange_type='fanout')

result = channel.queue_declare(queue='cracker_hashes_queue', exclusive=False, auto_delete=False)
queue_name = result.method.queue

#bind the queue to the url exchange
channel.queue_bind(exchange='hashes', queue=queue_name)


#========================================================================

#QUERY INIT
cursor = mariadb_connection.cursor()
_SQL = (""" 
        SELECT * FROM hash
        """)
#QUERY EXECUTE
cursor.execute(_SQL)
result = cursor.fetchall()

for row in result:

    message=json.dumps({"m": row[2], "v": value})
    #send the message through rabbbitMQ using the urls exchange
    channel.basic_publish(exchange='hashes', routing_key='', body=message)

#closing connection to rabbitMQ
connection.close()