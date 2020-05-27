#!/usr/bin/python3
import requests
import MySQLdb as mariadb
import pika
import sys
import os
import json
import time
from git import Repo
import tempfile
import uuid
import magic


tmpDirectory="/sharedTmp"
cacheDirectory="/cache"

mime = magic.Magic(mime=True)


def get_random_unique_filename(dest, ext=".txt"):
    nameavail=False
    if not os.path.isdir(dest):
        return None
    while not nameavail:
        filename=uuid.uuid4().hex+ext
        if not os.path.exists(os.path.join(dest,filename)):
            return filename


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

def parser_pastebin(url, cache, dest):
    filename=get_random_unique_filename(dest)
    with open(os.path.join(dest,filename), 'w') as tmp:
        #fetch url and write content in temporary file
        tmp.write(requests.get(url).text)
        print("Compiled one pastebin file")
    return [filename]

def parser_github(url, cache, dest):
    
    returns=[]
    newsourcehint=json.loads(sourcehint) or []
    #get repo name
    reponame=get_repo_name_from_url(url)
    repopath=os.path.join(os.getcwd(), os.path.join(cache,reponame))
    #clone the repo
    if os.path.isdir(repopath):
        repo = Repo(repopath)
        pullinfo = repo.remotes.origin.pull()
        for item in repo.index.diff(pullinfo[0].old_commit): #TODO: check this
            newpath=os.path.join(dest,get_random_unique_filename(dest, "."+os.path.basename(a_path)))
            shutil.copyfile(a_path, newpath)
            returns.append(newpath)

    else:
        repo = Repo.clone_from(url, repopath)
        for root, subdirs, files in os.walk(repo.working_tree_dir):
            for file in files:
                filepath=os.path.join(root, file)
                if mime.from_file(filepath) == "text/plain": #only allow plain text files
                    #with open(filepath, "rb") as readfile:
                        #append their content to the temporary file
                        #shutil.copyfileobj(readfile, tmp)
                    newpath=os.path.join(dest,get_random_unique_filename(dest, "."+file))
                    shutil.copyfile(filepath, newpath)
                    returns.append(newpath)
        
    #send the temporary file file descriptor

    return returns

#add your crawler in this dict to register it, the key is the one the DB should use
pre_parsers = {
  "pastebin": parser_pastebin,
  "git": parser_github,
  "github": parser_github
}


#========================================================================
#MODULE DELCARATION AND CONFIGURATION SECTION

def crawler_pastebin(url, sourcehint):
    #fetch url and parse json
    scraping = requests.get(url).json()
    returns = []
    if sourcehint is None:
        sourcehint="-1" 
    newsourcehint="-1"
    #get the scrape_url for each item returned by the API
    for item in scraping:
        date=item.get('date')
        if int(date) > int(sourcehint):
            if int(date) > int(newsourcehint):
                newsourcehint=date
            returns.append(item.get('scrape_url'))
        else:
            print("skipping already seen paste")
    return returns, newsourcehint

def crawler_github(url, sourcehint):
    returns = []
    data_json = requests.get(url).json()
    for item in data_json["items"]:
        returns.append(item["html_url"])
    sourcehint=None
    return returns, sourcehint

def crawler_git(url, sourcehint):
    returns = [url]
    sourcehint = None
    return returns, sourcehint

#add your crawler in this dict to register it, the key is the one the DB should use
crawlers = {
  "pastebin": crawler_pastebin,
  "github": crawler_github,
  "git": crawler_git
}

#========================================================================
#SETUP PHASE


#connecting to rabbitMQ

def main():
    success=False
    while not success:
        try:
            #connecting to mariadb
            mariadb_connection = mariadb.connect(host='db_dict', user=os.environ['MYSQL_USER'], password=os.environ['MYSQL_PASSWORD'], database='crack_it')
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
    channel.exchange_declare(exchange='files', exchange_type='fanout')

    result = channel.queue_declare(queue='parser_files_queue', exclusive=False, auto_delete=False)
    queue_name = result.method.queue

    #bind the queue to the url exchange
    channel.queue_bind(exchange='files', queue=queue_name)


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
        result, newsourcehint =crawlers[row[2]](row[1], row[4])
        cursor.execute("UPDATE source SET sourceHint = %s WHERE idsource = %s;", (newsourcehint, row[0]))
        mariadb_connection.commit() # w ecoult batch commit, but is it really worth it here ?
        for itemToParse in result:
            #assemble a json message to easely combine the two values, m=> module to use, v => url
            datafiles=pre_parsers[row[2]](itemToParse, cacheDirectory, tmpDirectory)
            for datafile in datafiles:

                
                #filedest=



                message=json.dumps({"m": row[2], "s": itemToParse, "v": datafile})
                #send the message through rabbbitMQ using the urls exchange
                channel.basic_publish(exchange='files', routing_key='', body=message)
        


    #closing connection to rabbitMQ
    connection.close()

if __name__ == '__main__':
    main()