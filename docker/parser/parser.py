#!/usr/bin/python3
from mysqldb import DB
import pika
import sys
import json
import re as regex
import hashid
import os
import time
from zxcvbn import zxcvbn
import math
import subprocess
import threading
import functools
import logging
tmpDirectory="/sharedTmp"

print("App start")

#========================================================================
#Setting up regular expressions

#This regular expression is used to check passwords list in this format TextOrUser:Password  Whitespaces between the semicolon : are ignored.
#We first compile it, which create an object we can sue to apply the regex, it is also faster than using the re. function directly
#I had to split the negative look-behinds (?<!https) into multiple because python does not seems to support them together (eg : (?<!https|http))
idSemicolumnThenItem = regex.compile(r'\b[^:^\n0-9]+(?<!http)(?<!https)(?<!ftp)(?<!sftp)(?<!rtmp)(?<!ws):([^\s\n]+)') #TODO: check this

hashID = hashid.HashID()

def ack_message(channel, delivery_tag):
    if channel.is_open:
        channel.basic_ack(delivery_tag)
    else:
        pass

def wccount(filename):
    out = subprocess.Popen(['wc', '-l', filename],
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT
                         ).communicate()[0]
    return int(out.partition(b' ')[0])

def mapValue(x, in_min, in_max, out_min, out_max):
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
#========================================================================

#Main function
#Parses a given file and then extracts all passwords and hashes founded. Return a mutli-level dict
def analyzeFile(fileDscrpt, weight, linecount):
    global idSemicolumnThenItem, hashID

    returnHashes=[]
    returnPasswords=[]
    #return dict structure
    results = {
        "hashes": [],
        "passwords": []
        }
    matches=0 #used to set a minimum number of matches to prevent non list files to trigger an action
    lines=0 #used to compute average line size

    #this block is computing the avergae line size of the first range(n) lines, if we have shrot lines in a very long file, this is probably a password list (with no username)
    linesizeavg=0
    for line in (fileDscrpt.readline() for i in range(200)):
        linesizeavg+=len(line)
        lines+=1
    fileDscrpt.seek(0)
    linesizeavg /= lines

    method="" #depending on the previous result, we choose a full passwordlist parsing method or a user:password parsing regex
    if os.fstat(fileDscrpt.fileno()).st_size > 100000 and linesizeavg < 32:
        method="fulllist"
    else:
        method="semicolonlist"
    lines=0 #we now use this to check for how many lines are not matched by the regex

    print("Method: ["+method+"]")

    for line in fileDscrpt:  #we parse line by line

        lines += 1
        
        if method == "semicolonlist":
            d = idSemicolumnThenItem.match(line) #apply the regex
            if lines > matches + 20:   #number of missed matches to consider the file invalid
                print("Too many lines are not matching, stopping !")
                return []
                break

        if method == "fulllist" or d: #if the regex match or we are in fulllist mode (= each line is a "string of interest")
            matches += 1
            if method == "semicolonlist":
                item=d.group(1).lstrip() #strip leading spaces if there were some after the semicolon
            else:
                item=line # the whole line is kept in fulllist mode
            item=item.rstrip('\r\n') #remove trailing newlines (works for any combinaisons, so it works for DOS, OSX and Unix line endings)
            hashType = hashID.identifyHash(item)  #try to identify a hash
            hashcatcount=0 #number of possible hash types identified
            #hash data structure declaration, this is what is sent via rabbitMQ. This is stored in the return dict in an array of these
            hashSummary={
                        "value": "",
                        "possibleHashTypes": [],
                        "possibleHashTypesNames": []
                    }
            #for each identified modes, we store them in the struct
            for mode in hashType:
                if mode.hashcat is not None: #we only keep hashes hashcat can break, it should also filter out obscure hashes that got matched by a hash regex (by hashid)
                    #logging.debug(mode.name)
                    #logging.debug(mode.hashcat)
                    hashSummary["possibleHashTypes"].append(mode.hashcat)
                    hashSummary["possibleHashTypesNames"].append(mode.name)
                    hashcatcount+=1

            #if there are no match, it must me plain text
            isPassword=False
            if hashcatcount > 0:
                #logging.debug("Testing for false positive")                  #TODO: find a better way because we're going to have a lot of false positive.
                results = zxcvbn(item)
                if results['guesses_log10'] >= 11:
                    hashSummary["value"]=item
                    #sendHash(hashSummary, srckey)
                    returnHashes.append(hashSummary)
                else:
                    print("Skipping '"+item+"' because entropy seems to be too low.")
                    isPassword=True
            else:
                isPassword=True
            if isPassword:
                localweight=weight
                if method == "fulllist":
                    localweight=mapValue(linecount-lines, 1, linecount, 1, weight)
                #registerPassword(item, srckey, localweight)
                returnPasswords.append((item, localweight))
    if matches==0:
        print("Found nothing in this file.")
    print("done")
    if not returnHashes or not returnPasswords:
        raise ValueError('Found nothing and both list empty')   
    else:
        print(str(len(returnHashes)))
        print(str(len(returnPasswords)))
    return returnHashes, returnPasswords

