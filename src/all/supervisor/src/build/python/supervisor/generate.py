from operator import itemgetter

from asystem import *
from fabfile import _get_modules_by_hosts, _get_host_label, _get_host_index, HOSTS

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    metadata_df = load_bootstrap_entities()

    write_container_healthchecks()

    # Build broker schema
    metadata_supervisor_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "Supervisor") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["name"].str.len() > 0) &
        (metadata_df["discovery_topic"].str.len() > 0) &
        (metadata_df["state_topic"].str.len() > 0)
        ]
    document = load_schema_document()
    modules_all = _get_modules_by_hosts("docker-compose.yml")
    modules_server = {}
    for host, services in modules_all.items():
        if HOSTS[_get_host_label(host)][4] == "edge" or HOSTS[_get_host_label(host)][4] == "server":
            modules_server[host] = sorted(modules_all[host])
    write_schema_broker(metadata_supervisor_df,
                        broker_topic_glob_discovery="homeassistant/+/supervisor_${SUPERVISOR_HOST}/+/config",
                        broker_topic_glob_data="supervisor/${SUPERVISOR_HOST}/#",
                        broker_document=document,
                        broker_entities=[{"HOST": host, "SERVICE": services}
                                         for host, services in sorted(modules_server.items())])

    # Build config and database schema
    write_schema_database(document, database_dialect="influxdb3", database_entities={
        "supervisor/host": sorted(modules_server.keys()),
        "supervisor/service": sorted({service for services in modules_server.values() for service in services}),
    }, database_renamed_measures={
        "warn_temperature_of_max": "warn_temperature",
        "spin_fan_speed_of_max": "spin_fan_speed",
    })
    metadata_supervisor_schema = []
    for host, services in sorted(modules_server.items(), key=itemgetter(0)):
        host_index = _get_host_index(_get_host_label(host))
        host_schema = {"host": host}
        if host_index is not None:
            host_schema["index"] = host_index
        host_schema["services"] = sorted(services)
        metadata_supervisor_schema.append(host_schema)
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
                "schema": metadata_supervisor_schema
            },
        }, indent=2))
    print("Build generate script [supervisor] service metadata persisted to [{}]".format(metadata_supervisor_path))
