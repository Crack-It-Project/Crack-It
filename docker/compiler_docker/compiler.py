#!/usr/bin/python3

from __future__ import generators
import sys
import os
import MySQLdb as mariadb

# Db connect
mariadb_connection = mariadb.connect(host='db_dict', user=os.environ['MYSQL_USER'], password=os.environ['MYSQL_PASSWORD'], database='crack_it')

# Create a cursor object to execute queries
cursor = mariadb_connection.cursor()

# Select all clear passwords in db
select_password_clear = "SELECT password FROM dict"

cursor.execute(select_password_clear)

# Create the new dictionnary in txt format
os.system("touch /dict/new_dict.txt")

# Select a list of 1000 passwords in db and put them in dict.txt until there's no passwords left  
def PasswordIterator(cursor, arraysize=1000):
	while True:
		passwords = cursor.fetchmany(arraysize)
		if not passwords:
			break
		for password in passwords:
			yield password

for password in PasswordIterator(cursor):
	os.system("echo "+ str(password) +" >> /dict/new_dict.txt")

# Fetchone method
#password_clear = cursor.fetchone()
#while password_clear is not None:
#	os.system("echo "+ password_clear + ">> dict.txt")
#	password_clear = cursor.fetchone()

cursor.close()

# Erase the older doctionnary file and replce it by the new one
os.system("cp /dict/new_dict.txt /dict/dict.txt")
os.system("rm /dict/new_dict.txt")
