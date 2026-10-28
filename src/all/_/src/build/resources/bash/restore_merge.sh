# shellcheck shell=bash
# shellcheck disable=SC2034

RESTORE_LIVE_ADDRESS=""
RESTORE_PLANNED=()

restore_stamped() {
  restore_report "$(date +%T) $*" >&2
}

restore_ticked() {
  local done="${1}" total="${2}" started="${3}" elapsed percent rate eta rows bytes mibs load
  elapsed=$((SECONDS - started))
  percent=$((total > 0 ? done * 100 / total : 100))
  rate=0
  eta="-"
  if [ "${elapsed}" -gt 0 ] && [ "${done}" -gt 0 ]; then
    rate=$((done * 60 / elapsed))
    eta="$(((total - done) * elapsed / done / 60))m"
  fi
  read -r rows bytes < <(awk '{ rows += $1; bytes += $2 } END { print rows + 0, bytes + 0 }' "${RESTORE_STATS_FILE:-/dev/null}" 2>/dev/null)
  mibs=0
  [ "${elapsed}" -gt 0 ] && mibs=$((${bytes:-0} / 1048576 / elapsed))
  load="$(cut -d' ' -f1 /proc/loadavg 2>/dev/null || echo -)"
  restore_stamped "merged [${done}] of [${total}] units [${percent}]%, [${rows:-0}] rows, [$(awk -v b="${bytes:-0}" 'BEGIN { printf "%.2f", b / 1073741824 }')] GiB at [${mibs}] MiB/s, [${rate}] units a minute, [$((elapsed / 60))m$((elapsed % 60))s] elapsed, about [${eta}] left, load [${load}]"
}

restore_planned_units() {
  local staged="${1}" live="${2}" line unit count
  declare -A held=()
  while read -r line; do
    [ -n "${line}" ] && held["${line% *}"]="${line##* }"
  done <<<"${live}"
  while read -r line; do
    [ -n "${line}" ] || continue
    unit="${line% *}"
    count="${line##* }"
    [ "${held["${unit}"]:-}" = "${count}" ] || echo "${unit}"
  done <<<"${staged}"
}

restore_merged_progress() {
  printf '%s\n' "$(dirname "$(restore_scratch_dir)")/${RESTORE_RUN_TIMESTAMP}.merged"
}

