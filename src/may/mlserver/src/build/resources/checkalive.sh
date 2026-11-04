curl -sf --max-time 5 "http://${MLSERVER_SERVICE}:${MLSERVER_HTTP_PORT}/v2/health/live" >/dev/null
