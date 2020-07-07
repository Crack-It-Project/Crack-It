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
import threading
import functools

#from pathlib import Path

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

def ack_message(channel, delivery_tag):
    if channel.is_open:
        channel.basic_ack(delivery_tag)
    else:
        pass

def callback(ch, method, properties, body, args):
    (channel, connection, threads) = args
    params=json.loads(body) #parse the json packet
    delivery_tag = method.delivery_tag
    t = threading.Thread(target=processOne, args=(delivery_tag, params, channel, connection))
    t.start()
    threads.append(t)

def processOne(delivery_tag, rabbitMQ_data_array, channel, connection):

	db = DB(host='db_dict', port=3306, user=os.environ['MYSQL_USER'], password=os.environ['MYSQL_PASSWORD'], database='crack_it')
	db.connect()

	# Prepare requests
	print("------------------------------Start------------------------------")
	check_bdd = "SELECT str FROM hash WHERE str = %s AND clear IS NOT NULL"
	update_bdd_hash = "UPDATE hash SET clear = %s WHERE str = %s"
	insert_bdd_clear = "INSERT INTO dict (password) VALUES (%s) ON DUPLICATE KEY UPDATE seen=seen+1" # Modifier requête pour checker si même repo ne pas incrémenter seen (cf. parser)
	insert_bdd_clear_notAhash = "INSERT INTO dict (password, seen) VALUES (%s, %s) ON DUPLICATE KEY UPDATE seen=seen+%s"
	get_origin_hash_seen = "SELECT count(*) FROM origin_hash WHERE item = %s"
	move_origin_data = "INSERT INTO origin_dict (srckey, item) SELECT srckey, (SELECT id FROM dict WHERE password = %s) FROM origin_hash WHERE item = %s"
	delete_old_origin_data = "DELETE FROM origin_hash WHERE item = %s"
	delete_old_hash = "DELETE FROM hash WHERE id = %s"
	get_hash_ID = "SELECT id FROM hash WHERE str = %s"

	# Does the hash exist in db ?
	hash = rabbitMQ_data_array['value']
	cursor = db.query(check_bdd, (hash,))
	result = cursor.fetchone()
	print("Processing Hash : "+rabbitMQ_data_array['value'])

	hash_presence_in_bdd = True

	hashId=db.query(get_hash_ID, (hash,)).fetchall()[0][0]

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
			print("------------------------------NewTry------------------------------")
			hashType = str(hashTypesNumber)

			# hashs cracking
			
			print(hash,  file=open('hash.txt', 'w'))
			print(str(path.exists("hash.txt")))
				
			#crack = subprocess.check_output(["hashcat","-a","0", "--show", "-m", hashType, "-o", "cracked.txt", "--force", hash, "dict/dict.txt"], stderr=subprocess.STDOUT, shell=False)
			print("Hashtype: "+str(hashType))
			"""
			try:
				#hashcat_proc= subprocess.Popen("hate_crack/hate_crack.py hash.txt "+str(hashType), encoding="latin1", input="2\n".encode(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
				while hashcat_proc.poll() is None:
					try:
						for line in hashcat_proc.stdout:
							if "Hash-value exception" in line or "Separator unmatched" in line:
								notAHash+=1		
								print("[hate_crack] [ERROR] "+line)
							print("[hate_crack] "+line)
					except (BrokenPipeError, IOError):
						print ('Caught InnerBrokenPipeError')
			except (BrokenPipeError, IOError):
				print ('Caught OuterBrokenPipeError')"""
			try:
				crack = subprocess.check_output(["hate_crack/hate_crack.py", "hash.txt", str(hashType)], input="2\n".encode(), stderr=subprocess.STDOUT, shell=False)	
				for line in crack:
					if "Hash-value exception" in line or "Separator unmatched" in line:
						notAHash+=1		
						print("[hate_crack] [ERROR] "+line)
					print("[hate_crack] "+line)
			except subprocess.CalledProcessError as e:
				print("Hashcat failed: ")
				print(e.output)
			# Success
			if path.isfile("hash.txt.out"):
				if (path.getsize("hash.txt.out") > 0):
					print("------------------------------Success------------------------------")
					success_token = True
					cracked = open("hash.txt.out", "r")
					password_data = cracked.readline().split(":")
					password_clear = password_data[1]
					cracked.close()

					# Clear password db insert
					cursor = db.query(insert_bdd_clear, (password_clear,))
					db.commit()
					print("Dictionnary has been updated ... Added: "+password_clear)

					cursor = db.query(update_bdd_hash, (cursor.lastrowid,hash))
					db.commit()
					print(cursor.rowcount, "Linked hash to dict value.")
					
					# Erase cracked.txt file
					#os.remove("hash.txt.out")
					# Create a new one
					#os.system("touch cracked.txt")
					#Path('cracked.txt').touch()
				os.remove("hash.txt.out")
			os.remove("hash.txt")

	if notAHash == len(rabbitMQ_data_array['possibleHashTypes']):
		print("Not a hash ! this is probably a password ! Saving in DB.")
		
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
	print("------------------------------End------------------------------")
	ack_callback = functools.partial(ack_message, channel, delivery_tag)
	connection.add_callback_threadsafe(ack_callback)

threads=[]

on_message_callback = functools.partial(callback, args=(channel, connection, threads))
channel.basic_consume(queue_name2, on_message_callback, auto_ack=False) #registering processing function

try:
    channel.start_consuming()
except (KeyboardInterrupt, SystemExit):
    print("Shutting down.")
finally:
    channel.stop_consuming()
    # Wait for all to complete
    for thread in threads:
        thread.join()

    connection.close()