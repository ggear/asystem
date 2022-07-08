#!/bin/sh

ROOT_DIR="$(
  cd -- "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

decode-config.py -s 10.0.6.99 --backup-type dmp --backup-file ${ROOT_DIR}/src/build/resources/Config_@d_@v
