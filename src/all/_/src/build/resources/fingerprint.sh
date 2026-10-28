# shellcheck shell=bash
# shellcheck disable=SC2034

BACKUP_FINGERPRINT_INCLUDES=()

backup_fingerprinted_default() {
  local file="${1:-}" includes
  includes="$(
    IFS=:
    echo "${BACKUP_FINGERPRINT_INCLUDES[*]}"
  )"
  case "${file}" in
  *.sql.gz)
    gzip -dc "${file}" | awk '
      /^\\connect / { db = $2; gsub(/["]/, "", db); next }
      /^-- Current Database: / { mdb = $4; gsub(/[`]/, "", mdb); next }
      /^COPY / { unit = db "." $2; incopy = 1; rows[unit] += 0; order[unit] = 1; next }
      /^\\\.$/ { incopy = 0; next }
      incopy { rows[unit]++; next }
      mdb != "" { bytes[mdb] += length($0) + 1 }
      END {
        for (unit in rows) print unit, rows[unit]
        for (unit in bytes) print unit, bytes[unit]
      }' | sort
    ;;
  *.tar.gz)
    tar -tvzf "${file}" | awk -v includes="${includes}" '
      BEGIN { count = split(includes, wanted, ":") }
      {
        gnu = ($2 ~ /\//)
        size = gnu ? $3 : $5
        skip = gnu ? 5 : 8
        name = $0
        sub(/^ +/, "", name)
        for (field = 0; field < skip; field++) sub(/^[^ ]+ +/, "", name)
        sub(/ -> .*$/, "", name)
        sub(/^\.\//, "", name)
        if (substr($1, 1, 1) == "d" || name == "") next
        unit = ""
        for (index_ = 1; index_ <= count; index_++) {
          if (wanted[index_] != "" && (name == wanted[index_] || index(name, wanted[index_] "/") == 1)) { unit = wanted[index_]; break }
        }
        if (unit == "") { unit = name; sub(/\/.*$/, "", unit) }
        bytes[unit] += size
      }
      END { for (unit in bytes) print unit, bytes[unit] }' | sort
    ;;
  *.zip)
    unzip -l "${file}" | awk '
      NR > 3 && $1 ~ /^[0-9]+$/ && $4 != "" {
        name = $0
        sub(/^ *[0-9]+ +[^ ]+ +[^ ]+ +/, "", name)
        bytes[name] += $1
      }
      END { for (unit in bytes) print unit, bytes[unit] }' | sort
    ;;
  esac
}
