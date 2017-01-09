#!/bin/bash

# STEP0: Get the config
USER_NAME=$1
USER_ID=$2
SSH_PORT=$3
COMPOSE_VERSION=$4
echo ${USER_NAME} ${USER_ID} ${SSH_PORT} ${COMPOSE_VERSION}

# STEP1: Make sure everything is updated and installed
apt-get -qy update && apt-get -yq upgrade && apt-get install -y htop tree vim git jq mosh tmux curl rsync python3-venv

# STEP2: Add non-sudo user
adduser --disabled-password --uid ${USER_ID} --gecos "" ${USER_NAME}
adduser ${USER_NAME} sudo
echo "${USER_NAME} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/90-cloud-init-users

# STEP3: SSH access and security
cd /home/${USER_NAME}/
mkdir .ssh && chmod 700 .ssh
cp /root/.ssh/authorized_keys .ssh/
ssh-keygen -q -t rsa -b 2048 -N '' -f .ssh/id_rsa
sed -i  s/root/${USER_NAME}/g .ssh/id_rsa.pub
chown -R ${USER_NAME}:${USER_NAME} .ssh/

sed -i 's/#\?Port .\+/Port 8622/g' /etc/ssh/sshd_config
sed -i 's/^#\?PermitRootLogin yes/PermitRootLogin no/g' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication yes/PasswordAuthentication no/g' /etc/ssh/sshd_config
sed -i 's/^#\?AuthorizedKeysFile/AuthorizedKeysFile/g'  /etc/ssh/sshd_config
sed -i 's/^#\?X11Forwarding yes/X11Forwarding no/g'  /etc/ssh/sshd_config
service ssh restart

# STEP4: Install docker compose and configure docker
curl -L https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m) -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
adduser ${USER_NAME} docker
service docker restart

# STEP5: Cleanup
passwd -l root
rm -rf /root/setup.sh
history -c && history -w
