from homeassistant.generate import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    env = load_env(DIR_ROOT)
    modules = load_modules(load_disabled=False, load_infrastrcture=False)
    metadata_df = load_entity_metadata()

    write_bootstrap("appdaemon", join(DIR_ROOT, "src/main/resources/image"))
    write_certificates("appdaemon", join(DIR_ROOT, "src/main/resources/image"))
    write_healthcheck("appdaemon", join(DIR_ROOT, "src/main/resources/image"), """
[ "$(curl -LI "https://${APPDAEMON_SERVICE}:${APPDAEMON_HTTP_PORT}/aui/index.html" | tac | tac | head -n 1 | cut -d$' ' -f2)" == "200" ]
        """, """
[ "$(curl -H "x-ad-access: ${APPDAEMON_TOKEN}" -H "Content-Type: application/json" "https://${APPDAEMON_SERVICE}:${APPDAEMON_HTTP_PORT}/api/appdaemon/health" | jq -er .health)" == "OK" ]
        """)

    print("Build generate script [appdaemon] completed".format())
