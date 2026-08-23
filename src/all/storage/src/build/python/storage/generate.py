from asystem import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    metadata_df = load_bootstrap_entities()

    # Build broker schema
    metadata_storage_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "Storage") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["name"].str.len() > 0) &
        (metadata_df["discovery_topic"].str.len() > 0) &
        (metadata_df["state_topic"].str.len() > 0)
        ]
    write_schema_broker(metadata_storage_df,
                        broker_topic_glob_discovery="homeassistant/+/storage_${STORAGE_HOST}/+/config",
                        broker_topic_glob_data="storage/${STORAGE_HOST}/data/+/+/+")
