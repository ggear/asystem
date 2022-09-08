#!/bin/sh

mkdir -p /home/asystem
[ ! -L ${HOME}/home ] && ln -s /home/asystem ${HOME}/home || true

mkdir -p /var/lib/asystem/install
[ ! -L ${HOME}/install ] && ln -s /var/lib/asystem/install ${HOME}/install || true
