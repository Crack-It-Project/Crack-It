#/bin/bash

#INSTALL DOCKER
#SEE https://docs.docker.com/engine/install/debian/
apt-get update -y
apt-get install -y --no-install-recommends\
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg-agent \
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

#INSTALL DOCKER-COMPOSE
curl -L "https://github.com/docker/compose/releases/download/1.25.5/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

######################################################

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
#Delete the rest
rm -rf /tmp/crack_it

#Launch project
cd /crack_it/manager_compose/
docker-compose up --detach --build



#TODO

#Add cron task for crawler 
#Run docker container every hour
#   echo "@hourly /usr/bin/docker run -d crawler >/dev/null 2>&1" > /etc/cron.hourly/hourly_crawler_start
#   hmod +x /etc/cron.hourly/hourly_crawler_start