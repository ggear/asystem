#!/usr/bin/env bash
#
# One-off bank cutover to the flow of plans/flow.md (section 11.2, steps 3 to 6), run by hand once on the host against the
# running release's version with its container stopped, just before the new release is installed, then deleted:
#
#   cutover.sh <running version> [<drive folder id>] [<archive dir>]
#
# Archives the Drive data folder and the release's data/bank, trashes every bank_reclassified_* file on Drive, removes the
# monthly placeholder rows from the manual_transactions_* files on Drive, and drops the old residue from the cache.

set -euo pipefail

VERSION="${1:?usage cutover.sh <version> [<drive folder id>] [<archive dir>]}"
DRIVE_FOLDER="${2:-1bfBMTDUj2Y5sZSu0yMR48ao_b6XEI72r}"
ARCHIVE_DIR="${3:-${HOME}/Backup/asystem/wrangle-cutover-$(date +%Y-%m-%d)}"
SERVICE_DIR="/home/asystem/wrangle/${VERSION}"

if [ ! -d "${SERVICE_DIR}/data/bank" ]; then
  echo "Bank cache [${SERVICE_DIR}/data/bank] not found" >&2
  exit 1
fi
if docker ps --format '{{.Names}}' | grep -qx wrangle; then
  echo "Container [wrangle] running, stop it before the cutover" >&2
  exit 1
fi
mkdir -p "${ARCHIVE_DIR}"

docker run --rm -i --entrypoint python3 \
  -v "${SERVICE_DIR}:/asystem/mnt" \
  -v "${ARCHIVE_DIR}:/archive" \
  "wrangle:${VERSION}" - "${DRIVE_FOLDER}" <<'PYEOF'
import csv
import glob
import io
import os
import re
import shutil
import sys

import google.oauth2.service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

drive_folder = sys.argv[1]
cache_dir = "/asystem/mnt/data/bank"
credentials = google.oauth2.service_account.Credentials.from_service_account_file("/root/.google_service_account.json", scopes=["https://www.googleapis.com/auth/drive"])
service = build("drive", "v3", credentials=credentials, cache_discovery=False)


def listed():
    files, token = [], None
    while True:
        response = service.files().list(q=f"'{drive_folder}' in parents and trashed = false", fields="nextPageToken, files(id, name)", pageSize=1000, pageToken=token).execute()
        files.extend(response.get("files", []))
        token = response.get("nextPageToken")
        if not token:
            return files


def downloaded(file_id):
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, service.files().get_media(fileId=file_id))
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()


shutil.copytree(cache_dir, "/archive/cache", dirs_exist_ok=True)
os.makedirs("/archive/drive", exist_ok=True)
drive_files = listed()
for drive_file in drive_files:
    with open(f"/archive/drive/{drive_file['id']}_{drive_file['name']}", "wb") as archive_file:
        archive_file.write(downloaded(drive_file["id"]))
print(f"Archived [{len(drive_files)}] Drive files and the cache to [/archive]")

trashed = 0
for drive_file in drive_files:
    if drive_file["name"].startswith("bank_reclassified_"):
        service.files().update(fileId=drive_file["id"], body={"trashed": True}).execute()
        trashed += 1
print(f"Trashed [{trashed}] change log files on Drive")

for drive_file in drive_files:
    if not re.fullmatch(r"manual_transactions_\d{4}\.csv", drive_file["name"]):
        continue
    lines = downloaded(drive_file["id"]).decode("utf-8").splitlines(keepends=True)
    header = next(csv.reader([lines[0]])) if lines else []
    kept = [lines[0]] if lines else []
    for line in lines[1:]:
        row = dict(zip(header, next(csv.reader([line])), strict=False))
        if row.get("Description", "").strip() == "Null Transaction" and float(row.get("Amount") or 0) == 0:
            continue
        kept.append(line)
    if len(kept) != len(lines):
        media = MediaIoBaseUpload(io.BytesIO("".join(kept).encode("utf-8")), mimetype="text/csv")
        service.files().update(fileId=drive_file["id"], media_body=media).execute()
        print(f"File [{drive_file['name']}] placeholder rows removed [{len(lines) - len(kept)}]")

removed = 0
for pattern in (
    "bank_reclassified_*",
    "__bank_transactions_*.csv",
    "__bank_balances_*.csv",
    "_sheet_bank_*",
    "__bank_classifier.csv",
    "__bank_accounts_dimension.csv",
    "__bank_logs.csv",
):
    for path in glob.glob(f"{cache_dir}/{pattern}"):
        os.remove(path)
        removed += 1
print(f"Removed [{removed}] old cache files")
PYEOF
