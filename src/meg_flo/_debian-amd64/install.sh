#!/bin/bash

################################################################################
# Packages
################################################################################
apt-get update
apt-get install -y --allow-downgrades 'intel-microcode=3.20230512.1'
apt-get install -y --allow-downgrades 'libc6-i386=2.36-9'
