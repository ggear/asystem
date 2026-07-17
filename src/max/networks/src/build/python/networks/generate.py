from homeassistant.generate import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    metadata_df = load_entity_metadata()

    write_bootstrap()
    write_healthcheck()

    # Build MQTT schema
    metadata_networks_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "Zeroth") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["name"].str.len() > 0) &
        (metadata_df["discovery_topic"].str.len() > 0) &
        (metadata_df["state_topic"].str.len() > 0)
        ]
    write_entity_metadata(metadata_networks_df,
                          topics_path="networks_${SUPERVISOR_HOST}",
                          topic_glob_discovery="homeassistant/+/networks_${SUPERVISOR_HOST}/+/config",
                          topic_glob_data="networks/${SUPERVISOR_HOST}/data/+/+/+")
