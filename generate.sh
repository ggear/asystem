#!/bin/bash
###############################################################################
# Generic module generate script, to be invoked by the Fabric management script
###############################################################################

function pull_repo() {
  INVOKING_DIR="${1}"
  MODULE_NAME="${2}"
  REPO_NAME="${3}"
  GITHUB_REPO="${4}"
  VERSION_TO_CHECK_OUT="${5}"
  VERSION_TO_MERGE_WITH=""
  IGNORE_NEW_VERSIONS=""
  PULL_LATEST="${6}"
  [ ! -d "${INVOKING_DIR}/../../../.deps" ] && mkdir -p "${INVOKING_DIR}/../../../.deps"
  if [ ! -d "${INVOKING_DIR}/../../../.deps/${MODULE_NAME}/${REPO_NAME}" ]; then
    mkdir -p "${INVOKING_DIR}/../../../.deps/${MODULE_NAME}"
    cd "${INVOKING_DIR}/../../../.deps/${MODULE_NAME}"
    REPO_URL="git@github.com:${GITHUB_REPO}.git"
    echo "Repository URL [${REPO_URL}]"
    git clone ${REPO_URL} "${REPO_NAME}"
    cd "${REPO_NAME}"
    git -c advice.detachedHead=false checkout "${VERSION_TO_CHECK_OUT}" 2>/dev/null
    if [ $(git branch | grep HEAD | wc -l) -eq 0 ]; then
      git branch --set-upstream-to="origin/${VERSION_TO_CHECK_OUT}" "${VERSION_TO_CHECK_OUT}"
    fi
  elif [ "${PULL_LATEST}" == "True" ]; then
    cd "${INVOKING_DIR}/../../../.deps/${MODULE_NAME}/${REPO_NAME}"
    echo "Pulling latest ${MODULE_NAME}/${REPO_NAME} ..."
    for BRANCH in development dev main master; do
      if [ $(git branch | grep ${BRANCH} | wc -l) -eq 1 ]; then
        git checkout ${BRANCH} 2>/dev/null
        git branch --set-upstream-to origin/${BRANCH} 2>/dev/null
      fi
    done
    git remote set-url origin https://github.com/$(git remote get-url origin | sed 's/https:\/\/github.com\///' | sed 's/git@github.com://')
    echo "Remote set to [$(git remote get-url origin)]"
    until git pull --all; do
      echo "Git pull failed, sleeping to avoid Github throttling ..."
      sleep 90
    done
    git -c advice.detachedHead=false checkout "${VERSION_TO_CHECK_OUT}" 2>/dev/null
    git status
    REPO_DIR="$(cd ${INVOKING_DIR}/../../../.deps/${MODULE_NAME}/${REPO_NAME} && pwd)"
    REPO_LABEL="$(basename $(dirname ${INVOKING_DIR}))/$(basename ${INVOKING_DIR}):${REPO_NAME}"
    echo -n "Module repository [${REPO_LABEL}] is being verified at [${REPO_DIR}] ... "
    TAG_CHECKED_OUT=$(git tag --points-at HEAD | head -n 1)
    TAG_MOST_RECENT=$(git tag --sort=creatordate | grep -iv dev | grep -iv beta | grep -v stable | grep -iv rc1 | grep -iv rc2 | grep -iv b0 | grep -iv 0b | tail -n 1)
    [[ $(git tag | wc -l) -eq 0 ]] && TAG_CHECKED_OUT=$(git branch --show-current) && TAG_MOST_RECENT=$(git branch --show-current)
    [[ $(git branch | grep "ggear" | wc -l) -gt 0 ]] && TAG_MOST_RECENT=$(git describe --tags --abbrev=0) && TAG_CHECKED_OUT=$(git describe --tags --abbrev=0)
    [[ "${TAG_CHECKED_OUT}" == "" ]] && TAG_CHECKED_OUT=$(git branch --show-current) && TAG_MOST_RECENT=$(git branch --show-current)
    [[ "${TAG_MOST_RECENT}" == "" ]] && TAG_CHECKED_OUT="${TAG_CHECKED_OUT}" && TAG_MOST_RECENT="${TAG_CHECKED_OUT}"
    echo "current tag [${TAG_CHECKED_OUT}] and upstream [${TAG_MOST_RECENT}]"
    [[ ${TAG_CHECKED_OUT} == ${TAG_MOST_RECENT} ]] && echo "Module [${REPO_LABEL}] [INFO] is up to date with version [${TAG_CHECKED_OUT}]"
    [[ ${TAG_CHECKED_OUT} != ${TAG_MOST_RECENT} ]] && echo "Module [${REPO_LABEL}] [WARN] requires update from version [${TAG_CHECKED_OUT}] to [${TAG_MOST_RECENT}]"
  fi
  cd "${INVOKING_DIR}"
}
