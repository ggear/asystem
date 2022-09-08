#!/bin/bash

################################################################################
# Samba
################################################################################
service smbd stop
systemctl disable smbd
service nmbd stop
systemctl disable nmbd
