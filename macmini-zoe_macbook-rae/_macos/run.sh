#!/bin/sh

################################################################################
# Normalise
################################################################################
mkdir -p ~/Temp ~/Code ~/Backup
rm -rf .zprofile .zsh_history .zsh_sessions
cat <<EOF >/Users/graham/.bash_profile
# .bash_profile

export CLICOLOR=1
export LSCOLORS=ExFxCxDxBxegedabagacad

bind '"\e[A":history-search-backward'
bind '"\e[B":history-search-forward'

alias edit="/Applications/Sublime\ Text.app/Contents/SharedSupport/bin/subl"
alias grep="grep --line-buffered"
alias fab="fab -e"

alias ssh-copy-id='sshcopyid_func'
function sshcopyid_func() { cat ~/.ssh/id_rsa.pub | ssh $1 'mkdir .ssh ; cat >>.ssh/authorized_keys' ;}

export PATH=/Users/graham/.conda/envs/python2/bin:/Library/Conda/anaconda2/bin:/opt/homebrew/bin:/usr/local/sbin:/usr/local/bin:${PATH}

EOF
. /Users/graham/.bash_profile
sed -i '' 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
mkdir -p /Users/graham/Backup /Users/graham/Code /Users/graham/Temp
chown graham /Users/graham/Backup /Users/graham/Code /Users/graham/Temp
chgrp staff /Users/graham/Backup /Users/graham/Code /Users/graham/Temp

################################################################################
# Brew
################################################################################
! which brew && /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew update
brew upgrade
brew install \
	htop \
	wget \
	watch

################################################################################
# Python
################################################################################
if [ ! -d /Library/Conda/anaconda2/bin/conda ]; then
	cd ~/Temp
	rm -rf /Library/Conda && mkdir -p /Library/Conda && chmod 777 /Library/Conda
	wget https://repo.anaconda.com/miniconda/Miniconda3-4.5.12-MacOSX-x86_64.sh
	chmod +x Miniconda3-4.5.12-MacOSX-x86_64.sh
	./Miniconda3-4.5.12-MacOSX-x86_64.sh -p /Library/Conda/anaconda2 -b
	rm Miniconda3-4.5.12-MacOSX-x86_64.sh
	conda config --set channel_priority false
	conda config --append envs_dirs $HOME/.conda/envs
	conda create -y -n python2 python=2.7.18
	conda create -y -n python3 python=3.10
fi

################################################################################
# Asystem
################################################################################
if [ ! -d ~/Code/asystem ]; then
	brew install pkg-config poppler
	pip install fabric
	cd ~/Code
	git clone https://github.com/ggear/asystem.git
	cd asystem
	fab purge setup
fi



