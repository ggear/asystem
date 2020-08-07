#!/bin/sh

apt-get install -y \
  htop=2.2.0-1+b1 \
  lm-sensors=1:3.5.0-3
sensors-detect --auto
