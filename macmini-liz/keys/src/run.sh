#!/bin/sh

#TODO: Copy keys to /home/root/.ssh && /home/graham, chmod/chown them

cp -rvf ./config/id_rsa.pub /root/.ssh
cp -rvf ./config/.id_rsa /root/.ssh/id_rsa
rm -rfv ./config/.id_rsa
