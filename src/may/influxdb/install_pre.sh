#!/bin/bash

# shellcheck disable=SC2153
SERVICE_HOME=/home/asystem/${SERVICE_NAME}/latest

chmod 600 "${SERVICE_HOME}/cluster_1/admin.json" "${SERVICE_HOME}/cluster_1/init.json"
