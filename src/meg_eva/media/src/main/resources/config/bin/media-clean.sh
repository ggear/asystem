#!/bin/bash

ROOT_DIR=$(dirname $(readlink -f "$0"))

. ${ROOT_DIR}/.env

find /share -name "*_metadata.yaml" -delete
${PYTHON_DIR}/python ${ROOT_DIR}/lib/analyse.py /share "14W6B2404_e1JKftOvHE4moV5w6VP5aitHVpX3Qcgcl8" --clean