#!/bin/bash

set -o nounset
set -o errexit
set -o pipefail

ROOT_DIR="$(cd "$(dirname "$(readlink -f "$0")")/../../.." && pwd)"
SOURCE_DIR="$(cd "${ROOT_DIR}/../.." && pwd)"
PYENV_BIN="${HOME}/.pyenv/versions/asystem/bin"
COMMAND="${1:?usage: model.sh <check|build|parity|refresh|status|rollback|ship>}"
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
  parity "${output_dir}" || status=1
  return "${status}"
}

build() {
  local replay_dir="${ROOT_DIR}/src/test/replay"
  (
    . "${SOURCE_DIR}/../.env_fab"
    export CARGO_HOME="${HOME}/.rust/versions/asystem" RUSTUP_HOME="${HOME}/.rust/versions/asystem"
    export PATH="${CARGO_HOME}/bin:${PATH}"
    export CARGO_TARGET_DIR="${ROOT_DIR}/target/rust"
    cd "${replay_dir}/rust" && cargo build --quiet
    cd "${replay_dir}/go" && "${GOROOT}/bin/go" build -o "${ROOT_DIR}/target/go/modelreplay" .
  )
}

parity() {
  local output_root="${1:-${ROOT_DIR}/target/model-output}"
  local gate_dir="${ROOT_DIR}/target/gate"
  local runtime local_arch arch name status=0
  local_arch="$(architecture "$(uname -m)")"
  runtime="${SERVICE_LOCAL_RUNTIME:-$(sed -n 's/^SERVICE_LOCAL_RUNTIME=//p' "${ROOT_DIR}/.env" 2>/dev/null | tr -d '\r"' | tail -1 || true)}"
  runtime="${runtime:-emulated}"
  local archs=("${local_arch}")
  case "${runtime}" in
    native) ;;
    emulated)
      while read -r arch; do
        [[ "${arch}" == "${local_arch}" ]] || archs+=("${arch}")
      done < <(host_architectures)
      ;;
    *)
      echo "ERROR unknown SERVICE_LOCAL_RUNTIME [${runtime}]" >&2
      return 1
      ;;
  esac
  rm -rf "${gate_dir}"
  mkdir -p "${gate_dir}"
  for arch in "${archs[@]}"; do
    echo "Parity on [${arch}] runtime [${runtime}]"
    if [[ "${arch}" == "${local_arch}" ]]; then
      parity_native "${output_root}" "${gate_dir}/${arch}" || status=1
    else
      parity_container "${arch}" "${output_root}" "${gate_dir}/${arch}" || status=1
    fi
  done
  for gate_file in "${gate_dir}/${archs[0]}"/*.json; do
    [[ -f "${gate_file}" ]] || continue
    name="$(basename "${gate_file}")"
    local gates=()
    for arch in "${archs[@]}"; do
      [[ -f "${gate_dir}/${arch}/${name}" ]] && gates+=("${gate_dir}/${arch}/${name}")
    done
    "${PYENV_BIN}/python" -W ignore -m asystem.model gate-merge --out "${gate_dir}/${name}" "${gates[@]}" || status=1
  done
  return "${status}"
}

parity_native() {
  build || return 1
  PARITY_PYTHON="${PYENV_BIN}/python" PARITY_RUST="${ROOT_DIR}/target/rust/debug/modelreplay" PARITY_GO="${ROOT_DIR}/target/go/modelreplay" \
    "${ROOT_DIR}/src/test/replay/parity.sh" "$1" "$2"
}

parity_container() {
  local arch="$1" output_root="$2" gate_dir="$3"
  local context="${ROOT_DIR}/target/replay/context-${arch}"
  local platform="linux/amd64"
  [[ "${arch}" == "aarch64" ]] && platform="linux/arm64"
  rm -rf "${context}"
  mkdir -p "${context}" "${gate_dir}"
  cp -R "${ROOT_DIR}/src/test/replay/Dockerfile" "${ROOT_DIR}/src/test/replay/.dockerignore" "${ROOT_DIR}/src/test/replay/parity.sh" "${ROOT_DIR}/src/test/replay/go" "${context}"
  mkdir -p "${context}/rust"
  cp -R "${ROOT_DIR}/src/test/replay/rust/Cargo.toml" "${ROOT_DIR}/src/test/replay/rust/Cargo.lock" "${ROOT_DIR}/src/test/replay/rust/src" "${context}/rust"
  (
    . "${SOURCE_DIR}/../.env_fab"
    grep -iE '^(numpy|pandas|pathlib2|requests|grafana-foundation-sdk|wasmtime|onnx|onnxruntime)==' "${SOURCE_DIR}/../py_deps_prod.txt" >"${context}/requirements.txt"
    echo "mlflow-skinny==${MLFLOW_VERSION}" >>"${context}/requirements.txt"
    timeout 3000 docker buildx build "${context}" --progress=plain --platform "${platform}" --output type=docker --tag "asystem-modelparity:${arch}" \
      --build-arg "ASYSTEM_PYTHON_VERSION=${PYTHON_VERSION}" --build-arg "ASYSTEM_GO_VERSION=${GO_VERSION}" --build-arg "ASYSTEM_RUST_VERSION=${RUST_VERSION}"
  ) || return 1
  timeout 900 docker run --rm --platform "${platform}" -v "${output_root}:/work/model-output:ro" -v "${SOURCE_DIR}/all/_/src/build:/asystem/build:ro" \
    -v "${gate_dir}:/work/gate" "asystem-modelparity:${arch}" /work/model-output /work/gate
}

architecture() {
  case "$1" in
    arm64 | aarch64) echo "aarch64" ;;
    *) echo "$1" ;;
  esac
}

host_architectures() {
  awk -F'[=,]' '$6 != "ignore" && $3 != "" { print $3 }' "${SOURCE_DIR}/../.hosts" | while read -r arch; do architecture "${arch}"; done | sort -u
}

refresh() {
  local label host
  label="$(basename "$(dirname "${ROOT_DIR}")")"
  host="$(awk -F'[=,]' -v label="${label}" '$1 == label { print $2 "-" $1 }' "${SOURCE_DIR}/../.hosts")"
  [[ -n "${host}" ]] || {
    echo "ERROR no host for label [${label}]" >&2
    return 1
  }
  echo "Restarting mlserver on [${host}], which pulls every release model at start and is healthy only once each is ready"
  # shellcheck disable=SC2016
  timeout 900 ssh -o ConnectTimeout=10 "root@${host}" 'docker restart mlserver >/dev/null && until [ "$(docker inspect -f "{{.State.Health.Status}}" mlserver)" = healthy ]; do sleep 5; done' || {
    echo "ERROR mlserver did not become healthy, see docker logs mlserver on [${host}]" >&2
    return 1
  }
  echo "mlserver healthy"
}

env_value() {
  sed -n "s/^$1=//p" "${ROOT_DIR}/.env" | tail -1 | tr -d '\r"'
}

status() {
  local mlserver
  mlserver="http://$(env_value MLSERVER_SERVICE_PROD):$(env_value MLSERVER_HTTP_PORT)"
  MLFLOW_TRACKING_URI="$(sed -n 's/^MLFLOW_TRACKING_URI=//p' "${ROOT_DIR}/.env_all")" "${PYENV_BIN}/python" -W ignore -m asystem.model status "${SOURCE_DIR}" --mlserver "${mlserver}"
}

rollback() {
  local name="${1:?usage: model.sh rollback <registered model>}"
  MLFLOW_TRACKING_URI="$(sed -n 's/^MLFLOW_TRACKING_URI=//p' "${ROOT_DIR}/.env_all")" "${PYENV_BIN}/python" -W ignore -m asystem.model rollback "${name}"
  refresh
}

ship() {
  local target="${1:?usage: model.sh ship <module>/<model>/<notebook> [--dry-run] [--reviewed-by <name>]}" dry_run=0 reviewer="${USER}"
  shift
  while (($#)); do
    case "$1" in
      --dry-run) dry_run=1 ;;
      --reviewed-by) reviewer="${2:?--reviewed-by needs a name}" && shift ;;
      *)
        echo "ERROR unknown option [$1]" >&2
        return 1
        ;;
    esac
    shift
  done
  local name="${target//\//_}"
  echo "Ship [1/5] check"
  check || return 1
  [[ -f "${ROOT_DIR}/target/gate/${name}.json" ]] || {
    echo "ERROR no parity gate for [${name}], the notebook produced no project" >&2
    return 1
  }
  if ((dry_run)); then
    echo "Ship dry run, would register [${target}] as candidate, promote [${name}] reviewed by [${reviewer}] and restart mlserver"
    return 0
  fi
  echo "Ship [2/5] register"
  "${ROOT_DIR}/src/main/resources/notebook.sh" "${target}" --register || return 1
  echo "Ship [3/5] promote"
  "${ROOT_DIR}/src/main/resources/promote.sh" "${name}" --reviewed-by "${reviewer}" || return 1
  echo "Ship [4/5] serve"
  refresh || return 1
  echo "Ship [5/5] status"
  status | grep -F "\"registry\": \"${name}\""
}

case "${COMMAND}" in
  check) check ;;
  build) build ;;
  parity) parity ;;
  refresh) refresh ;;
  status) status ;;
  rollback) rollback "${2:-}" ;;
  ship) shift && ship "$@" ;;
  *)
    echo "ERROR unknown command [${COMMAND}]" >&2
    exit 1
    ;;
esac
