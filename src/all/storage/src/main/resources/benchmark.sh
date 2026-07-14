#!/usr/bin/env bash
#
# benchmark.sh — measure read/write throughput of every eligible /share/* mount
# and print a colored per-mount MB/s table (optionally CSV). It models the real
# maintenance workload — a share-to-share rsync — as one sequential stream
# (numjobs=1) rather than peak parallel/high-QD throughput, so each number
# reflects what an rsync copy would actually sustain.
#
# Design decisions:
#   - Trim first: on write runs, all shares are `fstrim`-ed in one up-front pass
#     (before the table header), then a short settle lets the SSD's background GC
#     quiesce, so free-block state is consistent and never interleaved with the
#     live table. A read-only run does not trim (it would only mutate free space).
#   - Read and write are independent: a skip/failure in one phase still lets the
#     other run, and each mount commits exactly one row with per-phase notes.
#   - Reads use real media, not a synthetic file: a random set of files under
#     <mount>/media (each > SET_FILE_MIN, and untouched for > RECENT_WRITE_DAYS to
#     skip files still being written) is assembled until it totals READ_MIN_BYTES
#     — enough unique data to sustain the run without re-reading. The pool must
#     hold >= READ_POOL_MIN files or the read is skipped, so reuse across runs
#     stays low; the note shows used/pool counts plus a short md5 fingerprint of
#     the chosen set, making run-to-run variety visible. Caches are dropped and
#     fio reads buffered (--direct=0, --invalidate) — a cold read pipelined by
#     kernel readahead, exactly how rsync reads, not the latency-bound O_DIRECT
#     QD1 that understates USB-bridged drives. A loop guard shrinks the runtime
#     (or fails the read) if a re-read gets served from cache.
#   - Writes use fio O_DIRECT to a temp file (WRITE_SIZE, 4 GiB), removed after,
#     with a single end-of-run fsync (--end_fsync, not per-block) so the number is
#     streaming write bandwidth including the final device-cache flush. A mount is
#     skipped when it has under 5 GiB (MIN_FREE_BYTES) free. Sizes on the write
#     side are GiB (fio's G suffix and the free-space check are both 1024-based).
#   - --csv splits streams (exec 3>&1 1>&2): the live table goes to stderr and
#     machine-readable rows go to fd 3 (stdout), so the two never interleave.
set -u

MIN_FREE_BYTES=$((5 * 1024 * 1024 * 1024))
TEST_NAME='._bench_test_file'
ALLOWED_FSTYPES='ext4 btrfs xfs f2fs'
WRITE_RUNTIME=30
READ_RUNTIME=30
WRITE_SIZE='4G'
READ_MAX_MBPS=1000
READ_MIN_BYTES=$((READ_RUNTIME * READ_MAX_MBPS * 1000000))
READ_FLOOR_BYTES=$((6 * 1000000000))
SET_FILE_MIN=$((500 * 1000000))
READ_POOL_MIN=50
RECENT_WRITE_DAYS=5
TRIM_SETTLE=5

PARSER='
import sys, json
d = json.load(sys.stdin)
j = d["jobs"][0][sys.argv[1]]
print("%.1f" % (j["bw"] * 1024 / 1000000.0))
'

cleanup() {
  find /share -name "$TEST_NAME" -delete 2>/dev/null
}

color_val() {
  local v=$1 w=$2 c
  if awk -v v="$v" 'BEGIN { exit !(v > 300) }'; then
    c=$'\033[32m'
  elif awk -v v="$v" 'BEGIN { exit !(v >= 100) }'; then
    c=$'\033[33m'
  else
    c=$'\033[31m'
  fi
  # shellcheck disable=SC2183  # %-*.1f consumes $w as the dynamic field width, so 3 args is correct
  printf '%s%-*.1f\033[0m' "$c" "$w" "$v"
}

note_row() {
  printf '\r\033[K  %-12s %-12s %-12s %s\n' "$1" '' '' "$2"
}

read_looped() {
  awk -v r="$1" -v t="$2" -v s="$3" 'BEGIN { exit !(r * 1000000 * t > s) }'
}

fstype_allowed() {
  local fs=$1 allowed
  for allowed in $ALLOWED_FSTYPES; do
    [ "$fs" = "$allowed" ] && return 0
  done
  return 1
}

drop_caches() {
  sync 2>/dev/null
  if [ -w /proc/sys/vm/drop_caches ]; then
    echo 3 >/proc/sys/vm/drop_caches 2>/dev/null
  elif command -v sudo >/dev/null 2>&1; then
    echo 3 | sudo -n tee /proc/sys/vm/drop_caches >/dev/null 2>&1
  fi
  return 0
}

set_col() {
  if [ "$1" = read ]; then rfield=$2; else wfield=$2; fi
}

draw_row() {
  printf '\r\033[K  %-12s %-12s %-12s %s' "$mount" "$rfield" "$wfield" "$rnote" >&2
}

