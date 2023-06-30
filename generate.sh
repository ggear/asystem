#!/bin/bash
###############################################################################
#
# Generic module generate script, to be invoked by the fabric management script
#
###############################################################################

function pull_repo() {
  [ ! -d "${1}/../../../.deps" ] && mkdir -p "${1}/../../../.deps"
  if [ ! -d "${1}/../../../.deps/${2}/${3}" ]; then
    mkdir -p "${1}/../../../.deps/${2}"
    cd "${1}/../../../.deps/${2}"
    git clone "git@github.com:${4}.git" "${3}"
    cd "${3}"
    git -c advice.detachedHead=false checkout "${5}" 2>/dev/null
    if [ $(git branch | grep HEAD | wc -l) -eq 0 ]; then
      git branch --set-upstream-to="origin/${5}" "${5}"
    fi
  elif [ "${6}" == "True" ]; then
    cd "${1}/../../../.deps/${2}/${3}"
    echo "Pulling latest ${2}/${3} version ${5} ..."
    if [ $(git branch | grep HEAD | wc -l) -eq 1 ]; then
      for BRANCH in dev main master; do
        if [ $(git branch | grep ${BRANCH} | wc -l) -eq 1 ]; then
          git checkout ${BRANCH} 2>/dev/null
        fi
      done
    fi
    git remote set-url origin https://github.com/$(git remote get-url origin | sed 's/https:\/\/github.com\///' | sed 's/git@github.com://')
    until git pull --all; do
      echo "Sleeping to avoid Github throttling ..."
      sleep 90
    done
    git -c advice.detachedHead=false checkout "${5}" 2>/dev/null
    git status
    REPO=$(cd ${1}/../../../.deps/${2}/${3} && pwd)
    if [ $(git describe --tags --abbrev=0 2>/dev/null) ]; then
      TAG_CHECKED_OUT=$(git describe --tags --abbrev=0)
      TAG_MOST_RECENT=$(git describe --tags $(git rev-list --tags --max-count=1))
      [ ${TAG_CHECKED_OUT} != ${TAG_MOST_RECENT} ] && echo "Repo [${REPO}] requires update from [${TAG_CHECKED_OUT}] to [${TAG_MOST_RECENT}]"
    else
      echo "Repo [${REPO}] has no tags, sync them!"
    fi
  fi
  cd "${1}"
}
