#!/bin/bash

echo " "
echo "####################### UPDATE SYSTEM #######################"
echo " "

apt-get update -y
apt-get upgrade -y


######################################################


echo " "
echo "###################### INSTALL DOCKER #######################"
echo " "

#SEE https://docs.docker.com/engine/install/debian/

apt-get install -y --no-install-recommends\
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg-agent \
    gnupg \
    software-properties-common

curl -fsSL https://download.docker.com/linux/debian/gpg | apt-key add -
apt-key fingerprint 0EBFCD88
add-apt-repository \
   "deb [arch=amd64] https://download.docker.com/linux/debian \
   $(lsb_release -cs) \
   stable"

apt-get update -y
apt-get install -y --no-install-recommends\
    docker-ce \
    docker-ce-cli \
    containerd.io


######################################################


echo " "
echo "###################### DOCKER-COMPOSE #######################"
echo " "

#SEE https://docs.docker.com/compose/install/ 

curl -L "https://github.com/docker/compose/releases/download/1.25.5/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose


######################################################


echo " "
echo "########################### GIT #############################"
echo " "

apt install -y git


######################################################


echo " "
echo "######################## CLONE REPO #########################"
echo " "

git clone --recurse-submodules https://gitlab.com/intech-sud/nimes/semestre_4/2020_03/pi_projetsinformatiques/crack_it.git /tmp/crack_it


######################################################


echo " "
echo "########################## CONFIG ###########################"
echo " "

#Create project dir
mkdir /crack_it
#Move needed files
mv -f /tmp/crack_it/docker/* /crack_it
#Delete everything else
rm -rf /tmp/crack_it

#Run docker container every hour
#       Use "docker start" to execute an already ran container
(crontab -l 2> /dev/null ; echo "0 0-23 * * * /usr/bin/docker start crack_it_crawler_1" ) | crontab
(crontab -l 2> /dev/null ; echo "0 0 * * * /usr/bin/docker start crack_it_compiler_1" ) | crontab
(crontab -l 2> /dev/null ; echo "0 0 * * * /usr/bin/docker start crack_it_hashfetcher_1" ) | crontab

#Launch project
cd /crack_it/
docker-compose up --detach --build




#TODO
#Clear/Shape stdout
