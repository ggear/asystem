#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Replete fixture: touch source spreadsheets, trim the current snapshot's last date so rows_delta=1
refresh_replete_trimmed "inflation.xlsx retail.xlsx" "*.xlsx"
