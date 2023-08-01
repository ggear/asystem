#!/bin/bash

netcat -zw 1 localhost ${DIGITEMP_HEALTH_PORT} >/dev/null 2>&1 || exit 1
