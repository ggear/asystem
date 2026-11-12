import json

from asystem import *


def write_hosts(metadata_df, root_dir):
    labels = [line.split("=")[0] for line in Path(join(root_dir, "../../../.hosts")).read_text().strip().split("\n") if line.strip() and not line.strip().startswith("#")]
    servers = metadata_df[
        (metadata_df["entity_status"] == "Enabled")
        & (metadata_df["device_via_device"] == "Server")
        & (metadata_df["device_suggested_area"] == "Rack")
        & (metadata_df["device_model"].str.startswith("MacMini"))
        & (metadata_df["device_identifiers"].str.len() > 0)
    ]
    hosts = sorted(
        ({"name": identifier.split("-", 1)[1], "address": identifier, "mac": mac} for identifier, mac in zip(servers["device_identifiers"], servers["connection_mac"], strict=True)),
        key=lambda host: labels.index(host["name"]),
    )
    hosts_path = join(root_dir, "src/main/resources/image/hosts.json")
    os.makedirs(dirname(hosts_path), exist_ok=True)
    with open(hosts_path, "w") as hosts_file:
        json.dump(hosts, hosts_file, indent=2)
        hosts_file.write("\n")
    print(f"Build generate script [{basename(root_dir)}] hosts persisted to [{hosts_path}]")


if __name__ == "__main__":
    metadata_df = load_bootstrap_entities()

    write_container_healthchecks()
    write_container_backup()
    write_container_restore()
    write_hosts(metadata_df, abspath(join(dirname(realpath(realpath(sys.argv[0]))), "../../../..")))

    # Build broker schema
    metadata_rackmains_df = metadata_df[
        (metadata_df["index"] > 0)
        & (metadata_df["entity_status"] == "Enabled")
        & (metadata_df["device_via_device"] == "RackMains")
        & (metadata_df["unique_id"].str.len() > 0)
        & (metadata_df["name"].str.len() > 0)
        & (metadata_df["discovery_topic"].str.len() > 0)
        & (metadata_df["state_topic"].str.len() > 0)
    ].copy()
    document = load_schema_document()
    write_schema_broker(metadata_rackmains_df, broker_topic_glob_discovery="homeassistant/+/rackmains/+/config", broker_topic_glob_data="rackmains/#", broker_document=document)
