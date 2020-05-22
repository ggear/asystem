# Maybe have a -1, -2 etc suffix, check host to see if they have been run?
# Profile them out, host, worker, docker etc

###############################################################################
# Installer pre-conditions:
#   - create partitions for /, /tmp, /var, /home
#   - create user graham
#   - install ssh, standard utils
###############################################################################

###############################################################################
# Update system, install utilities
###############################################################################
apt-get update
apt-get install -y \
  vim=2:8.1.0875-5 \
  curl=7.64.0-4+deb10u1

###############################################################################
# Keys and certificates
###############################################################################
if [ $(grep graham /home/graham/.ssh/authorized_keys | wc -l) -eq 0 ]; then
  mkdir -p /home/graham/.ssh
  chmod 755 /home/graham/.ssh
  touch /home/graham/.ssh/authorized_keys
  chmod 644 /home/graham/.ssh/authorized_keys
  chown -R graham /home/graham
  cat <<EOF >/home/graham/.ssh/authorized_keys
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC17bbhX9GtT/YyDrYO98Q9xzfyhn3WtBbftpFJ1yTm0wkssNMrW6YNjW2dVDm2qPgJUg9pKqw+XdyDUcxKWal1mLecPDYNAJgU0mJkFehDAxW91YNzjCH+kY70mVgZCzhi6XAx8pX5TDDHRMNnp76OyblMlge8g21tf3AwrzvJIQuC7UTrJYRWsxAIxTQBKqPW96JfvPLXk9l+vs31xC1y+wbWlKRey8LpYi4v/dePkkpQaac4R2DR4AlJNPRsoSn+W1zYYMi34bw4smpglrH83fA42rWClPkth/X2RzXPrQMyBNPFLalMbDe+xXMq6ExdfTlU6gE4s8dW4Gi3b1J1 graham.gear@gmail.com
EOF
fi

###############################################################################
# Install Docker
###############################################################################
apt-get install -y \
    apt-transport-https=1.8.2 \
    ca-certificates=20190110 \
    curl=7.64.0-4+deb10u1 \
    gnupg-agent=2.2.12-1+deb10u1 \
    software-properties-common=0.96.20.2-2
curl -fsSL https://download.docker.com/linux/debian/gpg | apt-key add -
add-apt-repository \
   "deb [arch=amd64] https://download.docker.com/linux/debian \
   $(lsb_release -cs) \
   stable"
apt-get install -y \
  docker-ce=5:19.03.8~3-0~debian-buster \
  docker-ce-cli=5:19.03.8~3-0~debian-buster \
  containerd.io=1.2.13-1
curl -L "https://github.com/docker/compose/releases/download/1.25.5/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

###############################################################################
# Install K8s
###############################################################################
#curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=v1.17.4+k3s1 bash -
#curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=v1.17.4+k3s1 K3S_URL=https://192.168.2.6:6443 K3S_TOKEN=$(cat /var/lib/rancher/k3s/server/node-token) bash -
#export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
#kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml
#kubectl get storageclass
#
#curl -sfL https://git.io/get_helm.sh | bash -s -- --version v2.16.5
#kubectl -n kube-system create serviceaccount tiller
#kubectl create clusterrolebinding tiller --clusterrole cluster-admin --serviceaccount=kube-system:tiller
#helm init --service-account tiller
#
#apt-get install -y golang-cfssl=1.2.0+git20160825.89.7fb22c8-3+b13
#
## https://carpie.net/articles/installing-docker-registry-on-k3s
## https://itnext.io/setup-a-private-registry-on-k3s-f30404f8e4d3
#cat <<EOF >/etc/rancher/k3s/registries.yaml
#mirrors:
#  "192.168.2.6:30500":
#    endpoint:
#      - "http://192.168.2.6:30500"
#EOF
#systemctl restart k3s
