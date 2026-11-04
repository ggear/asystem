#!/bin/bash

set -o nounset
set -o errexit

OUTPUT_ROOT="${1:?usage: parity.sh <model output dir> <gate dir>}"
GATE_DIR="${2:?usage: parity.sh <model output dir> <gate dir>}"
PARITY_PYTHON="${PARITY_PYTHON:-python}"
PARITY_RUST="${PARITY_RUST:?PARITY_RUST is the path of the Rust runner}"
PARITY_GO="${PARITY_GO:?PARITY_GO is the path of the Go runner}"

status=0
mkdir -p "${GATE_DIR}"
for project_dir in "${OUTPUT_ROOT}"/project/*/*/*/ "${OUTPUT_ROOT}"/*/*/default/; do
  [[ -f "${project_dir}project.json" ]] || continue
  workspace="${project_dir#"${OUTPUT_ROOT}/"}"
  workspace="${workspace%/}"
  workspace="${workspace#project/}"
  echo "Replaying [${workspace}]"
  "${PARITY_PYTHON}" -W ignore -m asystem.model gate "${project_dir%/}" --out "${GATE_DIR}/${workspace//\//_}.json" \
    --runner "rust=${PARITY_RUST}" --runner "go=${PARITY_GO}" || status=1
done
exit "${status}"
