from asystem import *

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    metadata_df = load_bootstrap_entities()

    write_container_healthchecks()

    # Build broker schema
    metadata_networks_df = metadata_df[
        (metadata_df["index"] > 0) &
        (metadata_df["entity_status"] == "Enabled") &
        (metadata_df["device_via_device"] == "Networks") &
        (metadata_df["unique_id"].str.len() > 0) &
        (metadata_df["name"].str.len() > 0) &
        (metadata_df["discovery_topic"].str.len() > 0) &
        (metadata_df["state_topic"].str.len() > 0)
        ].copy()
    document = load_schema_document()
    write_schema_broker(metadata_networks_df,
                        topic_glob_discovery="homeassistant/+/networks/+/config",
                        topic_glob_data="networks/data/#",
                        document=document)

    # Build database schema
    write_schema_database(document, dialect="influxdb3", discover=True)