commit_row() {
  printf '\r\033[K  %-12s %-12s %-12s %s\n' "$mount" "$rfield" "$wfield" "$rnote"
}

emit_csv() {
  [ -n "$CSV" ] || return 0
  printf '"%s","%s","%s","%s","%s","%s"\n' \
    "$mount" "${usepct:-}" "$(date '+%Y/%m/%d')" "$(date '+%H:%M:%S')" "${rmbps:-}" "${wmbps:-}" >&3
}

run_col() {
  local col=$1 secs=$2
  shift 2
  local outfile pid i remaining
  outfile=$(mktemp)
  "$@" >"$outfile" 2>/dev/null &
  pid=$!
  i=0
  while kill -0 "$pid" 2>/dev/null; do
    remaining=$((secs - i))
    [ "$remaining" -lt 0 ] && remaining=0
    set_col "$col" "${remaining}s"
    draw_row
    sleep 1
    i=$((i + 1))
  done
  wait "$pid"
  col_mbps=$(python3 -c "$PARSER" "$col" <"$outfile" 2>/dev/null)
  rm -f "$outfile"
  if [ -n "$col_mbps" ]; then
    set_col "$col" "$(color_val "$col_mbps" 12)"
  else
    set_col "$col" '--'
  fi
  draw_row
}

run_write() {
  fio --name=write \
    --filename="$1" \
    --size="$WRITE_SIZE" \
    --bs=1M \
    --rw=write \
    --numjobs=1 \
    --runtime="$WRITE_RUNTIME" \
    --time_based \
    --direct=1 \
    --end_fsync=1 \
    --output-format=json 2>/dev/null
}

run_read() {
  fio --name=read \
    --filename="$1" \
    --bs=1M \
    --rw=read \
    --numjobs=1 \
    --runtime="${2:-$READ_RUNTIME}" \
    --time_based \
    --file_service_type=sequential \
    --direct=0 \
    --invalidate=1 \
    --output-format=json \
    --readonly 2>/dev/null
}

FILTER=''
EXECUTE=read_write
CSV=''
while [ $# -gt 0 ]; do
  case $1 in
  --filter)
    [ $# -ge 2 ] || { printf 'error: --filter needs a value\n' >&2; exit 1; }
    FILTER=${2%/}
    shift 2
    ;;
  --execute)
    [ $# -ge 2 ] || { printf 'error: --execute needs a value\n' >&2; exit 1; }
    EXECUTE=$2
    shift 2
    ;;
  --csv)
    CSV=1
    shift
    ;;
  -h | --help)
    printf 'usage: benchmark.sh [--filter <share>] [--execute read|write|read_write] [--csv]\n'
    printf '\n'
    printf 'Benchmark sequential read/write throughput of every eligible /share/* mount\n'
    printf 'and print a per-mount table of MB/s.\n'
    printf '\n'
    printf 'Options:\n'
    printf '  --filter <share>                 Benchmark only this mount (e.g. /share/media).\n'
    printf '  --execute read|write|read_write  Which passes to run (default: read_write).\n'
    printf '  --csv                            Emit machine-readable CSV rows on stdout\n'
    printf '                                   ("<mount>","<used%%>","<date>","<time>","<read>","<write>")\n'
    printf '                                   while the table is printed on stderr.\n'
    printf '  -h, --help                       Show this help and exit.\n'
    exit 0
    ;;
  *)
    printf 'error: unknown argument: %s\n' "$1" >&2
    exit 1
    ;;
  esac
done

case $EXECUTE in
read) do_read=1; do_write='' ;;
write) do_read=''; do_write=1 ;;
read_write) do_read=1; do_write=1 ;;
*)
  printf 'error: --execute must be read, write, or read_write\n' >&2
  exit 1
  ;;
esac

if ! command -v fio >/dev/null 2>&1; then
  printf 'error: fio is not installed\n' >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  printf 'error: python3 is not installed\n' >&2
  exit 1
fi

if [ -n "$CSV" ]; then
  exec 3>&1 1>&2
fi

trap cleanup EXIT

declare -a results=()

if [ -n "$do_write" ]; then
  trimmed=''
  while read -r mount fstype; do
    [ -z "$mount" ] && continue
    [ -n "$FILTER" ] && [ "$mount" != "$FILTER" ] && continue
    fstype_allowed "$fstype" || continue
    fstrim -v "$mount" 2>/dev/null && trimmed=1
  done < <(awk '$2 ~ /^\/share\// { print $2, $3 }' /proc/self/mounts | sort -u)
  [ -n "$trimmed" ] && sleep "$TRIM_SETTLE"
fi

printf '  %-12s %-12s %-12s %s\n' 'Mount' 'Read (MB/s)' 'Write (MB/s)' 'Notes'

