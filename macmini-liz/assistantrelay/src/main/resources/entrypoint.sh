#!/bin/sh

set -o nounset
set -o errexit

cd /home/assistant-relay
npm run start
