#!/bin/bash

. ../../../.env_fab
. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

export PYTHONPATH="${ROOT_DIR}/../../rue/mlmodels/src/main/python${PYTHONPATH:+:${PYTHONPATH}}"
python -m mlmodels embed "${ROOT_DIR}" "${ROOT_DIR}/../.." rackmains_ups_battery || exit $?
