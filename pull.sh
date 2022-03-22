#!/bin/bash

function pull_repo() {
  [ ! -d "${1}/../../.deps" ] && mkdir -p "${1}/../../.deps"
  if [ ! -d "${1}/../../.deps/${2}/${3}" ]; then
    mkdir -p "${1}/../../.deps/${2}"
    cd "${1}/../../.deps/${2}"
    git clone "git@github.com:${4}.git" "${3}"
    cd "${3}"
    git checkout "${5}"
  fi
  cd "${1}"
}
