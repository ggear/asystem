# Notes: https://github.com/AppDaemon/appdaemon/releases
FROM  acockburn/appdaemon:4.4.2 AS image_upstream

FROM image_upstream AS image_base

FROM image_base AS image_build

FROM image_build AS image_runtime
ENTRYPOINT ["/usr/src/app/dockerStart.sh"]
