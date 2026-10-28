from asystem import *

if __name__ == "__main__":
    metadata_df = load_bootstrap_entities()

    write_container_healthchecks()

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
