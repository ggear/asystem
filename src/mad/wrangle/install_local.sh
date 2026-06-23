#!/usr/bin/env bash

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

SOURCE_ROOT="${ROOT_DIR}/src/test/resources/repos/release"
TARGET_ROOT="${ROOT_DIR}/target/runtime-system/data"

for data_dir in "${SOURCE_ROOT}"/*/replete_1/data; do
  [[ -d "${data_dir}" ]] || continue
  repo_name="$(basename "${data_dir%/replete_1/data}")"
  target_dir="${TARGET_ROOT}/${repo_name}"
  rm -rf "${target_dir}"
  mkdir -p "${target_dir}"
  find "${data_dir}" -maxdepth 1 -not -name '_*' -not -path "${data_dir}" -exec cp -vpf {} "${target_dir}/" \;
done
