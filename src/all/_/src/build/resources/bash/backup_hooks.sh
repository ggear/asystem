# shellcheck shell=bash
# shellcheck disable=SC2034

backup_fingerprinted() {
  backup_fingerprinted_default "$@"
}

backup_durable() {
  return 0
}
