#!/bin/bash

# STEP0: Get the config
USER_NAME=$1
USER_ID=$2
SSH_PORT=$3
COMPOSE_VERSION=$4
echo ${USER_NAME} ${USER_ID} ${SSH_PORT} ${COMPOSE_VERSION}

# STEP1: Make sure everything is updated and installed
# apt-get -qy update && apt-get -yq upgrade && apt-get install -y htop tree vim git jq mosh tmux curl rsync python3-venv

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

# STEP4: Install xfce and vnc
sudo apt install xfce4 xfce4-goodies
sudo apt install tightvncserver
# Follow guide here:

# https://www.digitalocean.com/community/tutorials/how-to-install-and-configure-vnc-on-ubuntu-18-04

# Enter password
vncserver
vncserver -kill :1

mv ~/.vnc/xstartup ~/.vnc/xstartup.bak
cat <<EOT >> ~/.vnc/xstartup
#!/bin/bash
xrdb $HOME/.Xresources
startxfce4 &
EOT

sudo chmod +x ~/.vnc/xstartup

sudo -i
cat <<EOT >> /etc/systemd/system/vncserver@.service
[Unit]
Description=Start TightVNC server at startup
After=syslog.target network.target

[Service]
Type=forking
User=canary
Group=canary
WorkingDirectory=/home/canary

PIDFile=/home/canary/.vnc/%H:%i.pid
ExecStartPre=-/usr/bin/vncserver -kill :%i > /dev/null 2>&1
ExecStart=/usr/bin/vncserver -depth 24 -geometry 1280x800 :%i
ExecStop=/usr/bin/vncserver -kill :%i

[Install]
WantedBy=multi-user.target
EOT
#exit
sudo systemctl daemon-reload
sudo systemctl enable vncserver@1.service
sudo systemctl start vncserver@1
#sudo systemctl status vncserver@1

# STEP5: install bitrader
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
# install dependencies
sudo apt --fix-broken install
mv google-chrome-stable_current_amd64.deb Downloads/

mkdir Projects && cd Projects/
git clone https://github.com/jr-minnaar/bitrader-private
cd bitrader-private
git fetch --all
git checkout bleeding-alpha-hugo

sudo apt-get install -y python3-pip python3-dev
sudo apt-get install -y libxml2-dev libxslt1-dev

python3 -m venv venv
source venv/bin/activate
pip install -U pip wheel
pip install -e .


# STEP6: Install dropbox
# See steps here: https://www.dropbox.com/install-linux
cd ~ && wget -O - "https://www.dropbox.com/download?plat=lnx.x86_64" | tar xzf -
./.dropbox-dist/dropboxd
wget -O - https://www.dropbox.com/download?dl=packages/dropbox.py > dropbox.py
chmod +x dropbox.py
sudo mv dropbox.py /usr/local/bin/
sudo apt install python
dropbox.py status
dropbox.py start

# STEP 7: Install web drivers

DRIVER_VERSION=$(curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE)
wget -N http://chromedriver.storage.googleapis.com/${DRIVER_VERSION}/chromedriver_linux64.zip -P ~/
unzip ~/chromedriver_linux64.zip -d ~/
sudo mv chromedriver /usr/local/bin/
mv chromedriver_linux64.zip Downloads/

wget https://github.com/mozilla/geckodriver/releases/download/v0.22.0/geckodriver-v0.22.0-linux64.tar.gz -O /tmp/geckodriver.tar.gz && tar -C /opt -xzf /tmp/geckodriver.tar.gz && chmod 755 /opt/geckodriver && ln -fs /opt/geckodriver /usr/local/bin/geckodriver

#git config credential.helper store
#git pull

# Add secrets
#vi .env

# STEP5: Cleanup
passwd -l root
rm -rf /root/setup_gui.sh
history -c && history -w
