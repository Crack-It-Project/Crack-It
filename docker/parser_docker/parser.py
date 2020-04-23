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

hashID = hashid.HashID()

mime = magic.Magic(mime=True)

#idSemicolumnThenItem = regex.compile('[^:^\n]*:([^\n]+)')
#idSemicolumnThenItem = regex.compile('\b(?!http|https|ftp|sftp|rtmp|ws)[^:^\n0-9]+:(?!\/\/)([^\n]+)') # make this regex way better here password starting with // won't work

#This regular expression is sued to check passwords list in this format TextOrUser:Password  Whitespaces between the semicolon : are ignored.
#We first compile it, which create an object we can sue to apply the regex, it is also faster than using the re. function directly
#I had to split the negative look-behinds (?<!https) into multiple because python does not seems to support them together (eg : (?<!https|http))
idSemicolumnThenItem = regex.compile('\b[^:^\n0-9]+(?<!http)(?<!https)(?<!ftp)(?<!sftp)(?<!rtmp)(?<!ws):([^\n]+)') #TODO: check this

#Get the repo name from the URL (by trimming)
def get_repo_name_from_url(url):
    last_slash_index = url.rfind("/")
    last_suffix_index = url.rfind(".git")
    if last_suffix_index < 0:
        last_suffix_index = len(url)

    if last_slash_index < 0 or last_suffix_index <= last_slash_index:
        raise Exception("Badly formatted url {}".format(url))

    return url[last_slash_index + 1:last_suffix_index]


#to check: https://github.com/iphelix/pack
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
#SETUP PHASE

#connecting to rabbitMQ
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='rabbitmq'))
channel = connection.channel()
#connecting to mariadb
mariadb_connection = mariadb.connect(host='db', user='python', password='pythonpython', database='crack_it')


#create the exchanges if they do not exist already
channel.exchange_declare(exchange='urls', exchange_type='fanout')  #to get url to parse
channel.exchange_declare(exchange='hashes', exchange_type='fanout') #to send all hashes to cracker instances

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
            print(item)
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
                    print(mode.hashcat)
                    hashSummary["possibleHashTypes"].append(mode.hashcat)
                    hashSummary["possibleHashTypesNames"].append(mode.name)
                    hashcatcount+=1

            #if there are no match, it must me plain text            
            if hashcatcount == 0:                   #TODO: find a better way because we're going to have a lot of false positive.'
                registerPassword(item, srckey)
            else:
                hashSummary["value"]=item
                sendHash(hashSummary)
    print("done")

#========================================================================

#QUERY INIT
cursor = mariadb_connection.cursor()

#announce we have a queue because we are a data consumer
result = channel.queue_declare(queue='', exclusive=True)
queue_name = result.method.queue

#bind the queue to the url exchange
channel.queue_bind(exchange='urls', queue=queue_name)

dbactioncount=0

#called fo each item in the queue
def callback(ch, method, properties, body):
    global dbactioncount, cursor, mariadb_connection
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
    

def commitIfNecessary():
    global dbactioncount, mariadb_connection       
    if dbactioncount >=4:
        print("COMMIT")
        mariadb_connection.commit() #send everything pending to the database   
        dbactioncount = 0

def registerPassword(password, srckey):
    global dbactioncount, cursor, mariadb_connection
    print("[Saving] Password: "+password)
    sql = "INSERT INTO dict (password) VALUES (%s) ON DUPLICATE KEY UPDATE seen=if((select count(*) from origin_dict WHERE srckey = %s) IS NOT NULL, (select seen from dict WHERE password = %s), (select seen+1 from dict WHERE password = %s));"  #insert the password, and if it already exist, increment the "seen" counter only it we didn't get it from the same source
    sql2 = "INSERT INTO origin_dict(srckey, item) VALUES (%s, (select id from dict WHERE password = %s)) ON DUPLICATE KEY UPDATE srckey=srckey;"
    
    try:
        cursor.execute(sql, (password, srckey, password, password))
        mariadb_connection.commit()
        cursor.execute(sql2, (srckey, password))

        dbactioncount+=2
        
    except Exception as err:
        print("[Saving] [Error] ")
        print(err)

    print("Pending: ")
    print(dbactioncount)
    commitIfNecessary()
    if password == "0000":
        exit()
   

def sendHash(ihash):
    print("[Saving] Hash: "+ihash["value"])
    message=json.dumps(ihash) #serializing the dict to json
    #send the message through rabbbitMQ using the hashes exchange
    channel.basic_publish(exchange='hashes', routing_key='', body=message)

channel.basic_consume(callback, queue_name, True) #registering processing function

channel.start_consuming() #start processing messages in the url queue

#closing connection to rabbitMQ, important 
connection.close()
