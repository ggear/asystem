for script in $(ls src/test/resources/data); do mkdir -p target/runtime-system/data/${script}; find src/test/resources/data/${script}/success_typical -type f -exec cp -rvf {} target/runtime-system/data/${script} \;; done
docker compose --ansi never up --force-recreate
