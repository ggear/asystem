#!/bin/bash

function pull_repo() {
  [ ! -d "${1}/../../.deps" ] && mkdir -p "${1}/../../.deps"
  if [ ! -d "${1}/../../.deps/${2}/${3}" ]; then
    mkdir -p "${1}/../../.deps/${2}"
    cd "${1}/../../.deps/${2}"
    git clone "git@github.com:${4}.git" "${3}"
    cd "${3}"
    git checkout "${5}"
    if [ $(git branch | grep HEAD | wc -l) -eq 0 ]; then
      git branch --set-upstream-to="origin/${5}" "${5}"
    fi
  else
    cd "${1}/../../.deps/${2}/${3}"
    # TODO: Make branch/tag refresh
    #    if [ $(git branch | grep HEAD | wc -l) -eq 0 ]; then
    #      git branch --set-upstream-to="origin/${5}" "${5}"
    #    fi
    #    git pull --all
    #    git checkout "${5}"
    #    git pull --all
  fi
  cd "${1}"
}
