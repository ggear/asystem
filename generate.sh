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
    TAG_CHECKED_OUT=$(git describe --tags --abbrev=0)
    TAG_MOST_RECENT=$(git describe --tags --abbrev=0 $(git rev-list --tags --max-count=10) | grep -iv dev | grep -iv beta | head -n 1)
    [ $(git tag | wc -l) -eq 0 ] && TAG_CHECKED_OUT=$(git branch --show-current) && TAG_MOST_RECENT=$(git branch --show-current)
    [ $(git branch | grep "ggear-" | wc -l) -gt 0 ] && TAG_MOST_RECENT=${TAG_CHECKED_OUT}
    [ ${TAG_CHECKED_OUT} == ${TAG_MOST_RECENT} ] && echo "Module [${REPO}] [INFO] is up to date with version [${TAG_CHECKED_OUT}]"
    [ ${TAG_CHECKED_OUT} != ${TAG_MOST_RECENT} ] && echo "Module [${REPO}] [WARN] requires update from version [${TAG_CHECKED_OUT}] to [${TAG_MOST_RECENT}]"
  fi
  cd "${1}"
}
