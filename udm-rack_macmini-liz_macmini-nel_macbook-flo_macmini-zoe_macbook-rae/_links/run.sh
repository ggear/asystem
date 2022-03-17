#!/bin/sh

[ ! -L ${HOME}/home ] && ln -s /home/asystem ${HOME}/home || true
[ ! -L ${HOME}/install ] && ln -s /var/lib/asystem/install ${HOME}/install || true
