#!/bin/bash

set -o nounset
set -o errexit
set -o pipefail

ROOT_DIR="$(cd "$(dirname "$(readlink -f "$0")")/../../.." && pwd)"
SOURCE_DIR="$(cd "${ROOT_DIR}/../.." && pwd)"
PYENV_BIN="${HOME}/.pyenv/versions/asystem/bin"
COMMAND="${1:?usage: model.sh <check|refresh>}"
export PYTHONPATH="${SOURCE_DIR}/all/_/src/build/python${PYTHONPATH:+:${PYTHONPATH}}"

check() {
  local output_dir="${ROOT_DIR}/target/model-output"
  local status=0
  rm -rf "${output_dir}"
  mkdir -p "${output_dir}"
  for notebook_dir in "${ROOT_DIR}"/src/main/model/*/*/*/; do
    local target="${notebook_dir#"${ROOT_DIR}/src/main/model/"}"
    target="${target%/}"
    echo "Running notebook [${target}]"
    MODEL_OUTPUT_DIR="${output_dir}" "${ROOT_DIR}/src/main/resources/notebook.sh" "${target}" >"${output_dir}/notebook.log" 2>&1 || {
      cat "${output_dir}/notebook.log" >&2
      echo "ERROR notebook failed [${target}]" >&2
      status=1
    }
    [[ -f "${ROOT_DIR}/target/notebook/${target}/notebook.ipynb" ]] || continue
    "${PYENV_BIN}/python" - "${ROOT_DIR}/target/notebook/${target}/notebook.ipynb" "${target}" <<'PYTHON'
import json
import sys

with open(sys.argv[1]) as notebook_file:
    cells = json.load(notebook_file)["cells"]
for cell in cells:
    for output in cell.get("outputs", []):
        for line in "".join(output.get("text", "")).splitlines():
            if line.startswith("acceptance ["):
                print(f"Acceptance {sys.argv[2]} {line}")
PYTHON
  done
  for committed_dir in "${SOURCE_DIR}"/*/*/src/build/resources/model/default; do
    [[ -f "${committed_dir}/project.json" ]] || continue
    local consumer="${committed_dir#"${SOURCE_DIR}/"}"
    consumer="${consumer%/src/build/resources/model/default}"
    echo "Comparing [${consumer}] default"
    "${PYENV_BIN}/python" -W ignore -m asystem.model compare "${output_dir}/${consumer}/default" "${committed_dir}" || status=1
  done
  for release_dir in "${SOURCE_DIR}"/*/*/src/build/resources/model/release; do
    [[ -f "${release_dir}/project.json" ]] || continue
    echo "Checking [${release_dir#"${SOURCE_DIR}/"}]"
    "${PYENV_BIN}/python" -W ignore -m asystem.model check-release "${release_dir}" || status=1
  done
  return "${status}"
}

refresh() {
  local label host
  label="$(basename "$(dirname "${ROOT_DIR}")")"
  host="$(awk -F'[=,]' -v label="${label}" '$1 == label { print $2 "-" $1 }' "${SOURCE_DIR}/../.hosts")"
  [[ -n "${host}" ]] || {
    echo "ERROR no host for label [${label}]" >&2
    return 1
  }
  echo "Refreshing served models on [${host}]"
  timeout 300 ssh -o ConnectTimeout=10 "root@${host}" "docker start -a mlserver_bootstrap && docker restart mlserver"
}

case "${COMMAND}" in
  check) check ;;
  refresh) refresh ;;
  *)
    echo "ERROR unknown command [${COMMAND}]" >&2
    exit 1
    ;;
esac
