#!/bin/bash

echo " "
echo "######################## ETAPE 1 ##########################"
echo " "

#INSTALL DOCKER
#SEE https://docs.docker.com/engine/install/debian/
apt-get update -y
apt-get upgrade -y
echo " "
echo "######################## ETAPE 2 ##########################"
echo " "
apt-get install -y --no-install-recommends\
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg-agent \
    gnupg \
    software-properties-common

echo " "
echo "######################## ETAPE 3 ##########################"
echo " "
curl -fsSL https://download.docker.com/linux/debian/gpg | apt-key add -
apt-key fingerprint 0EBFCD88
add-apt-repository \
   "deb [arch=amd64] https://download.docker.com/linux/debian \
   $(lsb_release -cs) \
   stable"

echo " "
echo "######################## ETAPE 4 ##########################"
echo " "
apt-get update -y
apt-get install -y --no-install-recommends\
    docker-ce \
    docker-ce-cli \
    containerd.io

######################################################

echo " "
echo "######################## ETAPE 5 ##########################"
echo " "
#INSTALL DOCKER-COMPOSE
curl -L "https://github.com/docker/compose/releases/download/1.25.5/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

######################################################

echo " "
echo "######################## ETAPE 6 ##########################"
echo " "
#Install Git
apt install -y git

echo " "
echo "######################## FIN INSTALL ##########################"
echo " "

#Clone project repository
git clone --recurse-submodules https://gitlab.com/intech-sud/nimes/semestre_4/2020_03/pi_projetsinformatiques/crack_it.git /tmp/crack_it

#Create project dir
mkdir /crack_it
#Move needed files
mv -f /tmp/crack_it/docker/* /crack_it
#Delete evrything else
rm -rf /tmp/crack_it

#Run docker container every hour
(crontab -l 2> /dev/null ; echo "* * * * * /usr/bin/docker run -d crawler" ) | crontab

#Launch project
cd /crack_it/manager_compose/
docker-compose up --detach --build




#TODO
#Update project tree
#Update crontask command
#Clear/Shape stdout
#Easter egg