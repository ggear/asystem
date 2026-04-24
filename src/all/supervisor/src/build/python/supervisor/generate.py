from operator import itemgetter

from fabfile import _get_modules_by_hosts, _get_host_label, HOSTS
from homeassistant.generate import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    metadata_df = load_entity_metadata()

    write_bootstrap()
    write_healthcheck()

    # Build metadata publish JSON
    metadata_supervisor_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "Supervisor") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["name"].str.len() > 0) &
        (metadata_df["discovery_topic"].str.len() > 0) &
        (metadata_df["state_topic"].str.len() > 0)
        ]
    write_entity_metadata("supervisor", join(DIR_ROOT, "src/main/resources/image/mqtt"), metadata_supervisor_df,
                          "homeassistant/+/supervisor_${SUPERVISOR_HOST}/+/config",
                          "supervisor/${SUPERVISOR_HOST}/data/+/+/+", "supervisor_${SUPERVISOR_HOST}")

    # Build config
    hosts = []
    modules_all = _get_modules_by_hosts("docker-compose.yml")
    modules_server = {}
    for host, services in modules_all.items():
        if HOSTS[_get_host_label(host)][4] == "edge" or HOSTS[_get_host_label(host)][4] == "server":
            modules_server[host] = sorted(modules_all[host])
    metadata_supervisor_path = abspath(join(DIR_ROOT, "src/main/resources/image/config.json"))
    with open(metadata_supervisor_path, 'w') as metadata_supervisor_file:
        metadata_supervisor_file.write(json.dumps({
            "asystem": {
                "version": "$SERVICE_VERSION_ABSOLUTE",
                "host": "$SUPERVISOR_HOST",
                "mount": "$SUPERVISOR_MOUNT",
                "broker": {
                    "host": "$BROKER_HOST",
                    "port": "$BROKER_PORT",
                    "token": "$DATABASE_TOKEN"
                },
                "database": {
                    "host": "$DATABASE_HOST",
                    "port": "$DATABASE_PORT",
                    "name": "$DATABASE_NAME",
                    "token": "$DATABASE_TOKEN"
                },
                "schema": [{
                    "host": host,
                    "services": sorted(services)
                } for host, services in sorted(modules_server.items(), key=itemgetter(0))]
            },
        }, indent=2))
    print("Build generate script [supervisor] service metadata persisted to [{}]".format(metadata_supervisor_path))
