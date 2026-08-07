from asystem import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    metadata_df = load_bootstrap_entities()

    write_container_healthchecks()

    # Build broker schema
    metadata_tempstat_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "TempStat") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["name"].str.len() > 0) &
        (metadata_df["discovery_topic"].str.len() > 0) &
        (metadata_df["state_topic"].str.len() > 0)
        ].copy()
    document = load_schema_document(config="src/main/resources/image/sensors.json")
    write_schema_broker(metadata_tempstat_df,
                        topic_glob_discovery="homeassistant/+/tempstat/+/config",
                        topic_glob_data="tempstat/data",
                        document=document)
