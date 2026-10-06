#!/bin/bash
###############################################################################
# Generic module github dependency generate script,
# to be invoked by the Fabric management script
###############################################################################

# at_checkout_label: whether HEAD is at label 1, on the branch itself for a
# local branch, else at the commit a tag resolves to.
function at_checkout_label() {
  if git show-ref -q --verify "refs/heads/${1}"; then
    [ "$(git branch --show-current)" == "${1}" ]
  else
    [ "$(git rev-parse -q --verify HEAD)" != "" ] && [ "$(git rev-parse -q --verify HEAD)" == "$(git rev-parse -q --verify "${1}^{commit}")" ]
  fi
}

# replace_path: replace path 2 with a copy of path 1, refusing a missing or
# empty source, so a failed build or download never removes good output. A
# directory is replaced whole; a file is overwritten in place, which needs no
# write access to its directory (/usr/local/bin).
function replace_path() {
  if [ ! -s "${1}" ] || { [ -d "${1}" ] && [ "$(ls -A "${1}")" == "" ]; }; then
    echo "Source missing or empty [${1}], refusing to replace [${2}]" >&2
    return 1
  fi
  mkdir -p "$(dirname "${2}")" || return 1
  if [ -d "${1}" ]; then
    rm -rf "${2}" && cp -rvf "${1}" "${2}"
  else
    cp -vf "${1}" "${2}"
  fi
}