while read -r mount fstype; do
  [ -z "$mount" ] && continue
  [ -n "$FILTER" ] && [ "$mount" != "$FILTER" ] && continue
  fstype_allowed "$fstype" || continue
  rfield=''
  wfield=''
  rnote=''
  rmbps=''
  wmbps=''
  read_extra=''
  read_note=''
  write_note=''
  usepct=$(df -P "$mount" 2>/dev/null | awk 'NR==2 { gsub(/%/,"",$5); print $5 }')

  if [ -n "$do_read" ]; then
    media="$mount/media"
    pool_count=0
    read_bytes=0
    read_count=0
    read_target=''
    if [ -d "$media" ]; then
      entries=()
      while IFS= read -r -d '' entry; do
        entries+=("$entry")
      done < <(find "$media" -type f -size +"${SET_FILE_MIN}c" -mtime +"$RECENT_WRITE_DAYS" -printf '%s\t%p\0' 2>/dev/null | shuf -z)
      pool_count=${#entries[@]}
      for entry in "${entries[@]}"; do
        size=${entry%%$'\t'*}
        path=${entry#*$'\t'}
        esc=${path//:/\\:}
        [ -z "$read_target" ] && read_target=$esc || read_target="$read_target:$esc"
        read_bytes=$((read_bytes + size))
        read_count=$((read_count + 1))
        [ "$read_bytes" -ge "$READ_MIN_BYTES" ] && break
      done
    fi
    if [ "$pool_count" -lt "$READ_POOL_MIN" ]; then
      rfield='--'
      read_note="Read: skipped (pool $pool_count < $READ_POOL_MIN files)"
    elif [ "$read_bytes" -lt "$READ_FLOOR_BYTES" ]; then
      rfield='--'
      read_note="Read: skipped (<$((READ_FLOOR_BYTES / 1000000000)) GB media)"
    else
      read_hash=$(printf '%s' "$read_target" | md5sum 2>/dev/null | cut -c1-6)
      read_label="$read_count/$pool_count files ($((read_bytes / 1000000000)) GB) #$read_hash"
      read_rt=$(awk -v s="$read_bytes" -v c="$READ_MAX_MBPS" -v m="$READ_RUNTIME" 'BEGIN { t = int(s / (c * 1000000)); if (t > m) t = m; if (t < 1) t = 1; print t }')
      drop_caches
      run_col read "$read_rt" run_read "$read_target" "$read_rt"
      rmbps=$col_mbps
      looped=''
      if [ -n "$rmbps" ] && read_looped "$rmbps" "$read_rt" "$read_bytes"; then
        read_rt=$(awk -v s="$read_bytes" -v r="$rmbps" 'BEGIN { t = int(s / (r * 1000000) * 0.9); if (t < 1) t = 1; print t }')
        drop_caches
        run_col read "$read_rt" run_read "$read_target" "$read_rt"
        rmbps=$col_mbps
        if [ -n "$rmbps" ] && read_looped "$rmbps" "$read_rt" "$read_bytes"; then
          looped=1
        fi
      fi
      if [ -n "$looped" ]; then
        rfield='--'
        rmbps=''
        read_note="Read: failed (looped $((read_bytes / 1000000000)) GB at ${read_rt}s)"
      elif [ -z "$rmbps" ]; then
        rfield='--'
        read_note='Read: failed (no parseable output)'
      else
        [ "$read_rt" -lt "$READ_RUNTIME" ] && read_extra=" (read ${read_rt}s)"
        read_note="Read: $read_label$read_extra"
      fi
    fi
  fi

  if [ -n "$do_write" ]; then
    avail=$(df -B1 --output=avail "$mount" 2>/dev/null | tail -1 | tr -d ' ')
    if [ -z "$avail" ] || [ "$avail" -lt "$MIN_FREE_BYTES" ]; then
      wfield='--'
      write_note="Write: skipped (<$((MIN_FREE_BYTES / 1024 / 1024 / 1024)) GiB free)"
    elif ! mkdir -p "$mount/tmp" 2>/dev/null; then
      wfield='--'
      write_note="Write: skipped (cannot create $mount/tmp)"
    else
      testfile="$mount/tmp/$TEST_NAME"
      run_col write "$WRITE_RUNTIME" run_write "$testfile"
      wmbps=$col_mbps
      rm -f "$testfile"
      if [ -z "$wmbps" ]; then
        wfield='--'
        write_note='Write: failed (no parseable output)'
      else
        write_note="Write: 01 file (${WRITE_SIZE%G} GiB)"
      fi
    fi
  fi

  [ -n "$usepct" ] && rnote="Used: ${usepct}%"
  if [ -n "$read_note" ]; then
    [ -n "$rnote" ] && rnote="$rnote | "
    rnote="${rnote}${read_note}"
  fi
  if [ -n "$write_note" ]; then
    [ -n "$rnote" ] && rnote="$rnote | "
    rnote="${rnote}${write_note}"
  fi
  commit_row
  emit_csv

  results+=("$mount")
done < <(awk '$2 ~ /^\/share\// { print $2, $3 }' /proc/self/mounts | sort -u)

printf '\r\033[K'

if [ "${#results[@]}" -eq 0 ]; then
  printf 'No eligible /share/* mounts were benchmarked\n'
fi
