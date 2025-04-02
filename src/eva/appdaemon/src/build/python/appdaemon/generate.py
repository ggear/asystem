from homeassistant.generate import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    env = load_env(DIR_ROOT)
    modules = load_modules(load_disabled=False, load_infrastrcture=False)
    metadata_df = load_entity_metadata()

    write_bootstrap(script_bootstrap="""
echo 'No-Op bootstrap executed'
        """)
    write_healthcheck(script_alive="""
[ "$(curl -LI "https://${APPDAEMON_SERVICE}:${APPDAEMON_HTTP_PORT}/aui/index.html" | tac | tac | head -n 1 | cut -d$' ' -f2)" == "200" ]
        """, script_ready="""
[ "$(curl -H "x-ad-access: ${APPDAEMON_TOKEN}" -H "Content-Type: application/json" "https://${APPDAEMON_SERVICE}:${APPDAEMON_HTTP_PORT}/api/appdaemon/health" | jq -er .health)" == "OK" ]
        """)
    write_certificates()

    print("Build generate script [appdaemon] completed".format())
