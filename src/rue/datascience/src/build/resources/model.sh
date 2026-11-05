#!/bin/bash

set -o nounset
set -o errexit
set -o pipefail

export MLFLOW_DISABLE_TELEMETRY=true
export MLFLOW_DISABLE_AGENT_HINT=1
ROOT_DIR="$(cd "$(dirname "$(readlink -f "$0")")/../../.." && pwd)"
SOURCE_DIR="$(cd "${ROOT_DIR}/../.." && pwd)"
PYENV_BIN="${HOME}/.pyenv/versions/asystem/bin"
OUTPUT_DIR="${ROOT_DIR}/target/model-output"
COMMAND="${1:?usage: model.sh <unittest|systest|release|publish|status>}"
export PYTHONPATH="${SOURCE_DIR}/all/_/src/build/python${PYTHONPATH:+:${PYTHONPATH}}"

unittest() {
  rm -rf "${OUTPUT_DIR}"
  mkdir -p "${OUTPUT_DIR}"
  run_notebooks ""
}

systest() {
  run_notebooks "--register" || return 1
}

release() {
  local version="${1:?usage: model.sh release <version> [--by <name>]}" by="${USER}"
  shift
  [[ "${1:-}" == "--by" ]] && by="${2:?--by needs a name}"
  MLFLOW_TRACKING_URI="$(env_value MLFLOW_TRACKING_URI)" "${PYENV_BIN}/python" -W ignore -m asystem.model release "${SOURCE_DIR}" \
    --version "${version}" --by "${by}" --mlserver "$(mlserver_url)"
}

publish() {
  MLFLOW_TRACKING_URI="$(env_value MLFLOW_TRACKING_URI)" "${PYENV_BIN}/python" -W ignore -m asystem.model publish "${SOURCE_DIR}" --mlserver "$(mlserver_url)"
}

status() {
  MLFLOW_TRACKING_URI="$(env_value MLFLOW_TRACKING_URI)" "${PYENV_BIN}/python" -W ignore -m asystem.model status "${SOURCE_DIR}" --mlserver "$(mlserver_url)"
}

run_notebooks() {
  local flag="$1" status=0
  SECONDS=0
  for notebook_dir in "${ROOT_DIR}"/src/main/notebook/*/*/*/; do
    local target="${notebook_dir#"${ROOT_DIR}/src/main/notebook/"}"
    target="${target%/}"
    local state
    state="$("${PYENV_BIN}/python" -W ignore -m asystem.model changed "${notebook_dir}" "${SOURCE_DIR}/../.py_deps_prod.txt")"
    if [[ "${state}" == "unpackaged" ]]; then
      echo "--- SKIP: notebook ${target} (nothing packaged)"
      continue
    fi
    if [[ -z "${flag}" && "${state}" == "unchanged" ]]; then
      echo "--- SKIP: notebook ${target} (unchanged inputs)"
      continue
    fi
    MODEL_OUTPUT_DIR="${OUTPUT_DIR}" "${ROOT_DIR}/src/build/resources/notebook.sh" "${target}" ${flag:+"${flag}"} || status=1
  done
  if [[ "${status}" -eq 0 ]]; then
    printf 'PASS\nok  \tdatascience/notebook\t%ss\n' "${SECONDS}"
  else
    printf 'FAIL\nFAIL\tdatascience/notebook\t%ss\n' "${SECONDS}"
  fi
  return "${status}"
}

env_value() {
  sed -n "s/^$1=//p" "${ROOT_DIR}/.env" | tail -1 | tr -d '\r"'
}

mlserver_url() {
  echo "http://$(env_value MLSERVER_SERVICE_PROD):$(env_value MLSERVER_HTTP_PORT)"
}

case "${COMMAND}" in
  unittest) unittest ;;
  systest) systest ;;
  release) shift && release "$@" ;;
  publish) publish ;;
  status) status ;;
  *)
    echo "ERROR unknown command [${COMMAND}]" >&2
    exit 1
    ;;
esac
