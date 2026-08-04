#!/bin/bash
###############################################################################
# Generic module github dependency generate script,
# to be invoked by the Fabric management script
###############################################################################

# pull_repo: clone/update one .deps/ GitHub dependency and report whether the
# pinned checkout is behind the latest upstream tag. Args:
#   1 INVOKING_DIR
#   2 PULL_LATEST("True"=fetch)
#   3 MODULE_NAME
#   4 REPO_NAME
#   5 GITHUB_REPO
#   6 CHECKOUT_LABEL(pinned tag/branch)
#   7 FORKED_UPSTREAM
#   8 FORKED_LABEL(patch branch; "main"/"master" = track tip)
#   9 IGNORE_PRERELEASE("True" = pick latest from Releases API, not git tags)
function pull_repo() {
  INVOKING_DIR="${1}"
  PULL_LATEST="${2}"
  MODULE_NAME="${3}"
  REPO_NAME="${4}"
  GITHUB_REPO="${5}"
  CHECKOUT_LABEL="${6}"
  FORKED_UPSTREAM="${7}"
  FORKED_LABEL="${8}"
  IGNORE_PRERELEASE="${9}"
  [ ! -d "${INVOKING_DIR}/../../../.deps" ] && mkdir -p "${INVOKING_DIR}/../../../.deps"
  if [ ! -d "${INVOKING_DIR}/../../../.deps/${MODULE_NAME}/${REPO_NAME}" ]; then
    mkdir -p "${INVOKING_DIR}/../../../.deps/${MODULE_NAME}"
    cd "${INVOKING_DIR}/../../../.deps/${MODULE_NAME}" || return 1
    REPO_URL="git@github.com:${GITHUB_REPO}.git"
    echo "Repository URL [${REPO_URL}]"
    git clone "${REPO_URL}" "${REPO_NAME}"
    cd "${REPO_NAME}" || return 1
    git -c advice.detachedHead=false checkout "${CHECKOUT_LABEL}" 2>/dev/null
    # If the label was a branch (not a detached tag), track its upstream.
    if ! git branch | grep -q HEAD; then
      git branch --set-upstream-to="origin/${CHECKOUT_LABEL}" "${CHECKOUT_LABEL}"
    fi
  elif [ "${PULL_LATEST}" == "True" ]; then
    cd "${INVOKING_DIR}/../../../.deps/${MODULE_NAME}/${REPO_NAME}" || return 1
    echo "Pulling latest ${MODULE_NAME}/${REPO_NAME} ..."
    for BRANCH in master main development dev; do
      if [ "$(git branch | grep -c "${BRANCH}")" -eq 1 ]; then
        git checkout "${BRANCH}"
        git branch --set-upstream-to "origin/${BRANCH}" 2>/dev/null
        # Fork upkeep: rebase our default branch onto real upstream, replay our
        # patch branch (FORKED_LABEL) on top, force-push so CHECKOUT_LABEL tracks both.
        if [ "${FORKED_UPSTREAM}" != "" ] && [ "${FORKED_LABEL}" != "" ]; then
          git remote add upstream "${FORKED_UPSTREAM}" 2>/dev/null
          git fetch upstream
          git rebase "upstream/${BRANCH}"
          git checkout "${CHECKOUT_LABEL}"
          git merge "${FORKED_LABEL}"
          git push --all --force
          git checkout "${BRANCH}" 2>/dev/null
        fi
        break
      fi
    done
    # Force origin to ssh however it was cloned (https or ssh).
    git remote set-url origin "git@github.com:$(git remote get-url origin | sed 's|https://github.com/||;s|git@github.com:||')"
    echo "Remote set to [$(git remote get-url origin)]"
    # GitHub throttling is transient; retry forever with a backoff.
    until git pull --all; do
      echo "Git pull failed, sleeping to avoid Github throttling ..."
      sleep 90
    done
    REPO_DIR="$(cd "${INVOKING_DIR}/../../../.deps/${MODULE_NAME}/${REPO_NAME}" && pwd)"
    REPO_LABEL="$(basename "$(dirname "${INVOKING_DIR}")")"/"$(basename "${INVOKING_DIR}"):${REPO_NAME}"
    git -c advice.detachedHead=false checkout "${CHECKOUT_LABEL}"
    if ! git status | grep -q "${CHECKOUT_LABEL}"; then
      echo "" && echo "Module repository [${REPO_LABEL}] failed to checkout [${CHECKOUT_LABEL}]" && echo ""
    else
      git status
      echo -n "Module repository [${REPO_LABEL}] is being verified at [${REPO_DIR}] ... "
      # On a tag, git status reads "HEAD detached at <tag>"; strip to the tag.
      TAG_CHECKED_OUT="$(git status | head -n 1 | sed -E 's/^HEAD detached at //')"
      # Our fork patch branches ("ggear*") show a branch name, not a tag; resolve
      # to the tag. Must precede TAG_PREFIX so the prefix comes from the tag.
      git branch | grep -q "ggear" && TAG_CHECKED_OUT=$(git describe --tags --abbrev=0)
      # Restrict the "latest" search to the checked-out tag's naming family:
      # prefix = chars before the first digit (v1.23.2->"v", 2.4.0->"",
      # Z-Stack_3.x.0_coordinator_20230507->"Z-Stack_"). Keeps powercalc's v* off
      # its sibling "measure-v*" tags, and keeps Z-Stack_* tags a bare ^v?[0-9]
      # would drop. Does NOT split same-prefix sub-families (z-stack coordinator
      # vs router); prefix is interpolated unescaped so must stay regex-safe.
      TAG_PREFIX="$(printf '%s' "${TAG_CHECKED_OUT}" | sed -E 's/[0-9].*$//')"
      # Reset per call: not local, so a stale value would leak to the next dep
      # (once made every HA component report core's 2026.7.4 as its own latest).
      TAG_MOST_RECENT=""
      # Releases API excludes prereleases more reliably than the grep chain below.
      if [ "${IGNORE_PRERELEASE}" == "True" ]; then
        TAG_MOST_RECENT="$(gh api "repos/${GITHUB_REPO}/releases" --paginate --jq '.[] | select(.prerelease | not) | .tag_name' 2>/dev/null | sort -V | tail -n 1)"
      fi
      # Newest in-family tag by push order (creatordate), prereleases stripped.
      # Push order != version order, hence the version-sorted recompute below.
      [[ "${TAG_MOST_RECENT}" == "" ]] && TAG_MOST_RECENT="$(git tag --sort=creatordate | grep -E "^${TAG_PREFIX}[0-9]" | grep -iv dev | grep -iv beta | grep -v stable | grep -iv rc | grep -iv a0 | grep -iv 0a | grep -iv b0 | grep -iv b1 | grep -iv b2 | grep -iv 0b | grep -iv ts | tail -n 1)"
      # A real tag is pinned but nothing survived the filters: we can't classify
      # it, and the fallback below would falsely say "up to date". Fail instead.
      # Branch-tracked deps ("On branch …" / FORKED_LABEL main|master) are exempt.
      if [[ "${TAG_MOST_RECENT}" == "" ]] && [[ "${TAG_CHECKED_OUT}" != "" ]] && [[ "${TAG_CHECKED_OUT}" != "On branch "* ]] && [[ "${FORKED_LABEL}" != "main" && "${FORKED_LABEL}" != "master" ]]; then
        echo "" && echo "Module repository [${REPO_LABEL}] has no candidate version at tag [${TAG_CHECKED_OUT}] prefix [${TAG_PREFIX}] filtered out entirely" && echo ""
        return 1
      fi
      # Tag-less (branch-tracked) deps: compare the branch against itself.
      [[ "${TAG_CHECKED_OUT}" == "" ]] && TAG_CHECKED_OUT="$(git branch --show-current)" && TAG_MOST_RECENT="$(git branch --show-current)"
      [[ "${TAG_MOST_RECENT}" == "" ]] && TAG_MOST_RECENT="${TAG_CHECKED_OUT}"
      # If the pinned tag out-sorts the push-order pick, trust version order.
      if [ "${IGNORE_PRERELEASE}" != "True" ] && [ "$(printf "%s\n%s" "${TAG_MOST_RECENT#v}" "${TAG_CHECKED_OUT#v}" | sort -V | head -n1)" != "${TAG_CHECKED_OUT#v}" ]; then
        TAG_MOST_RECENT="$(git tag --sort=version:refname | grep -E "^${TAG_PREFIX}[0-9]" | grep -iv dev | grep -iv beta | grep -v stable | grep -iv rc | grep -iv a0 | grep -iv 0a | grep -iv b0 | grep -iv b1 | grep -iv b2 | grep -iv 0b | grep -iv ts | tail -n 1)"
      fi
      if [[ "${FORKED_LABEL}" == "main" || "${FORKED_LABEL}" == "master" ]]; then
        echo "tracking branch [${FORKED_LABEL}] at [${TAG_CHECKED_OUT}]"
        echo "Module [${REPO_LABEL}] [INFO] is up to date with version [${FORKED_LABEL}]"
      else
        echo "current tag [${TAG_CHECKED_OUT}] and upstream [${TAG_MOST_RECENT}]"
        [[ "${TAG_CHECKED_OUT}" == "${TAG_MOST_RECENT}" ]] && echo "Module [${REPO_LABEL}] [INFO] is up to date with version [${TAG_CHECKED_OUT}]"
        [[ "${TAG_CHECKED_OUT}" != "${TAG_MOST_RECENT}" ]] && echo "Module [${REPO_LABEL}] [WARN] requires update from version [${TAG_CHECKED_OUT}] to [${TAG_MOST_RECENT}]"
      fi
    fi
  fi
  cd "${INVOKING_DIR}" || return 1
}
