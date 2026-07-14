#!/usr/bin/env bash
set -u

MIN_FREE_BYTES=$((5 * 1024 * 1024 * 1024))
TEST_NAME='._bench_test_file'
ALLOWED_FSTYPES='ext4 btrfs xfs f2fs'
WRITE_RUNTIME=30
READ_RUNTIME=30
WRITE_SIZE='4G'
READ_MAX_MBPS=1000
READ_MIN_BYTES=$((READ_RUNTIME * READ_MAX_MBPS * 1000000))
READ_MAX_BYTES=$((READ_MIN_BYTES * 2))
READ_FLOOR_BYTES=$((6 * 1000000000))
SET_FILE_MIN=$((500 * 1000000))
READ_POOL=30

PARSER='
import sys, json
d = json.load(sys.stdin)
j = d["jobs"][0][sys.argv[1]]
print("%.1f" % (j["bw"] * 1024 / 1000000.0))
'

cleanup() {
  find /share -name "$TEST_NAME" -delete 2>/dev/null
}
trap cleanup EXIT

color_val() {
  local v=$1 w=$2 c
  if awk -v v="$v" 'BEGIN { exit !(v > 300) }'; then
    c=$'\033[32m'
  elif awk -v v="$v" 'BEGIN { exit !(v >= 100) }'; then
    c=$'\033[33m'
  else
    c=$'\033[31m'
  fi
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

pick_random() {
  local end=$1 record
  record=$(sort -z -n | "$end" -z -n "$READ_POOL" | shuf -z -n 1 | tr -d '\0')
  [ -n "$record" ] || return 1
  printf '%s' "${record#*$'\t'}"
}

select_read_file() {
  local media="$1/media"
  [ -d "$media" ] || return 1
  find "$media" -type f -size +"${READ_MIN_BYTES}c" -size -"${READ_MAX_BYTES}c" -printf '%T@\t%p\0' 2>/dev/null | pick_random head
}

select_read_set() {
  local media="$1/media" need=$2
  [ -d "$media" ] || return 1
  local total=0 count=0 list='' size path esc
  while IFS=$'\t' read -r -d '' size path; do
    esc=${path//:/\\:}
    [ -z "$list" ] && list=$esc || list="$list:$esc"
    total=$((total + size))
    count=$((count + 1))
    [ "$total" -ge "$need" ] && break
  done < <(find "$media" -type f -size +"${SET_FILE_MIN}c" -printf '%s\t%p\0' 2>/dev/null | shuf -z)
  [ "$count" -eq 0 ] && return 1
  printf '%s\t%s\t%s' "$total" "$count" "$list"
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
  [ -n "$col_mbps" ] && set_col "$col" "$(color_val "$col_mbps" 12)" || set_col "$col" '--'
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
    --fsync=1 \
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
    --direct=1 \
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
    printf '                                   ("<mount>","<date>","<time>","<read>","<write>")\n'
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

declare -a results=()

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
  usepct=$(df -P "$mount" 2>/dev/null | awk 'NR==2 { gsub(/%/,"",$5); print $5 }')

  testfile=''
  if [ -n "$do_write" ]; then
    avail=$(df -B1 --output=avail "$mount" 2>/dev/null | tail -1 | tr -d ' ')
    if [ -z "$avail" ] || [ "$avail" -lt "$MIN_FREE_BYTES" ]; then
      note_row "$mount" 'Skipped: less than 5GB free'
      continue
    fi
    tmpdir="$mount/tmp"
    testfile="$tmpdir/$TEST_NAME"
    mkdir -p "$tmpdir" 2>/dev/null || {
      note_row "$mount" "Skipped: cannot create $tmpdir"
      continue
    }
  fi

  if [ -n "$do_read" ]; then
    read_target=$(select_read_file "$mount")
    if [ -n "$read_target" ]; then
      read_bytes=$(stat -c %s "$read_target" 2>/dev/null)
      read_label=$(basename "$read_target")
    else
      set_result=$(select_read_set "$mount" "$READ_MIN_BYTES")
      IFS=$'\t' read -r read_bytes read_count read_target <<<"$set_result"
      if [ -z "$read_bytes" ] || [ "$read_bytes" -lt "$READ_FLOOR_BYTES" ]; then
        note_row "$mount" "Skipped: media totals under $((READ_FLOOR_BYTES / 1000000000)) GB"
        continue
      fi
      read_label="$read_count files ($((read_bytes / 1000000000)) GB)"
    fi
    read_rt=$(awk -v s="$read_bytes" -v c="$READ_MAX_MBPS" -v m="$READ_RUNTIME" 'BEGIN { t = int(s / (c * 1000000)); if (t > m) t = m; if (t < 1) t = 1; print t }')

    drop_caches
    run_col read "$read_rt" run_read "$read_target" "$read_rt"
    rmbps=$col_mbps
    if [ -n "$rmbps" ] && [ -n "$read_bytes" ] && read_looped "$rmbps" "$read_rt" "$read_bytes"; then
      read_rt=$(awk -v s="$read_bytes" -v r="$rmbps" 'BEGIN { t = int(s / (r * 1000000) * 0.9); if (t < 1) t = 1; print t }')
      drop_caches
      run_col read "$read_rt" run_read "$read_target" "$read_rt"
      rmbps=$col_mbps
      if [ -n "$rmbps" ] && read_looped "$rmbps" "$read_rt" "$read_bytes"; then
        note_row "$mount" "Failed: read still looped $((read_bytes / 1000000000)) GB at ${read_rt}s"
        continue
      fi
    fi
    if [ -z "$rmbps" ]; then
      note_row "$mount" 'Failed: read produced no parseable output'
      continue
    fi
    [ "$read_rt" -lt "$READ_RUNTIME" ] && read_extra=" (read ${read_rt}s)"
  fi

  if [ -n "$do_write" ]; then
    run_col write "$WRITE_RUNTIME" run_write "$testfile"
    wmbps=$col_mbps
    rm -f "$testfile"
    if [ -z "$wmbps" ]; then
      note_row "$mount" 'Failed: write produced no parseable output'
      continue
    fi
  fi

  [ -n "$usepct" ] && rnote="Used: ${usepct}%"
  if [ -n "$do_read" ]; then
    [ -n "$rnote" ] && rnote="$rnote | "
    rnote="${rnote}Read: $read_label$read_extra"
  fi
  if [ -n "$do_write" ]; then
    [ -n "$rnote" ] && rnote="$rnote | "
    rnote="${rnote}Write: 1 file (${WRITE_SIZE%G} GB)"
  fi
  commit_row
  emit_csv

  results+=("$mount")
done < <(awk '$2 ~ /^\/share\// { print $2, $3 }' /proc/self/mounts | sort -u)

printf '\r\033[K'

if [ "${#results[@]}" -eq 0 ]; then
  printf 'No eligible /share/* mounts were benchmarked\n'
fi