restore_merge() {
  local staged live after unit planned progress scratch
  if ! declare -F restore_merged >/dev/null; then
    restore_fault "module [${RESTORE_MODULE_NAME}] defines no restore_merged, merge is not offered"
    return 1
  fi
  restore_stamped "staging [${#RESTORE_CHAIN_FILES[@]}] artifact(s) into scratch"
  scratch="$(restore_staged)" || {
    restore_fault "could not stage [${RESTORE_RUN_TIMESTAMP}] into scratch"
    return 1
  }
  RESTORE_SCRATCH="${scratch}"
  restore_stamped "scratch staged, fingerprinting it"
  staged="$(backup_fingerprinted "${scratch}")"
  restore_stamped "sealing scratch read only"
  restore_sealed "${scratch}" || {
    restore_fault "could not seal scratch [${scratch}] read only"
    restore_teardown "${scratch}"
    return 1
  }
  restore_stamped "fingerprinting live"
  live="$(backup_fingerprinted "${RESTORE_LIVE_ADDRESS}")"
  mapfile -t RESTORE_PLANNED < <(restore_planned_units "${staged}" "${live}")
  restore_report "merge     [${#RESTORE_PLANNED[@]}] closed unit(s) differ from live"
  for unit in "${RESTORE_PLANNED[@]:0:20}"; do
    restore_report "plan      [${unit}]"
  done
  [ "${#RESTORE_PLANNED[@]}" -gt 20 ] && restore_report "plan      and [$((${#RESTORE_PLANNED[@]} - 20))] more"
  if [ "${RESTORE_FORCE}" != "true" ]; then
    [ "${RESTORE_KEEP_SCRATCH}" = "true" ] || restore_teardown "${scratch}"
    return 0
  fi
  restore_backed || return 1
  progress="$(restore_merged_progress)"
  mkdir -p "$(dirname "${progress}")"
  touch "${progress}"
  local jobs="${RESTORE_MERGE_JOBS:-3}" running=0 failures total="${#RESTORE_PLANNED[@]}" started="${SECONDS}" last="${SECONDS}" every="${RESTORE_PROGRESS_SECONDS:-30}"
  failures="${progress}.failed"
  RESTORE_STATS_FILE="${progress}.stats"
  export RESTORE_STATS_FILE
  rm -f "${failures}" "${RESTORE_STATS_FILE}"
  restore_stamped "merging [${total}] unit(s) with [${jobs}] job(s), progress is recorded in [${progress}]"
  for unit in "${RESTORE_PLANNED[@]}"; do
    grep -Fxq -- "${unit}" "${progress}" && continue
    if [ "${jobs}" -le 1 ]; then
      restore_merged "${unit}" "${scratch}" || {
        restore_fault "could not merge [${unit}]"
        return 1
      }
      echo "${unit}" >>"${progress}"
      RESTORE_CHANGED=$((RESTORE_CHANGED + 1))
    else
      (restore_merged "${unit}" "${scratch}" && echo "${unit}" >>"${progress}" || echo "${unit}" >>"${failures}") &
      running=$((running + 1))
      if [ "${running}" -ge "${jobs}" ]; then
        wait -n || true
        running=$((running - 1))
      fi
    fi
    if [ $((SECONDS - last)) -ge "${every}" ]; then
      restore_ticked "$(grep -c . "${progress}")" "${total}" "${started}"
      last="${SECONDS}"
    fi
  done
  while [ "$(jobs -rp | wc -l)" -gt 0 ]; do
    sleep 1
    if [ $((SECONDS - last)) -ge "${every}" ]; then
      restore_ticked "$(grep -c . "${progress}")" "${total}" "${started}"
      last="${SECONDS}"
    fi
  done
  wait || true
  restore_ticked "$(grep -c . "${progress}")" "${total}" "${started}"
  if [ -s "${failures}" ]; then
    while read -r unit; do
      restore_fault "could not merge [${unit}]"
    done <"${failures}"
    return 1
  fi
  [ "${jobs}" -gt 1 ] && RESTORE_CHANGED=$((RESTORE_CHANGED + $(grep -c . "${progress}")))
  restore_stamped "merge written, restarting [${RESTORE_LIVE_ADDRESS}] and waiting for its counts to settle"
  restore_restarted
  declare -A held=() want=()
  while read -r line; do
    [ -n "${line}" ] && want["${line% *}"]="${line##* }"
  done <<<"${staged}"
  local attempt=0 short=0 shorts=()
  while true; do
    after="$(backup_fingerprinted "${RESTORE_LIVE_ADDRESS}")"
    held=()
    while read -r line; do
      [ -n "${line}" ] && held["${line% *}"]="${line##* }"
    done <<<"${after}"
    shorts=()
    for unit in "${RESTORE_PLANNED[@]}"; do
      [ "${held["${unit}"]:-0}" -ge "${want["${unit}"]:-0}" ] || shorts+=("${unit}")
    done
    [ "${#shorts[@]}" -eq 0 ] && break
    restore_stamped "verifying, attempt [$((attempt + 1))] of [${RESTORE_VERIFY_ATTEMPTS:-24}], [${#shorts[@]}] unit(s) still short"
    attempt=$((attempt + 1))
    [ "${attempt}" -lt "${RESTORE_VERIFY_ATTEMPTS:-24}" ] || break
    sleep "${RESTORE_VERIFY_SLEEP:-5}"
  done
  [ "${#shorts[@]}" -eq 0 ] && restore_stamped "verified, every merged unit holds at least the backup's count"
  for unit in "${shorts[@]}"; do
    restore_fault "unit [${unit}] holds [${held["${unit}"]:-0}] after the merge, wants at least [${want["${unit}"]}]"
    short=$((short + 1))
  done
  [ "${short}" -eq 0 ] && rm -f "${progress}" "${failures}" "${RESTORE_STATS_FILE}"
  [ "${RESTORE_KEEP_SCRATCH}" = "true" ] || restore_teardown "${scratch}"
  return "$((short > 0))"
}

restore_restarted() {
  docker restart "${RESTORE_MODULE_NAME}" >/dev/null 2>&1 || true
}
