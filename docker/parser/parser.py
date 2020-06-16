#!/usr/bin/python3
from mysqldb import DB
import pika
import sys
import json
import re as regex
import hashid
import os
#import shutil
import time
from zxcvbn import zxcvbn

tmpDirectory="/sharedTmp"

#========================================================================
#Setting up regular expressions

#idSemicolumnThenItem = regex.compile('[^:^\n]*:([^\n]+)')
#idSemicolumnThenItem = regex.compile('\b(?!http|https|ftp|sftp|rtmp|ws)[^:^\n0-9]+:(?!\/\/)([^\n]+)') # make this regex way better here password starting with // won't work

#This regular expression is sued to check passwords list in this format TextOrUser:Password  Whitespaces between the semicolon : are ignored.
#We first compile it, which create an object we can sue to apply the regex, it is also faster than using the re. function directly
#I had to split the negative look-behinds (?<!https) into multiple because python does not seems to support them together (eg : (?<!https|http))
idSemicolumnThenItem = regex.compile(r'\b[^:^\n0-9]+(?<!http)(?<!https)(?<!ftp)(?<!sftp)(?<!rtmp)(?<!ws):([^\s\n]+)') #TODO: check this

#========================================================================
#MODULE DELCARATION AND CONFIGURATION SECTION

#========================================================================

#Main function
#Parses a given file and then extracts all passwords and hashes founded. Return a mutli-level dict
def analyzeFile(fileDscrpt, srckey, weight):
    global idSemicolumnThenItem, hashID
    

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
    if os.fstat(fileDscrpt.fileno()).st_size > 20000000 and linesizeavg < 32:
        method="fulllist"
    else:
        method="semicolonlist"
    lines=0 #we now use this to check for how many lines are not matched by the regex

    print("Method: ["+method+"]")

    for line in fileDscrpt:  #we parse line by line
        #print("Ligne: "+line)
        if method == "semicolonlist":
            d = idSemicolumnThenItem.match(line) #apply the regex
            #print("Applied regex")
            #print(d)

            if lines < 1000: #we don't really care about counting lines if we are over 1000, this is only used to detect if this is a list or not, and only on first lines
                lines += 1
            if lines > matches + 20:   #number of missed matches to consider the file invalid
                print("Too many lines are not matching, stopping !")
                return []
                break

        if method == "fulllist" or d: #if the regex match or we are in fulllist mode (= each line is a "string of interest")
            matches += 1 
            #print("Got One match")
            if method == "semicolonlist":
                item=d.group(1).lstrip() #strip leading spaces if there were some after the semicolon
            else:
                item=line # the whole line is kept in fulllist mode
            item=item.rstrip('\r\n') #remove trailing newlines (works for any combinaisons, so it works for DOS, OSX and Unix line endings)
            #print(item)
            #print("Checking for hash")
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
                    #print(mode.name)
                    #print(mode.hashcat)
                    hashSummary["possibleHashTypes"].append(mode.hashcat)
                    hashSummary["possibleHashTypesNames"].append(mode.name)
                    hashcatcount+=1

            #if there are no match, it must me plain text            
            isPassword=False
            if hashcatcount > 0: 
                #print("Got a hash")
                #print("Testing for false positive")                  #TODO: find a better way because we're going to have a lot of false positive.'
                results = zxcvbn(item)
                if results['guesses_log10'] >= 11:
                    hashSummary["value"]=item
                    sendHash(hashSummary)
                else:
                    print("Skipping '"+item+"' because entropy seems to be too low.")
                    isPassword=True
            else:
                isPassword=True
            if isPassword:
                registerPassword(item, srckey, weight)
                
    print("done")

#========================================================================

#called fo each item in the queue
def callback(ch, method, properties, body):
    global dbactioncount, cursor, mariadb_connection, channel
    params=json.loads(body) #parse the json packet
    print(" ") #For log clarity 
    print("processing:")
    print(params["v"])
    #datafiles=parsers[params["m"]](params["v"])  #we select and execute the appropriate parser by name from the parser list. (the parser name is also in the packet)
    # we get a file descriptor we can pass to analyseFile, we get a dict which contains everything extracted from it
    filename=os.path.join(tmpDirectory,params["v"])

    #Check if file exist to avoid errors
    if os.path.isfile(filename) == True :
        #Latin 1 will work for utf-8 but may mangle character if we edit the stream (see the official doc)
        with open(filename, 'r', encoding="latin-1") as file:
            print("Processing file : "+filename)
            analyzeFile(file, params["s"], params["w"])
        print("LAST COMMIT")
        mariadb_connection.commit()
        print("Deleting source file")
        os.remove(filename)
        print("ACK-ING the message")
        ch.basic_ack(method.delivery_tag)
    else :
        print("FILE DOES NOT EXIST...")
        mariadb_connection.commit()
        print("ACK-ING the message")
        ch.basic_ack(method.delivery_tag)

