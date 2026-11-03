#!/bin/bash

set -o nounset
set -o errexit

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

"${ROOT_DIR}/src/main/resources/model.sh" check
"${ROOT_DIR}/src/main/resources/model.sh" refresh
