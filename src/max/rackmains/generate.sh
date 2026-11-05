#!/bin/bash

. ../../../.env_fab
. ../../../generate.sh

ROOT_DIR="$(dirname "$(readlink -f "$0")")"
MODEL_DIR="${ROOT_DIR}/src/build/resources/model"

export PYTHONPATH="${ROOT_DIR}/../../all/_/src/build/python${PYTHONPATH:+:${PYTHONPATH}}"
python -m asystem.model embed "${ROOT_DIR}" "${ROOT_DIR}/../.." rackmains_ups_battery || exit $?
if [ -f "${MODEL_DIR}/project.json" ]; then
  python -m asystem.model verify "${MODEL_DIR}" || exit $?
  python -m asystem.model generate "${MODEL_DIR}" --rust "${ROOT_DIR}/src/main/rust/rackmains/src/contract.rs" || exit $?
  (cd "${ROOT_DIR}/src/main/rust/rackmains" && rustfmt --edition 2021 src/contract.rs) || exit $?
fi