#========================================================================

#called fo each item in the queue
def callback(ch, method, properties, body, args):
    (channel, connection, threads) = args
    params=json.loads(body) #parse the json packet
    delivery_tag = method.delivery_tag
    t = threading.Thread(target=processOne, args=(delivery_tag, params, channel, connection))
    t.start()
    threads.append(t)

def processOne(delivery_tag, params, channel, connection):
    
    mariadb_connection = DB(host='db_dict', port=3306, user=os.environ['MYSQL_USER'], password=os.environ['MYSQL_PASSWORD'], database='crack_it')
    #QUERY INIT
    mariadb_connection.connect()
    
    print(" ") #For log clarity
    print("processing:")
    print(params["v"])

    dbactioncount=[0]
    
    filename=os.path.join(tmpDirectory,params["v"])
    
    #Check if file exist to avoid errors
    if os.path.isfile(filename):
        #Latin 1 will work for utf-8 but may mangle character if we edit the stream (see the official doc)
        linecount=wccount(filename)
        try:
            with open(filename, 'r', encoding="latin-1") as file:
                print("Processing file : "+filename)
                hashes, passwords = analyzeFile(file, params["w"], linecount)
                
            for item_hash in hashes:
                dbactioncount[0]+=sendHash(item_hash, params["s"], mariadb_connection)
                commitIfNecessary(mariadb_connection, dbactioncount)
            for item_password in passwords:
                dbactioncount[0]+=registerPassword(*item_password, params["s"], mariadb_connection)
                commitIfNecessary(mariadb_connection, dbactioncount)
            print("LAST COMMIT")
            mariadb_connection.commit()
        except ValueError:
            print("Nothing was found in this file. Discarding it....")
        finally:
            print("Deleting source file")
            os.remove(filename)
            print("ACK-ING the message")
    else:
        print("FILE DOES NOT EXIST...")
        mariadb_connection.commit()
        print("Discarding (ACK-ING) the message")
    ack_callback = functools.partial(ack_message, channel, delivery_tag)
    connection.add_callback_threadsafe(ack_callback)
#========================================================================

def commitIfNecessary(mariadb_connection, dbactioncount):
    if dbactioncount[0] >=1000:
        print("COMMIT")
        mariadb_connection.commit() #send everything pending to the database
        dbactioncount[0] = 0
        

#========================================================================

def registerPassword(password, weight, srckey, mariadb_connection):
    print("[Saving] Password: "+password+" . Weight: "+str(weight))
    sql="INSERT INTO dict (password, seen) VALUES (%s, %s) ON DUPLICATE KEY UPDATE seen = (if((SELECT count(*) FROM (select * from origin_dict INNER JOIN dict ON dict.id = origin_dict.item WHERE origin_dict.srckey = %s AND dict.password = %s) s) > 0, dict.seen, dict.seen+%s));" #insert the password, and if it already exist, increment the "seen" counter only it we didn't get it from the same source
    sql2 = "INSERT INTO origin_dict(srckey, item) VALUES (%s, (select id from dict WHERE password = %s)) ON DUPLICATE KEY UPDATE srckey=srckey;" #remember from which source the entry is from, if this is the first time we see it.

    try:
        mariadb_connection.query(sql, (password, weight, srckey, password, weight))
        mariadb_connection.query(sql2, (srckey, password))

        

    except Exception as err:
        print("[Saving] [Error] ")
        print(str(err))
    
    return 2 #two queries

#========================================================================

def sendHash(ihash, srckey, mariadb_connection):
    insert_bdd_hash = "INSERT INTO hash (str, algo, clear) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE str=str;"
    insert_origin = "INSERT INTO origin_hash(srckey, item) VALUES (%s, (select id from hash WHERE str = %s)) ON DUPLICATE KEY UPDATE srckey=srckey;" 

    print("[Saving] Hash: "+ihash["value"])
    mariadb_connection.query(insert_bdd_hash, (ihash["value"], json.dumps(ihash["possibleHashTypes"]), None))

    mariadb_connection.query(insert_origin, (srckey, ihash["value"]))
    return 2 #two queries
    
#========================================================================

########################################## END FUNCTONS #######################################

def main():
    threads = []
    #Connecting to RabbitMQ
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


    #========================================================================
    #Setting up queues

    #Create the exchanges if they do not exist already
    channel.exchange_declare(exchange='files', exchange_type='fanout')  #to get url to parse
    #channel.exchange_declare(exchange='hashes', exchange_type='fanout') #to send all hashes to cracker instances

    #announce we have a queue because we are a data consumer
    queue_name = 'parser_files_queue'
    result = channel.queue_declare(queue=queue_name, exclusive=False, auto_delete=False)
    #bind the queue to the url exchange
    channel.queue_bind(exchange='files', queue=queue_name)

    ######################################### START #########################################
    print("Setting up callback.")
    
    on_message_callback = functools.partial(callback, args=(channel, connection, threads))
    channel.basic_consume(queue_name, on_message_callback, auto_ack=False) #registering processing function

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

    #========================================================================

if __name__ == '__main__':
    main()
