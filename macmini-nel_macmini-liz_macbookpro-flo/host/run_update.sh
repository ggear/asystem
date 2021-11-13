#!/bin/sh

################################################################################
# Update system
################################################################################
apt update
echo "" && echo "Run script upgrade package versions:"
apt list --upgradable 2>/dev/null | column -t | awk -F"/" '{print $1"\t"$2}' | awk '{print "apt-get install -y --allow-downgrades "$1"="$3""}' | grep -v Listing
echo ""
