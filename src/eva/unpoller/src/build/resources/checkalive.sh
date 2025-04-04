[ "$(curl "http://${UNPOLLER_SERVICE}:${UNPOLLER_HTTP_PORT}/health")" == "OK" ]
