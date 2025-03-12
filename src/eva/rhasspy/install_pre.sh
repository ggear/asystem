#!/bin/bash

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/latest
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/latest

rm -rf ${SERVICE_HOME}/models/*
rm -rf ${SERVICE_HOME}/train/*
