#!/bin/bash

RETURN_STRING="failed"
if python3 /config/scripts/ingress.py /downloads; then
  RETURN_STRING="done"
fi
echo "Post processing /downloads ... ${RETURN_STRING}"