# pull_repo: clone or update one .deps dependency, hold it at its pin, and
# report whether upstream has a newer release. Args:
#   1 INVOKING_DIR
#   2 PULL_LATEST ("True" fetches, merges and pushes fork upkeep)
#   3 MODULE_NAME
#   4 REPO_NAME
#   5 GITHUB_REPO
#   6 CHECKOUT_LABEL (pinned tag or branch; for a fork, its patch branch)
#   7 FORKED_UPSTREAM (a fork's upstream URL)
#   8 FORKED_LABEL (upstream tag or branch merged into the patch branch)
#   9 IGNORE_PRERELEASE ("True" takes the latest from the Releases API)
function pull_repo() {
  local INVOKING_DIR="${1}"
  local PULL_LATEST="${2}"
  local MODULE_NAME="${3}"
  local REPO_NAME="${4}"
  local GITHUB_REPO="${5}"
  local CHECKOUT_LABEL="${6}"
  local FORKED_UPSTREAM="${7}"
  local FORKED_LABEL="${8}"
  local IGNORE_PRERELEASE="${9}"
  local REPO_URL="" CONFLICTED="" MARKED="" FILE="" BRANCH="" OWN_COMMITS="" COMMIT="" UPSTREAM_REF="" MERGE_REF=""
  local REPO_DIR="" REPO_LABEL="" TAG_CHECKED_OUT="" TAG_PREFIX="" TAG_MOST_RECENT="" TAG_FAMILY="" PATCH_COUNT="" FETCH_ATTEMPT="" BRANCH_PINNED=""
  [ ! -d "${INVOKING_DIR}/../../../.deps" ] && mkdir -p "${INVOKING_DIR}/../../../.deps"
  if [ ! -d "${INVOKING_DIR}/../../../.deps/${MODULE_NAME}/${REPO_NAME}" ]; then
    mkdir -p "${INVOKING_DIR}/../../../.deps/${MODULE_NAME}"
    cd "${INVOKING_DIR}/../../../.deps/${MODULE_NAME}" || return 1
    REPO_URL="git@github.com:${GITHUB_REPO}.git"
    echo "Repository URL [${REPO_URL}]"
    git clone "${REPO_URL}" "${REPO_NAME}"
    cd "${REPO_NAME}" || return 1
    if [ "${FORKED_UPSTREAM}" != "" ] && [ "${FORKED_LABEL}" != "" ]; then
      git remote add upstream "${FORKED_UPSTREAM}"
      git fetch upstream --tags --force || return 1
    fi
  fi
  # Every run: conclude a merge left in progress once its files are free of
  # conflict markers, then check out the pin (fetching it first if new),
  # forcing only past line-ending noise, never past real local edits.
  cd "${INVOKING_DIR}/../../../.deps/${MODULE_NAME}/${REPO_NAME}" || return 1
  if [ "${FORKED_UPSTREAM}" != "" ] && [ "${FORKED_LABEL}" != "" ]; then
    git config rerere.enabled true
    git config rerere.autoUpdate true
    if [ -f .git/MERGE_HEAD ]; then
      CONFLICTED="$(git diff --name-only --diff-filter=U)"
      MARKED=""
      while IFS= read -r FILE; do
        [ "${FILE}" != "" ] && grep -qE '^(<<<<<<<|[|]{7}|>>>>>>>)( |$)' -- "${FILE}" 2>/dev/null && MARKED="${MARKED} [${FILE}]"
      done <<<"${CONFLICTED}"
      if [ "${MARKED}" != "" ]; then
        echo "" && echo "Module repository [${MODULE_NAME}/${REPO_NAME}] merge into [${CHECKOUT_LABEL}] still has conflict markers in${MARKED}, resolve them in [$(pwd)] and rerun" && echo ""
        return 1
      fi
      while IFS= read -r FILE; do
        [ "${FILE}" != "" ] && { git add -A -- "${FILE}" || return 1; }
      done <<<"${CONFLICTED}"
      git commit --no-edit || return 1
      echo "Module repository [${MODULE_NAME}/${REPO_NAME}] concluded hand-resolved merge into [${CHECKOUT_LABEL}]"
    fi
  fi
  if ! at_checkout_label "${CHECKOUT_LABEL}"; then
    if [ "${PULL_LATEST}" == "True" ] && ! git rev-parse -q --verify "${CHECKOUT_LABEL}^{commit}" >/dev/null && ! git rev-parse -q --verify "origin/${CHECKOUT_LABEL}" >/dev/null; then
      git fetch --all --tags --force
    fi
    if git diff --quiet --ignore-cr-at-eol HEAD && [ "$(git ls-files --others --exclude-standard)" == "" ]; then
      git -c advice.detachedHead=false checkout -f "${CHECKOUT_LABEL}"
    else
      git -c advice.detachedHead=false checkout "${CHECKOUT_LABEL}"
    fi
    if ! at_checkout_label "${CHECKOUT_LABEL}"; then
      echo "" && echo "Module repository [${MODULE_NAME}/${REPO_NAME}] cannot check out pinned [${CHECKOUT_LABEL}] (missing label, or local edits block it) in [$(pwd)]" && echo ""
      return 1
    fi
  fi
  git show-ref -q --verify "refs/heads/${CHECKOUT_LABEL}" && git branch --set-upstream-to "origin/${CHECKOUT_LABEL}" >/dev/null 2>&1
  if [ "${PULL_LATEST}" == "True" ]; then
    cd "${INVOKING_DIR}/../../../.deps/${MODULE_NAME}/${REPO_NAME}" || return 1
    echo "Pulling latest ${MODULE_NAME}/${REPO_NAME} ..."
    if [ -f .git/MERGE_HEAD ] || [ -d .git/rebase-apply ] || [ -d .git/rebase-merge ]; then
      echo "" && echo "Module repository [${MODULE_NAME}/${REPO_NAME}] has an unresolved merge/rebase from a previous run; resolve it (or 'git merge --abort'/'git rebase --abort') by hand in [$(pwd)] before pulling again" && echo ""
      return 1
    fi
    # Fork upkeep stops only on a genuine conflict. The fork's default branches
    # mirror upstream (after an upstream rewrite, realigned by a leased force
    # push unless they hold our own commits); the patch branch then merges
    # origin's copy and the pinned upstream label, rerere replaying known
    # resolutions, and an unresolved conflict is left in progress.
    if [ "${FORKED_UPSTREAM}" != "" ] && [ "${FORKED_LABEL}" != "" ]; then
      git remote add upstream "${FORKED_UPSTREAM}" 2>/dev/null
      git fetch origin || return 1
      git fetch upstream --tags --force || return 1
      for BRANCH in master main development dev; do
        if git rev-parse -q --verify "refs/remotes/upstream/${BRANCH}" >/dev/null && git rev-parse -q --verify "refs/remotes/origin/${BRANCH}" >/dev/null; then
          if ! git merge-base --is-ancestor "origin/${BRANCH}" "upstream/${BRANCH}"; then
            OWN_COMMITS=""
            for COMMIT in $(git rev-list --author="$(git config user.name)" "upstream/${BRANCH}..origin/${BRANCH}"); do
              git branch -r --contains "${COMMIT}" | grep -q "origin/ggear" || OWN_COMMITS="${OWN_COMMITS} ${COMMIT}"
            done
            if [ "${OWN_COMMITS}" != "" ]; then
              echo "" && echo "Module repository [${MODULE_NAME}/${REPO_NAME}] [WARN] fork [origin/${BRANCH}] holds our commits [${OWN_COMMITS# }] in no ggear branch, not realigning it to [upstream/${BRANCH}]" && echo ""
              continue
            fi
            echo "Module repository [${MODULE_NAME}/${REPO_NAME}] realigning fork [origin/${BRANCH}] to rewritten [upstream/${BRANCH}]"
          fi
          git push --force-with-lease="refs/heads/${BRANCH}:$(git rev-parse "origin/${BRANCH}")" origin "refs/remotes/upstream/${BRANCH}:refs/heads/${BRANCH}" ||
            echo "Module repository [${MODULE_NAME}/${REPO_NAME}] [WARN] fork [origin/${BRANCH}] could not be updated to [upstream/${BRANCH}]"
        fi
      done
      UPSTREAM_REF="${FORKED_LABEL}"
      git rev-parse -q --verify "refs/remotes/upstream/${FORKED_LABEL}" >/dev/null && UPSTREAM_REF="upstream/${FORKED_LABEL}"
      for MERGE_REF in "origin/${CHECKOUT_LABEL}" "${UPSTREAM_REF}"; do
        if ! git merge --no-edit "${MERGE_REF}"; then
          if [ -f .git/MERGE_HEAD ] && [ "$(git diff --name-only --diff-filter=U)" == "" ]; then
            git commit --no-edit || return 1
            echo "Module repository [${MODULE_NAME}/${REPO_NAME}] merge of [${MERGE_REF}] into [${CHECKOUT_LABEL}] resolved from recorded resolutions"
          else
            echo "" && echo "Module repository [${MODULE_NAME}/${REPO_NAME}] merge of [${MERGE_REF}] into [${CHECKOUT_LABEL}] conflicts, left in progress, edit the conflicted files in [$(pwd)] and rerun" && echo ""
            return 1
          fi
        fi
      done
      git push origin "${CHECKOUT_LABEL}" || return 1
    else
      for BRANCH in master main development dev; do
        if [ "$(git branch | grep -c "${BRANCH}")" -eq 1 ]; then
          git checkout "${BRANCH}" || return 1
          git branch --set-upstream-to "origin/${BRANCH}" 2>/dev/null
          break
        fi
      done
    fi
    # Force origin to ssh however it was cloned (https or ssh).
    git remote set-url origin "git@github.com:$(git remote get-url origin | sed 's|https://github.com/||;s|git@github.com:||')"
    echo "Remote set to [$(git remote get-url origin)]"
    # Retry transient GitHub throttling, giving up after five attempts.
    for FETCH_ATTEMPT in 1 2 3 4 5; do
      git fetch --all && break
      if [ "${FETCH_ATTEMPT}" -eq 5 ]; then
        echo "" && echo "Module repository [${MODULE_NAME}/${REPO_NAME}] fetch failed [${FETCH_ATTEMPT}] times, giving up" && echo ""
        return 1
      fi
      echo "Git fetch failed [${FETCH_ATTEMPT}], sleeping to avoid Github throttling ..."
      sleep 90
    done
    REPO_DIR="$(cd "${INVOKING_DIR}/../../../.deps/${MODULE_NAME}/${REPO_NAME}" && pwd)"
    REPO_LABEL="$(basename "$(dirname "${INVOKING_DIR}")")"/"$(basename "${INVOKING_DIR}"):${REPO_NAME}"
    # Forced for plain dependencies: home-assistant/core has a file its own
    # .gitattributes renormalises, which would otherwise block every checkout.
    # Forks are never forced, so local edits survive.
    if [ "${FORKED_UPSTREAM}" == "" ] || [ "${FORKED_LABEL}" == "" ]; then
      git -c advice.detachedHead=false checkout -f "${CHECKOUT_LABEL}"
      # A branch pin fast-forwards to origin, failing if it has diverged.
      if git show-ref -q --verify "refs/heads/${CHECKOUT_LABEL}" && git show-ref -q --verify "refs/remotes/origin/${CHECKOUT_LABEL}" && ! git merge --ff-only "origin/${CHECKOUT_LABEL}"; then
        echo "" && echo "Module repository [${REPO_LABEL}] branch [${CHECKOUT_LABEL}] has diverged from [origin/${CHECKOUT_LABEL}], reconcile by hand in [${REPO_DIR}]" && echo ""
        return 1
      fi
    fi
    if ! at_checkout_label "${CHECKOUT_LABEL}"; then
      echo "" && echo "Module repository [${REPO_LABEL}] failed to checkout [${CHECKOUT_LABEL}]" && echo ""
      return 1
    else
      git status
      echo -n "Module repository [${REPO_LABEL}] is being verified at [${REPO_DIR}] ... "
      # The pin is verified by now: a tag is its own version, a ggear* patch
      # branch reports the tag it is based on, any other branch is tracked.
      if ! git show-ref -q --verify "refs/heads/${CHECKOUT_LABEL}"; then
        TAG_CHECKED_OUT="${CHECKOUT_LABEL}"
      elif [[ "${CHECKOUT_LABEL}" == ggear* ]]; then
        TAG_CHECKED_OUT="$(git describe --tags --abbrev=0)"
      else
        BRANCH_PINNED="True"
      fi
      # Tag family prefix: the chars before the first digit (v1.2.3->"v",
      # 2.4.0->"", Z-Stack_3.x.0_...->"Z-Stack_"), keeping powercalc's v* tags
      # off its "measure-v*" ones. Interpolated unescaped, so must stay regex-safe.
      TAG_PREFIX="$(printf '%s' "${TAG_CHECKED_OUT}" | sed -E 's/[0-9].*$//')"
      # In-family tags in push order, prereleases stripped, carrying no word the
      # pinned tag lacks: splits z-stack coordinator from router, still admits
      # 1.0.6 after 1.0.5-fix.
      TAG_FAMILY="$(git tag --sort=creatordate | grep -E "^${TAG_PREFIX}[0-9]" | grep -iv dev | grep -iv beta | grep -v stable | grep -iv rc | grep -iv a0 | grep -iv 0a | grep -iv b0 | grep -iv b1 | grep -iv b2 | grep -iv 0b | grep -iv ts |
        awk -v prefix="${TAG_PREFIX}" -v words=" $(printf '%s' "${TAG_CHECKED_OUT#"${TAG_PREFIX}"}" | grep -oE '[A-Za-z]+' | tr '\n' ' ')" '{
          rest = substr($0, length(prefix) + 1); keep = 1
          while (match(rest, /[A-Za-z]+/)) { if (index(words, " " substr(rest, RSTART, RLENGTH) " ") == 0) keep = 0; rest = substr(rest, RSTART + RLENGTH) }
          if (keep) print
        }')"
      # Releases API excludes prereleases more reliably than the grep chain below.
      if [ "${IGNORE_PRERELEASE}" == "True" ]; then
        TAG_MOST_RECENT="$(gh api "repos/${GITHUB_REPO}/releases" --paginate --jq '.[] | select(.prerelease | not) | .tag_name' 2>/dev/null | sort -V | tail -n 1)"
      fi
      # Newest by push order; the version-sorted recompute below corrects it.
      [[ "${TAG_MOST_RECENT}" == "" ]] && TAG_MOST_RECENT="$(printf '%s\n' "${TAG_FAMILY}" | tail -n 1)"
      # A pinned tag with no surviving candidate can't be classified; fail rather
      # than claim it is up to date. Branch pins are exempt.
      if [[ "${TAG_MOST_RECENT}" == "" ]] && [[ "${TAG_CHECKED_OUT}" != "" ]] && [[ "${FORKED_LABEL}" != "main" && "${FORKED_LABEL}" != "master" ]]; then
        echo "" && echo "Module repository [${REPO_LABEL}] has no candidate version at tag [${TAG_CHECKED_OUT}] prefix [${TAG_PREFIX}] filtered out entirely" && echo ""
        return 1
      fi
      [[ "${TAG_MOST_RECENT}" == "" ]] && TAG_MOST_RECENT="${TAG_CHECKED_OUT}"
      # If the pinned tag out-sorts the push-order pick, trust version order.
      if [ "${IGNORE_PRERELEASE}" != "True" ] && [ "$(printf "%s\n%s" "${TAG_MOST_RECENT#v}" "${TAG_CHECKED_OUT#v}" | sort -V | head -n1)" != "${TAG_CHECKED_OUT#v}" ]; then
        TAG_MOST_RECENT="$(printf '%s\n' "${TAG_FAMILY}" | sort -V | tail -n 1)"
      fi
      if [ "${BRANCH_PINNED}" == "True" ]; then
        echo "tracking branch [${CHECKOUT_LABEL}] at [$(git rev-parse --short HEAD)]"
        echo "Module [${REPO_LABEL}] [INFO] is up to date with branch [origin/${CHECKOUT_LABEL}]"
      elif [[ "${FORKED_LABEL}" == "main" || "${FORKED_LABEL}" == "master" ]]; then
        echo "tracking branch [${FORKED_LABEL}] at [${TAG_CHECKED_OUT}]"
        echo "Module [${REPO_LABEL}] [INFO] is up to date with version [${FORKED_LABEL}]"
      else
        echo "current tag [${TAG_CHECKED_OUT}] and upstream [${TAG_MOST_RECENT}]"
        [[ "${TAG_CHECKED_OUT}" == "${TAG_MOST_RECENT}" ]] && echo "Module [${REPO_LABEL}] [INFO] is up to date with version [${TAG_CHECKED_OUT}]"
        [[ "${TAG_CHECKED_OUT}" != "${TAG_MOST_RECENT}" ]] && echo "Module [${REPO_LABEL}] [WARN] requires update from version [${TAG_CHECKED_OUT}] to [${TAG_MOST_RECENT}]"
      fi
    fi
  fi
  # Callers copy straight from the work tree, so every run must end at the pin,
  # with a fork still carrying its patches.
  cd "${INVOKING_DIR}/../../../.deps/${MODULE_NAME}/${REPO_NAME}" || return 1
  if ! at_checkout_label "${CHECKOUT_LABEL}"; then
    echo "" && echo "Module repository [${MODULE_NAME}/${REPO_NAME}] is not at pinned [${CHECKOUT_LABEL}] in [$(pwd)]" && echo ""
    return 1
  fi
  if [ "${FORKED_UPSTREAM}" != "" ] && [ "${FORKED_LABEL}" != "" ]; then
    UPSTREAM_REF="${FORKED_LABEL}"
    git rev-parse -q --verify "refs/remotes/upstream/${FORKED_LABEL}" >/dev/null && UPSTREAM_REF="upstream/${FORKED_LABEL}"
    # A pinned upstream tag must already be merged; a tracked upstream branch
    # may run ahead of the last pull.
    if [ "${UPSTREAM_REF}" == "${FORKED_LABEL}" ] && ! git rev-parse -q --verify "${FORKED_LABEL}^{commit}" >/dev/null; then
      echo "" && echo "Module repository [${MODULE_NAME}/${REPO_NAME}] pinned upstream [${FORKED_LABEL}] is not fetched, run with pull" && echo ""
      return 1
    fi
    if [ "${UPSTREAM_REF}" == "${FORKED_LABEL}" ] && ! git merge-base --is-ancestor "${FORKED_LABEL}" HEAD; then
      echo "" && echo "Module repository [${MODULE_NAME}/${REPO_NAME}] branch [${CHECKOUT_LABEL}] has not merged pinned upstream [${FORKED_LABEL}], run with pull" && echo ""
      return 1
    fi
    if ! PATCH_COUNT="$(git rev-list --no-merges --count "${UPSTREAM_REF}..HEAD" 2>/dev/null)" || [ "${PATCH_COUNT}" -eq 0 ]; then
      echo "" && echo "Module repository [${MODULE_NAME}/${REPO_NAME}] branch [${CHECKOUT_LABEL}] carries no patches beyond [${UPSTREAM_REF}]" && echo ""
      return 1
    fi
    echo "Module repository [${MODULE_NAME}/${REPO_NAME}] branch [${CHECKOUT_LABEL}] carries [${PATCH_COUNT}] patches beyond [${UPSTREAM_REF}]"
  fi
  cd "${INVOKING_DIR}" || return 1
}

# test_pull_repo: run with "./generate.sh test". Drives pull_repo against
# throwaway local repos in a temp dir; nothing touches GitHub or .deps.
function test_pull_repo() {
  (
    T="$(mktemp -d)"
    trap 'rm -rf "${T}"' EXIT
    FAILED=0
    export GIT_CONFIG_GLOBAL=/dev/null GIT_AUTHOR_NAME=test GIT_AUTHOR_EMAIL=test@test GIT_COMMITTER_NAME=test GIT_COMMITTER_EMAIL=test@test
    git() {
      case "${1} ${2}" in
      "remote set-url") return 0 ;;
      "clone "*) command git clone -q "${T}/${2##*/}" "${3}" ;;
      *) command git "$@" ;;
      esac
    }
    sleep() { :; }
    commit() {
      printf '%b' "${3}" >"${T}/${1}/${2}" && command git -C "${T}/${1}" add -A && command git -C "${T}/${1}" commit -qm "${4}"
    }
    expect() {
      local DESCRIPTION="${1}" EXPECTED_RC="${2}" EXPECTED_LOG="${3}" RC
      shift 3
      pull_repo "${T}/a/b/mod" "$@" >"${T}/log" 2>&1
      RC=$?
      if [ "${RC}" -eq "${EXPECTED_RC}" ] && grep -qE "${EXPECTED_LOG}" "${T}/log"; then
        echo "Test [PASS] ${DESCRIPTION}"
      else
        echo "Test [FAIL] ${DESCRIPTION} rc [${RC}] expected [${EXPECTED_RC}] log [${EXPECTED_LOG}]" && tail -n 15 "${T}/log" | sed 's/^/    /'
        FAILED=1
      fi
    }
    check() {
      local DESCRIPTION="${1}"
      shift
      if "$@"; then echo "Test [PASS] ${DESCRIPTION}"; else echo "Test [FAIL] ${DESCRIPTION}" && FAILED=1; fi
    }
    fork() { expect "${1}" "${2}" "${3}" "${4}" m fork test/origin ggear-x "${T}/upstream.git" "${5}"; }
    plain() { expect "${1}" "${2}" "${3}" "${4}" m plain test/upstream "${5}"; }
    # shellcheck disable=SC2329
    same() { [ "$(command git -C "${1}" rev-parse "${2}")" == "$(command git -C "${3}" rev-parse "${4}")" ]; }
    F="${T}/.deps/m/fork"
    P="${T}/.deps/m/plain"

    # Upstream with tags v1, v2; our fork carries one patch on ggear-x off v1.
    mkdir -p "${T}/a/b/mod" && command git init -q -b master "${T}/up" && commit up f.txt 'a\n' up1 && command git -C "${T}/up" tag v1
    command git clone -q --bare "${T}/up" "${T}/upstream.git" && command git clone -q --bare "${T}/up" "${T}/origin.git"
    command git clone -q "${T}/origin.git" "${T}/other" && command git -C "${T}/other" checkout -qb ggear-x v1
    commit other patch.txt 'patch\n' PATCH && command git -C "${T}/other" push -q origin ggear-x
    commit up f.txt 'b\n' up2 && command git -C "${T}/up" tag v2 && command git -C "${T}/up" push -q "${T}/upstream.git" master --tags

    fork "fresh clone checks out the patch branch" 0 'carries \[1\] patches beyond \[v2\]' True v2
    command git -C "${F}" config user.name test
    fork "pull merges the pinned upstream tag, keeping the patches" 0 'carries \[1\] patches beyond \[v2\]' True v2
    check "merge is pushed to origin" same "${T}/origin.git" ggear-x "${F}" ggear-x
    check "fork default branch is fast-forwarded to upstream" same "${T}/origin.git" master "${T}/upstream.git" master

    command git -C "${T}/other" pull -q origin ggear-x && commit other p2.txt 'p2\n' P2 && command git -C "${T}/other" push -q origin ggear-x
    fork "patches pushed from another clone are merged, never overwritten" 0 'carries \[2\] patches' True v2

    command git -C "${T}/other" pull -q origin ggear-x && commit other README.md 'Title\n=======\nmine\n' P3 && command git -C "${T}/other" push -q origin ggear-x
    commit up README.md 'Title\n=======\ntheirs\n' up3 && command git -C "${T}/up" tag v3 && command git -C "${T}/up" push -q "${T}/upstream.git" master --tags
    fork "a conflicting upstream merge is left in progress and fails" 1 'conflicts, left in progress' True v3
    fork "a rerun with conflict markers still present fails" 1 'still has conflict markers' "" v3
    printf 'Title\n=======\nmerged\n' >"${F}/README.md"
    fork "an edited conflict is concluded; a ======= heading is no marker" 0 'concluded hand-resolved merge' True v3
    check "concluded merge is pushed to origin" same "${T}/origin.git" ggear-x "${F}" ggear-x

    PRE_MERGE="$(command git -C "${F}" rev-parse 'ggear-x^1')"
    command git -C "${F}" reset -q --hard "${PRE_MERGE}" && command git -C "${T}/origin.git" update-ref refs/heads/ggear-x "${PRE_MERGE}"
    fork "a conflict resolved before is replayed by rerere" 0 'resolved from recorded resolutions' True v3

    command git -C "${T}/up" commit -q --amend -m up3-rewritten && command git -C "${T}/up" push -qf "${T}/upstream.git" master
    fork "an upstream history rewrite realigns the fork default branch" 0 'realigning fork \[origin/master\]' True v3
    check "realigned default branch matches upstream" same "${T}/origin.git" master "${T}/upstream.git" master

    command git -C "${T}/other" fetch -q origin && command git -C "${T}/other" checkout -q -B master origin/master
    printf 'own\n' >"${T}/other/own.txt" && command git -C "${T}/other" add own.txt && command git -C "${T}/other" commit -qm OWN --author="me <me@me>"
    command git -C "${T}/other" push -q origin master && command git -C "${F}" config user.name me
    commit up z.txt 'z\n' up4 && command git -C "${T}/up" push -q "${T}/upstream.git" master
    fork "a default branch holding our own commit is never realigned" 0 'holds our commits' True v3
    command git -C "${F}" config user.name test

    command git -C "${F}" checkout -q master
    fork "a repo left on another branch is switched back" 0 'carries \[3\] patches' "" v3
    command git -C "${F}" checkout -q master && printf 'edit\n' >>"${F}/f.txt"
    fork "local edits blocking the switch fail" 1 'cannot check out pinned \[ggear-x\]' "" v3
    command git -C "${F}" checkout -q -- f.txt && command git -C "${F}" checkout -q ggear-x
    printf 'wip\n' >>"${F}/patch.txt"
    fork "uncommitted work on the patch branch survives a pull" 0 'carries' True v3
    check "uncommitted work is still there" grep -q wip "${F}/patch.txt"
    command git -C "${F}" checkout -q -- patch.txt

    command git -C "${T}/up" tag v4 && command git -C "${T}/up" push -q "${T}/upstream.git" --tags
    fork "a fork pin bumped to an unfetched upstream tag fails without pull" 1 'pinned upstream \[v4\] is not fetched' "" v4
    command git -C "${F}" fetch -q upstream --tags
    fork "a fork pin bumped to an unmerged upstream tag fails without pull" 1 'has not merged pinned upstream \[v4\]' "" v4

    plain "a fresh clone of a missing pin fails" 1 'cannot check out pinned \[9.9.9\]' "" 9.9.9
    rm -rf "${P}"
    plain "a fresh clone checks out the pinned tag" 0 '' "" v2
    command git -C "${P}" checkout -q master
    plain "a repo left on another branch is moved back to its pin" 0 '' "" v2
    check "repo is at the pinned tag" same "${P}" HEAD "${P}" 'v2^{commit}'
    printf 'built\n' >"${T}/built.js" && mkdir -p "${T}/out/card" && printf 'good\n' >"${T}/out/card/card.js"
    : >"${T}/empty.js" && replace_path "${T}/empty.js" "${T}/out/card/card.js" 2>/dev/null
    check "replace_path refuses an empty source, keeping the output" grep -q good "${T}/out/card/card.js"
    replace_path "${T}/built.js" "${T}/out/card/card.js" >/dev/null
    check "replace_path replaces the output from a good source" grep -q built "${T}/out/card/card.js"
    mkdir -p "${T}/src/dir" && printf 'new\n' >"${T}/src/dir/new.txt" && mkdir -p "${T}/out/dir" && printf 'stale\n' >"${T}/out/dir/stale.txt"
    replace_path "${T}/src/dir" "${T}/out/dir" >/dev/null
    check "replace_path replaces a directory whole, dropping stale files" [ -f "${T}/out/dir/new.txt" ] && [ ! -f "${T}/out/dir/stale.txt" ]
    plain "a newer upstream tag is reported" 0 'requires update from version \[v2\] to \[v4\]' True v2
    check "no pull_repo variable leaks to the caller" [ -z "${CHECKOUT_LABEL+x}${UPSTREAM_REF+x}${TAG_MOST_RECENT+x}" ]

    plain "a branch pin checks out" 0 '' "" master
    commit up y.txt 'y\n' up5 && command git -C "${T}/up" push -q "${T}/upstream.git" master
    plain "a branch pin fast-forwards to origin" 0 'up to date with branch \[origin/master\]' True master
    check "branch pin is at origin" same "${P}" HEAD "${P}" origin/master
    commit .deps/m/plain local.txt 'local\n' LOCAL && commit up x.txt 'x\n' up6 && command git -C "${T}/up" push -q "${T}/upstream.git" master
    plain "a branch pin diverged from origin fails" 1 'has diverged from \[origin/master\]' True master
    command git -C "${P}" reset -q --hard origin/master

    command git -C "${T}/up" tag Z_1.x_coordinator_1 && command git -C "${T}/up" tag Z_1.x_router_2 && command git -C "${T}/up" push -q "${T}/upstream.git" --tags
    plain "a pin bumped to a tag not yet fetched is fetched first" 0 'is up to date with version \[Z_1.x_coordinator_1\]' True Z_1.x_coordinator_1
    plain "a newer tag from a sibling sub-family is no update" 0 'up to date with version \[Z_1.x_coordinator_1\]' True Z_1.x_coordinator_1

    command git -C "${P}" remote set-url origin "${T}/missing.git"
    plain "a failing fetch gives up after five attempts" 1 'fetch failed \[5\] times' True v2

    [ "${FAILED}" -eq 0 ] && echo "Test [PASS] all" || echo "Test [FAIL] see above"
    exit "${FAILED}"
  )
}

if [ "${BASH_SOURCE[0]}" == "${0}" ] && [ "${1}" == "test" ]; then
  test_pull_repo
  exit $?
fi
