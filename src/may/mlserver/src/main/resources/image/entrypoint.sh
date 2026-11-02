#!/bin/bash

set -o nounset
set -o errexit

mlserver --version
trap 'exit 0' TERM INT
while true; do sleep 10 & wait $!; done
