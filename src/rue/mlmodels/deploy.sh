#!/bin/bash

set -o nounset
set -o errexit

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

"${ROOT_DIR}/src/build/resources/model.sh" publish
"${ROOT_DIR}/src/build/resources/model.sh" status
