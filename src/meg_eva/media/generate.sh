#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

cp -rvf ${ROOT_DIR}/src/main/python/media/rename.py ${ROOT_DIR}/src/main/resources/config
