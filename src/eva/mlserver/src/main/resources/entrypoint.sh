#!/bin/sh

set -o nounset
set -o errexit

mlserver --version
while true; do sleep 10; done
