#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, forced reprocessing dedupes every transactions file by source id: one in two files keeps the earlier, while a sourced transaction beside an id-less one of the same amount within three days, split parts sharing a source id and identical id-less transactions all stay
refresh_write_fixture 0 0 "" 1 -1
