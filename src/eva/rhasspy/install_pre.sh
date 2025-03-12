#!/bin/bash

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/latest
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/latest

rm -rf ${SERVICE_HOME}/train/*
rm -rf ${SERVICE_HOME}/custom/*
rm -rf ${SERVICE_HOME}/models/*
