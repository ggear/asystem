#!/bin/bash

################################################################################
# Packages
################################################################################
apt-get update
apt-get install -y --allow-downgrades 'mbpfan=2.2.1-1'
apt-get install -y --allow-downgrades 'intel-microcode=3.20220510.1~deb11u1'
apt-get install -y --allow-downgrades 'libc6-i386=2.31-13+deb11u3'