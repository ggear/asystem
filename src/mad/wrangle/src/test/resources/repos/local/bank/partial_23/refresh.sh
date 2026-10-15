#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, on linked rows a category manual and a valid split are kept, the split saved as contiguous parts sharing one id, the bucket following the category
refresh_write_fixture 0 0 "" 0 -1
