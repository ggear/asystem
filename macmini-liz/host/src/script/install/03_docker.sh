#!/bin/sh

apt-get install -y \
  apt-transport-https=1.8.2.1 \
  ca-certificates=20200601~deb10u1 \
  gnupg-agent=2.2.12-1+deb10u1 \
  software-properties-common=0.96.20.2-2
curl -sfsSL https://download.docker.com/linux/debian/gpg | APT_KEY_DONT_WARN_ON_DANGEROUS_USAGE=1 apt-key add -
add-apt-repository \
  "deb [arch=amd64] https://download.docker.com/linux/debian \
   $(lsb_release -cs) \
   stable"
apt-get install -y \
  docker-ce=5:19.03.12~3-0~debian-buster \
  docker-ce-cli=5:19.03.12~3-0~debian-buster \
  containerd.io=1.2.13-2
curl -sL "https://github.com/docker/compose/releases/download/1.26.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
