[ "$(curl -LI "https://${APPDAEMON_SERVICE}:${APPDAEMON_HTTP_PORT}/aui/index.html" | tac | tac | head -n 1 | cut -d$' ' -f2)" == "200" ]
