from homeassistant.generate import load_entity_metadata

if __name__ == "__main__":
    metadata_df = load_entity_metadata()

    print("Build generate script [mlserver] completed".format())
