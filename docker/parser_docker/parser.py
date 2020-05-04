#!/usr/bin/python3
import requests
import MySQLdb as mariadb
import pika
import sys
import json
import tempfile
import re as regex
import hashid
from git import Repo
import os
#import shutil
import magic
import time
from zxcvbn import zxcvbn


########################################## FUNCTONS ##########################################

#Get the repo name from the URL (by trimming)
def get_repo_name_from_url(url):
    last_slash_index = url.rfind("/")
    last_suffix_index = url.rfind(".git")
    if last_suffix_index < 0:
        last_suffix_index = len(url)

    if last_slash_index < 0 or last_suffix_index <= last_slash_index:
        raise Exception("Badly formatted url {}".format(url))

    return url[last_slash_index + 1:last_suffix_index]

#========================================================================

#MODULE DELCARATION AND CONFIGURATION SECTION

def parser_pastebin(url):
    
    tmp=tempfile.TemporaryFile(mode='r+')
    #fetch url and write content in temporary file
    tmp.write(requests.get(url).text)
    print("Compiled one pastebin file")
    return [tmp]

def parser_github(url):
    
    returns=[]
    #get repo name
    reponame=get_repo_name_from_url(url)
    repopath=os.path.join(os.getcwd(), 'repos/'+reponame)
    #clone the repo
    if os.path.isdir(repopath):
        repo = Repo(repopath)
        pullinfo = repo.remotes.origin.pull()
    #    pullchanges=repo.index.diff(pullinfo[0].old_commit) #TODO: check this

    else:
        repo = Repo.clone_from(url, repopath)
    #find all files in the repo
    for root, subdirs, files in os.walk(repo.working_tree_dir):
        for file in files:
            filepath=os.path.join(root, file)
            if mime.from_file(filepath) == "text/plain": #only allow plain text files
                #with open(filepath, "rb") as readfile:
                    #append their content to the temporary file
                    #shutil.copyfileobj(readfile, tmp)
                returns.append(filepath)
        
    #send the temporary file file descriptor

    return returns

#add your crawler in this dict to register it, the key is the one the DB should use
parsers = {
  "pastebin": parser_pastebin,
  "git": parser_github,
  "github": parser_github
}

#========================================================================

#parse a given file and then extract all passwords and hashes found. Return a mutli-level dict
def analyzeFile(fileDscrpt, srckey):
    print("Processing one file")
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

    method="" #depending on the previous result, we choose a full passwordlist parsing emthod or a user:password parsing regex
    if os.fstat(fileDscrpt.fileno()).st_size > 20000000 and linesizeavg < 32:
        method="fulllist"
    else:
        method="semicolonlist"
    lines=0 #we now use this to check for how many lines are not matched by the regex
    print("Method: ["+method+"]")
    for line in fileDscrpt:  #we parse line by line
        
        if method == "semicolonlist":
            d = idSemicolumnThenItem.match(line) #apply the regex
            if lines < 1000: #we don't really care about counting lines if we are over 1000, this is only used to detect if this is a list or not, and only on first lines
                lines += 1
            if lines > matches + 20:   #number of missed matches to consider the file invalid
                print("Too many lines are not matching, stopping !")
                return []
                break;

        if method == "fulllist" or d: #if the regex match or we are in fulllist mode (= each line is a "string of interest")
            matches += 1 
            if method == "semicolonlist":
                item=d.group(1).lstrip() #strip leading spaces if there were some after the semicolon
            else:
                item=line # the whole line is kept in fulllist mode
            item=item.rstrip('\r\n') #remove trailing newlines (works for any combinaisons, so it works for DOS, OSX and Unix line endings)
            #print(item)
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
                    print(mode.name)
                    #print(mode.hashcat)
                    hashSummary["possibleHashTypes"].append(mode.hashcat)
                    hashSummary["possibleHashTypesNames"].append(mode.name)
                    hashcatcount+=1

            #if there are no match, it must me plain text            
            isPassword=False
            if hashcatcount > 0:                   #TODO: find a better way because we're going to have a lot of false positive.'
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
                registerPassword(item, srckey)
                
    print("done")

#========================================================================

#called fo each item in the queue
def callback(ch, method, properties, body):
    global dbactioncount, cursor, mariadb_connection, channel
    params=json.loads(body) #parse the json packet
    print("processing:")
    print(params["v"])
    datafiles=parsers[params["m"]](params["v"])  #we select and execute the appropriate parser by name from the parser list. (the parser name is also in the packet)
    # we get a file descriptor we can pass to analyseFile, we get a dict which contains everything extracted from it
    for datafile in datafiles:
        srckey=params["v"]
        if isinstance(datafile, str):
            file=open(datafile, "r", encoding="utf-8", errors="ignore")
            srckey+=":"+os.path.basename(datafile)
        else:
            file=datafile
        analyzeFile(file, srckey)
        file.close() #we close the file, VERY IMPORTANT

    print("LAST COMMIT")
    mariadb_connection.commit()
    print("ACK-ING the message")
    ch.basic_ack(method.delivery_tag)
    """
    if "passwords" in data:
        for password in data["passwords"]: #if we have passwords, then for each one do            
            #DB insert
            
            print("[Saving] Password: "+password)
            sql = "INSERT INTO dict (password, seen) VALUES (%s, 0) ON DUPLICATE KEY UPDATE seen=seen+1"  #insert the password, and if it already exist, increment the "seen" counter
            val = [password]
            try:
                cursor.execute(sql, val)
            except mariadb.DataError:
                print("[Saving] [Error]")
    if "hashes" in data:    
        for ihash in data["hashes"]: #if we have hashes, then for each one do        
            print("[Saving] Hash: "+ihash)
            message=json.dumps(ihash) #serializing the dict to json
            #send the message through rabbbitMQ using the hashes exchange
            channel.basic_publish(exchange='hashes', routing_key='', body=message)"""
    
