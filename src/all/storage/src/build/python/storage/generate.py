from homeassistant.generate import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    metadata_df = load_entity_metadata()

    # Build MQTT schema
    metadata_storage_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "Zeroth") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["name"].str.len() > 0) &
        (metadata_df["discovery_topic"].str.len() > 0) &
        (metadata_df["state_topic"].str.len() > 0)
        ]
    write_entity_metadata(metadata_storage_df,
                          topics_path="storage_${SUPERVISOR_HOST}",
                          topic_glob_discovery="homeassistant/+/storage_${SUPERVISOR_HOST}/+/config",
                          topic_glob_data="storage/${SUPERVISOR_HOST}/data/+/+/+")
