#!/bin/bash

SERVICE_HOME=/home/asystem/appdaemon/latest
SERVICE_INSTALL=/var/lib/asystem/install/appdaemon/latest

rm -rf ${SERVICE_HOME}/apps && cp -rf ${SERVICE_INSTALL}/apps ${SERVICE_HOME}
rm -rf ${SERVICE_HOME}/dashboards && cp -rf ${SERVICE_INSTALL}/dashboards ${SERVICE_HOME}
