#!/usr/bin/python3

import sys
import os
import re
import copy
import json
import MySQLdb as mariadb
import requests
import shutil
import os.path
from os import path
import pika
import time

success=False
while not success:
    try:
        mariadb_connection = mariadb.connect(host='db', user='python', password='pythonpython', database='crack_it')
        success=True
    except mariadb._exceptions.OperationalError as e:
        success=False
        print("Failed to connect to database... Retrying in 5 seconds.")
        time.sleep(5)

# Create a Cursor object to execute queries
cursor = mariadb_connection.cursor()


success=False
while not success:
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq'))
        channel = connection.channel()
        channel.basic_qos(prefetch_count=1)
        success=True
    except (pika.exceptions.AMQPConnectionError) as e:
        success=False
        print("Failed to connect to rabbitMQ ... Retrying in 5 seconds.")
        time.sleep(5)



channel.exchange_declare(exchange='hashes', exchange_type='fanout') #to send all hashes to cracker instances


queue_name2 = 'cracker_hashes_queue'
result2 = channel.queue_declare(queue=queue_name2, exclusive=False, auto_delete=False)
#bind the queue to the url exchange
channel.queue_bind(exchange='hashes', queue=queue_name2)

def callback(ch, method, properties, body):
	# Prepare requests
	check_bdd = "SELECT str FROM hash WHERE str = %s"
	insert_bdd_hash = "INSERT INTO hash (str, algo, clear) VALUES (%s, %s, %s)"
	insert_bdd_clear = "INSERT INTO dict (password) VALUES (%s) ON DUPLICATE KEY UPDATE seen=seen+1" # Modifier requête pour checker si même repo ne pas incrémenter seen (cf. parser)



	# Get Hashs
	rabbitMQ_data = body

	# Parse JSON into array
	rabbitMQ_data_array = json.loads(rabbitMQ_data)

	# Does the hash exist in db ?
	hash = rabbitMQ_data_array['value']
	cursor.execute(check_bdd, (hash,))
	result = cursor.fetchone()

	hash_presence_in_bdd = True

	os.system("touch cracked.txt")

	if result == None:
		hash_presence_in_bdd = False
		success_token = False
	else:
		print("Hash already exists !")
		success_token = True


	if hash_presence_in_bdd == False:

		# Get Hash types (numbers) for hash types in hashcat
		for hashTypesNumber in rabbitMQ_data_array['possibleHashTypes']:
			hashType = str(hashTypesNumber)

			# hashs cracking
			crack = os.system("hashcat -a 0 -m "+ hashType +" -o cracked.txt --force "+ hash +" dict/dict.txt --show")	
			
			# Success
			if (os.stat("cracked.txt").st_size != 0):
				print("------------------------------Success------------------------------")
				success_token = True
				cracked = open("cracked.txt", "r")
				password_data = cracked.readline().split(":")
				password_clear = password_data[1]
				cracked.close()

				# Clear password db insert
				val_clear = (password_clear)
				cursor.execute(insert_bdd_clear, (val_clear,))
				mariadb_connection.commit()
				print("Dictionnary has been updated ...")

				# Hash password db insert
				val_hash = [hash, hashType, val_clear]		# Link foreign key for clear password
				cursor.execute(insert_bdd_hash, val_hash)
				mariadb_connection.commit()
				print(cursor.rowcount, "Hashed password was inserted")
				
				# Erase cracked.txt file
				os.system("rm cracked.txt")
				# Create a new one
				os.system("touch cracked.txt")
				pass

			# Fail
			else:
				pass

	# Erase cracked.txt file
	os.system("rm cracked.txt 2> /dev/null")

	# Insert hash in db if the script hasn't cracked it
	if success_token == False:
		possibleHashTypes = str(rabbitMQ_data_array['possibleHashTypes'])
		val_hash = [hash, possibleHashTypes, None]
		cursor.execute(insert_bdd_hash, val_hash)
		mariadb_connection.commit()
		print(cursor.rowcount, "Hash not decrypted was inserted in db")


channel.basic_consume(queue_name, callback, auto_ack=False) #registering processing function

channel.start_consuming() #start processing messages in the url queue

connection.close()
