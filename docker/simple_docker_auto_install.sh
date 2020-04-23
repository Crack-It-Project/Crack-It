#/bin/bash

#INSTALL DOCKER
apt-get remove docker docker-engine docker.io containerd runc


apt-get update -y
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg-agent \
    software-properties-common


curl -fsSL https://download.docker.com/linux/debian/gpg | sudo apt-key add -
add-apt-repository \
   "deb [arch=amd64] https://download.docker.com/linux/debian \
   $(lsb_release -cs) \
   stable"


apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io

######################################################

apt install -y git

git clone --recurse-submodules https://gitlab.com/intech-sud/nimes/semestre_4/2020_03/pi_projetsinformatiques/crack_it.git /tmp/

mkdir /crack_it
rm -rf /tmp/crack_it/

mv /tmp/crack_it/docker/* /crack_it

docker-compose up --detach --build /crack_it/manager_compose/.

echo "0 * * * * /usr/bin/docker run -d crawler >/dev/null 2>&1" >> /var/spool/cron/root