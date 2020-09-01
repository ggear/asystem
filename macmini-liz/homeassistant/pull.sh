HOST_HOMEASSISTANT=$(basename $(dirname $(find . -type d -mindepth 1 -maxdepth 2 ! -path '/*/.*' | grep anode)))
HOST_LETSENCRYPT=$(basename $(dirname $(find . -type d -mindepth 1 -maxdepth 2 ! -path '/*/.*' | grep letsencrypt)))
DIR_LETSENCRYPT=$(sshpass -f /Users/graham/.ssh/.password ssh -q "root@${HOST_LETSENCRYPT}" 'find /home/asystem/letsencrypt -maxdepth 1 -mindepth 1 2>/dev/null | sort | tail -n 1')
sshpass -f /Users/graham/.ssh/.password scp -qpr "root@${HOST_LETSENCRYPT}:${DIR_LETSENCRYPT}/certificates/privkey.pem" "${HOST_HOMEASSISTANT}/homeassistant/src/main/resources/config/.pem" 2>/dev/null
sshpass -f /Users/graham/.ssh/.password scp -qpr "root@${HOST_LETSENCRYPT}:${DIR_LETSENCRYPT}/certificates/fullchain.pem" "${HOST_HOMEASSISTANT}/homeassistant/src/main/resources/config/certificate.pem" 2>/dev/null
echo "Pulled latest home assistant certificate"
