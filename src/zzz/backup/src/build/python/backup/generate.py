from os.path import abspath, dirname, join, realpath

from asystem import load_bootstrap_entities

DIR_ROOT = abspath(join(dirname(realpath(__file__)), "../../../.."))

if __name__ == "__main__":
    metadata_df = load_bootstrap_entities()
