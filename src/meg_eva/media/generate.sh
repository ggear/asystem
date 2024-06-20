#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

cp -rvf ${ROOT_DIR}/src/main/python/media/*.py ${ROOT_DIR}/src/main/resources/config
