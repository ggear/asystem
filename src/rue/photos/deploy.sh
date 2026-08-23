#!/bin/bash

ROOT_DIR="$(dirname "$(readlink -f "$0")")"

PYTHONPATH="${ROOT_DIR}/../../all/_/src/build/python${PYTHONPATH:+:${PYTHONPATH}}" \
  "${HOME}/.pyenv/versions/asystem/bin/python" "${ROOT_DIR}/src/build/python/photos/export_photoslibrary.py"
