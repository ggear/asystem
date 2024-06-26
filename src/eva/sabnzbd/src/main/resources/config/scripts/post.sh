#!/bin/bash

RETURN_STRING="failed"
if python3 /config/scripts/rename.py /downloads; then
  RETURN_STRING="done"
fi
/config/scripts/normalise.sh /downloads/finished
echo "Post processing ... ${RETURN_STRING}"