#========================================================================

def commitIfNecessary():
    global dbactioncount, mariadb_connection       
    if dbactioncount >=1000:
        print("COMMIT")
        mariadb_connection.commit() #send everything pending to the database   
        dbactioncount = 0

#========================================================================

def registerPassword(password, srckey):
    global dbactioncount, cursor, mariadb_connection
    #print("[Saving] Password: "+password)
    #sql = "INSERT INTO dict (password) VALUES (%s) ON DUPLICATE KEY UPDATE seen = if(CAST((select count(*) from origin_dict WHERE origin_dict.srckey = %s) AS UNSIGNED) > 0, dict.seen, dict.seen+1);"  
    sql="INSERT INTO dict (password) VALUES (%s) ON DUPLICATE KEY UPDATE seen = if((SELECT count(*) FROM (select * from origin_dict INNER JOIN dict ON dict.id = origin_dict.item WHERE origin_dict.srckey = %s AND dict.password = %s) s) > 0, dict.seen, dict.seen+1);" #insert the password, and if it already exist, increment the "seen" counter only it we didn't get it from the same source
    sql2 = "INSERT INTO origin_dict(srckey, item) VALUES (%s, (select id from dict WHERE password = %s)) ON DUPLICATE KEY UPDATE srckey=srckey;" #remember from which source the entry is from, if this is the first time we see it.
    
    try:
        cursor.execute(sql, (password, srckey, password))
        #mariadb_connection.commit()
        cursor.execute(sql2, (srckey, password))

        dbactioncount+=2
        
    except Exception as err:
        print("[Saving] [Error] ")
        print(err)

    #print("Pending: ")
    #print(dbactioncount)
    commitIfNecessary()

#========================================================================

def sendHash(ihash):
    global channel_uplink
    print("[Saving] Hash: "+ihash["value"])
    message=json.dumps(ihash) #serializing the dict to json
    #send the message through rabbbitMQ using the hashes exchange
    channel_uplink.basic_publish(exchange='hashes', routing_key='', body=message)

#========================================================================

hashID = hashid.HashID()

#========================================================================

mime = magic.Magic(mime=True)

#========================================================================
#Setting up regular expressions

#idSemicolumnThenItem = regex.compile('[^:^\n]*:([^\n]+)')
#idSemicolumnThenItem = regex.compile('\b(?!http|https|ftp|sftp|rtmp|ws)[^:^\n0-9]+:(?!\/\/)([^\n]+)') # make this regex way better here password starting with // won't work

#This regular expression is sued to check passwords list in this format TextOrUser:Password  Whitespaces between the semicolon : are ignored.
#We first compile it, which create an object we can sue to apply the regex, it is also faster than using the re. function directly
#I had to split the negative look-behinds (?<!https) into multiple because python does not seems to support them together (eg : (?<!https|http))
idSemicolumnThenItem = regex.compile('\b[^:^\n0-9]+(?<!http)(?<!https)(?<!ftp)(?<!sftp)(?<!rtmp)(?<!ws):([^\n]+)') #TODO: check this


########################################## END FUNCTONS #######################################


#========================================================================
#Connecting to mariadb
success=False
while not success:
    try:
        mariadb_connection = mariadb.connect(host='db', user='python', password='pythonpython', database='crack_it')
        success=True
    except mariadb._exceptions.OperationalError as e:
        success=False
        print("Failed to connect to database... Retrying in 5 seconds.")
        time.sleep(5)

#QUERY INIT
cursor = mariadb_connection.cursor()


#========================================================================
#Connecting to RAbbiMQ
success=False
while not success:
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host='rabbitmq'))
        channel = connection.channel()
        channel_uplink = connection.channel()
        channel.basic_qos(prefetch_count=1)
        channel_uplink.basic_qos(prefetch_count=1)
        success=True
    except (pika.exceptions.AMQPConnectionError) as e:
        success=False
        print("Failed to connect to rabbitMQ ... Retrying in 5 seconds.")
        time.sleep(5)


#========================================================================
#Setting up queues

#Create the exchanges if they do not exist already
channel.exchange_declare(exchange='urls', exchange_type='fanout')  #to get url to parse
channel.exchange_declare(exchange='hashes', exchange_type='fanout') #to send all hashes to cracker instances

#announce we have a queue because we are a data consumer
queue_name = 'parser_urls_queue'
result = channel.queue_declare(queue=queue_name, exclusive=False, auto_delete=False)
#bind the queue to the url exchange
channel.queue_bind(exchange='urls', queue=queue_name)


queue_name2 = 'cracker_hashes_queue'
result2 = channel.queue_declare(queue=queue_name2, exclusive=False, auto_delete=False)
#bind the queue to the url exchange
channel.queue_bind(exchange='hashes', queue=queue_name2)

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
connection.close()