#========================================================================

def commitIfNecessary():
    global dbactioncount, mariadb_connection       
    if dbactioncount >=1000:
        print("COMMIT")
        mariadb_connection.commit() #send everything pending to the database   
        dbactioncount = 0

#========================================================================

def registerPassword(password, srckey, weight):
    global dbactioncount, mariadb_connection
    print("[Saving] Password: "+password)
    #sql = "INSERT INTO dict (password) VALUES (%s) ON DUPLICATE KEY UPDATE seen = if(CAST((select count(*) from origin_dict WHERE origin_dict.srckey = %s) AS UNSIGNED) > 0, dict.seen, dict.seen+1);"  
    sql="INSERT INTO dict (password, seen) VALUES (%s, %s) ON DUPLICATE KEY UPDATE seen = (if((SELECT count(*) FROM (select * from origin_dict INNER JOIN dict ON dict.id = origin_dict.item WHERE origin_dict.srckey = %s AND dict.password = %s) s) > 0, dict.seen, dict.seen+1))+%s;" #insert the password, and if it already exist, increment the "seen" counter only it we didn't get it from the same source
    sql2 = "INSERT INTO origin_dict(srckey, item) VALUES (%s, (select id from dict WHERE password = %s)) ON DUPLICATE KEY UPDATE srckey=srckey;" #remember from which source the entry is from, if this is the first time we see it.
    
    try:
        mariadb_connection.query(sql, (password, weight, srckey, password, weight))
        #mariadb_connection.commit()
        mariadb_connection.query(sql2, (srckey, password))

        dbactioncount+=2
        
    except Exception as err:
        print("[Saving] [Error] ")
        print(err)

    #print("Pending: ")
    #print(dbactioncount)
    commitIfNecessary()

#========================================================================

def sendHash(ihash):
    global dbactioncount, mariadb_connection
    insert_bdd_hash = "INSERT INTO hash (str, algo, clear) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE str=str;"

    print("[Saving] Hash: "+ihash["value"])
    mariadb_connection.query(insert_bdd_hash, (ihash["value"], json.dumps(ihash["possibleHashTypes"]), None))
    dbactioncount+=1
    commitIfNecessary()
    #message=json.dumps(ihash) #serializing the dict to json
    #send the message through rabbbitMQ using the hashes exchange
    #channel_uplink.basic_publish(exchange='hashes', routing_key='', body=message)

#========================================================================

hashID = hashid.HashID()
#========================================================================

########################################## END FUNCTONS #######################################

def main():
    global mariadb_connection, dbactioncount, channel
    #========================================================================
    #Connecting to mariadb
    """
    success=False
    while not success:
        try:
            mariadb_connection = mariadb.connect(host='db_dict', user=os.environ['MYSQL_USER'], password=os.environ['MYSQL_PASSWORD'], database='crack_it')
            success=True
        except mariadb._exceptions.OperationalError as e:
            success=False
            print("Failed to connect to database... Retrying in 5 seconds.")
            time.sleep(5)
    """
    mariadb_connection = DB(host='db_dict', port=3306, user=os.environ['MYSQL_USER'], password=os.environ['MYSQL_PASSWORD'], database='crack_it')
    #QUERY INIT
    #cursor = mariadb_connection.cursor()
    mariadb_connection.connect()

    #========================================================================
    #Connecting to RabbitMQ
    success=False
    while not success:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq'))
            channel = connection.channel()
            #channel_uplink = connection.channel()
            channel.basic_qos(prefetch_count=1)
            #channel_uplink.basic_qos(prefetch_count=1)
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


    #queue_name2 = 'cracker_hashes_queue'
    #result2 = channel.queue_declare(queue=queue_name2, exclusive=False, auto_delete=False)
    #bind the queue to the url exchange
    #channel.queue_bind(exchange='hashes', queue=queue_name2)

    #========================================================================

    #Global variable useb in multiple functions - DO NOT TOUCH
    #Count actions on db before commiting
    dbactioncount=0

    #========================================================================


    ######################################### START #########################################


    channel.basic_consume(queue_name, callback, auto_ack=False) #registering processing function

    channel.start_consuming() #start processing messages in the url queue



    #========================================================================
    #closing connection to rabbitMQ, important 
    #connection.close()

if __name__ == '__main__':
    main()
