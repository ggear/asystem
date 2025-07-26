#!/bin/bash

mkdir -p /home/asystem
ln -s /home/asystem ${HOME}/home || true

mkdir -p /var/lib/asystem/install
ln -s /var/lib/asystem/install ${HOME}/install || true
