#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Error-case fixture: source data is not processable, derive expected errors from the case name
refresh_error_case
