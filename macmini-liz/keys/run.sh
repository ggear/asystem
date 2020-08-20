#!/bin/sh

cp -rvf ./config/id_rsa.pub /root/.ssh
cp -rvf ./config/.id_rsa /root/.ssh/id_rsa
rm -rfv ./config/.id_rsa
