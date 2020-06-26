#!/usr/bin/python3

from __future__ import generators
import sys
import os
from mysqldb import DB
import time
from pathlib import Path
from shutil import copyfile

# Db connect
db = DB(host='db_dict', port=3306, user=os.environ['MYSQL_USER'], password=os.environ['MYSQL_PASSWORD'], database='crack_it')
db.connect()

# Select all clear passwords in db
select_password_clear = "SELECT password FROM dict ORDER BY seen DESC"

cursor=db.query(select_password_clear)

# Create the new dictionnary in txt format
Path('/dict/new_dict.txt').touch()

# Select a list of 1000 passwords in db and put them in dict.txt until there's no passwords left  
def PasswordIterator(cursor, arraysize=1000):
	while True:
		passwords = cursor.fetchmany(arraysize)
		if not passwords:
			break
		for password in passwords:
			yield password

with open("/dict/new_dict.txt", "a") as myfile:
	for password in PasswordIterator(cursor):
		myfile.write(str(password[0])+"\n")

cursor.close()

# Erase the older doctionnary file and replce it by the new one
copyfile('/dict/new_dict.txt', '/dict/dict.txt')
os.remove("/dict/new_dict.txt")

os.system("create-cracklib-dict -o /dict/cracklib /dict/dict.txt")
