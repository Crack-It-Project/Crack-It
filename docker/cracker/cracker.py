#!/usr/bin/python3

import sys
import os
import re
import copy
import json
from mysqldb import DB
import requests
import shutil
import os.path
from os import path
import pika
import time
import subprocess

db = DB(host='db_dict', port=3306, user=os.environ['MYSQL_USER'], password=os.environ['MYSQL_PASSWORD'], database='crack_it')
db.connect()

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
	check_bdd = "SELECT str FROM hash WHERE str = %s AND clear IS NOT NULL"
	update_bdd_hash = "UPDATE hash SET clear = %s WHERE str = %s"
	insert_bdd_clear = "INSERT INTO dict (password) VALUES (%s) ON DUPLICATE KEY UPDATE seen=seen+1" # Modifier requête pour checker si même repo ne pas incrémenter seen (cf. parser)
	insert_bdd_clear_notAhash = "INSERT INTO dict (password, seen) VALUES (%s, %s) ON DUPLICATE KEY UPDATE seen=seen+%s"
	get_origin_hash_seen = "SELECT count(*) FROM origin_hash WHERE item = %s"
	move_origin_data = "INSERT INTO origin_dict (srckey, item) SELECT srckey, (SELECT id FROM dict WHERE password = %s) FROM origin_hash WHERE item = %s"
	delete_old_origin_data = "DELETE FROM origin_hash WHERE item = %s"
	delete_old_hash = "DELETE FROM hash WHERE id = %s"
	get_hash_ID = "SELECT id FROM hash WHERE str = %s"


	# Get Hashs
	rabbitMQ_data = body

	# Parse JSON into array
	rabbitMQ_data_array = json.loads(rabbitMQ_data)

	# Does the hash exist in db ?
	hash = rabbitMQ_data_array['value']
	cursor = db.query(check_bdd, (hash,))
	result = cursor.fetchone()
	print("Processing Hash : "+rabbitMQ_data_array['value'])

	hash_presence_in_bdd = True

	os.system("touch cracked.txt")

	if result == None:
		hash_presence_in_bdd = False
		success_token = False
	else:
		print("Hash already exists !")
		success_token = True

	notAHash=0
	if hash_presence_in_bdd == False:

		# Get Hash types (numbers) for hash types in hashcat
		for hashTypesNumber in rabbitMQ_data_array['possibleHashTypes']:
			hashType = str(hashTypesNumber)

			# hashs cracking
			try:
				crack = subprocess.check_output(["hashcat","-a","0", "--show", "-m", hashType, "-o", "cracked.txt", "--force", hash, "dict/dict.txt"], stderr=subprocess.STDOUT, shell=False)
				if crack is not '':
					print("=======")
					print(crack)
					print("=======")
			except subprocess.CalledProcessError as e:
				error=e.output.decode()
				
				if "Hash-value exception" in error or "Separator unmatched" in error:
					notAHash+=1			
				else:
					print("Unexpected error : "+error)
				print("Hashcat failed.")
				


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
				cursor = db.query(insert_bdd_clear, (val_clear,))
				db.commit()
				print("Dictionnary has been updated ...")

				# Hash password db insert
				val_hash = [hash, hashType, val_clear]		# Link foreign key for clear password
				cursor = db.query(insert_bdd_hash, val_hash)
				db.commit() #must commit to get the inserted id
				cursor = db.query(update_bdd_hash, (cursor.lastrowid,val_hash))
				db.commit()
				print(cursor.rowcount, "Hashed password was inserted")
				
				# Erase cracked.txt file
				os.system("rm cracked.txt")
				# Create a new one
				os.system("touch cracked.txt")
				pass

			# Fail
			else:
				pass
			

	if notAHash == len(rabbitMQ_data_array['possibleHashTypes']):
		print("Not a hash ! this is probably a password ! Saving in DB.")
		hashId=db.query(get_hash_ID, (hash,)).fetchall()[0][0]
		print("Old Hash ID: "+str(hashId))
		cursor = db.query(get_origin_hash_seen, (hashId,))
		count=cursor.fetchall()[0][0]
		cursor = db.query(insert_bdd_clear_notAhash, (hash, count, count))
		cursor = db.query(move_origin_data, (hash,hashId))
		cursor = db.query(delete_old_origin_data, (hashId,))
		cursor = db.query(delete_old_hash, (hashId, ))
		db.commit()
		print("Done")
	else:
		print("==============")
		print("Not going to save in DB.")
		print("Errors: "+str(notAHash))
		print("Hash Types : "+str(len(rabbitMQ_data_array['possibleHashTypes'])))
		print("Hash in question : "+hash)
	

	# Erase cracked.txt file
	os.system("rm cracked.txt 2> /dev/null")

	# Insert hash in db if the script hasn't cracked it
	if success_token == False:
		#possibleHashTypes = str(rabbitMQ_data_array['possibleHashTypes'])
		#val_hash = [hash, possibleHashTypes, None]
		#cursor.execute(insert_bdd_hash, val_hash)
		#mariadb_connection.commit()
		print("Hash not decrypted")
	ch.basic_ack(method.delivery_tag)


channel.basic_consume(queue_name2, callback, auto_ack=False) #registering processing function

channel.start_consuming() #start processing messages in the url queue

connection.close()
