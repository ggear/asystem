#!/bin/bash

# TODO: Update to check docker and git versions check - is there a newer version available?

function pull_repo() {
  [ ! -d "${1}/../../.deps" ] && mkdir -p "${1}/../../.deps"
  if [ ! -d "${1}/../../.deps/${2}/${3}" ]; then
    mkdir -p "${1}/../../.deps/${2}"
    cd "${1}/../../.deps/${2}"
    git clone "git@github.com:${4}.git" "${3}"
    cd "${3}"
    git -c advice.detachedHead=false checkout "${5}"
    if [ $(git branch | grep HEAD | wc -l) -eq 0 ]; then
      git branch --set-upstream-to="origin/${5}" "${5}"
    fi
  elif [ "${6}" == "True" ]; then
    cd "${1}/../../.deps/${2}/${3}"
    echo "Pulling latest ${2}/${3} version ${5} ..."
    if [ $(git branch | grep HEAD | wc -l) -eq 1 ]; then
      for BRANCH in dev main master; do
        if [ $(git branch | grep ${BRANCH} | wc -l) -eq 1 ]; then
          git checkout ${BRANCH}
        fi
      done
    fi
    until git pull --all; do
      echo "Sleeping to avoid Github throttling ..."
      sleep 90
    done
    git -c advice.detachedHead=false checkout "${5}"
  fi
  cd "${1}"
}
