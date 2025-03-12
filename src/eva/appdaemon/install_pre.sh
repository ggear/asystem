#!/bin/bash

SERVICE_HOME=/home/asystem/${SERVICE_NAME}/latest
SERVICE_INSTALL=/var/lib/asystem/install/${SERVICE_NAME}/latest

rm -rf ${SERVICE_HOME}/apps && cp -rf ${SERVICE_INSTALL}/data/apps ${SERVICE_HOME}
rm -rf ${SERVICE_HOME}/dashboards && cp -rf ${SERVICE_INSTALL}/data/dashboards ${SERVICE_HOME}
