# all - generalise deploy artefacts to scripts, docker, certs from target - wrap up as bundle
#     - add python3 install, include fab, mqtt etc in requirements.txt
#     - consider an init.sh and a poll.sh script, the former does a cron, the latter does the ticks
#     - convert all docker-compose to run.sh

# macmini-liz/certs - Add mount points to docker-compose.yml for config, certs, hooks (udm, anode, ha etc)

# udm-rack/host - Develop script to sshpass authorization key if not there, prepapre and copy certifcates, post uptime (ssh/portal/network/video/internet) to MQTT

# macmini-liz/ha - Develop script to copy certs, checkuptime, restart

# macmini-liz/anode - Develop script to copy certs, uptime to down, perhaps restart

# macmini-liz/speedtest - run speedtest in docker
