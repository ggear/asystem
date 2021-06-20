from __future__ import print_function

import glob
import importlib
import os
import sys

from wrangle import library


def main(arguments=[]):
    runtime_errors = 0
    for module_path in glob.glob("{}/wrangle/*/*.py".format(os.path.dirname(os.path.realpath(__file__)))):
        if not module_path.endswith("__init__.py"):
            module_name = os.path.basename(os.path.dirname(module_path))
            module = getattr(importlib.import_module("wrangle.{}".format(module_name)), module_name.title())()
            module.run()
            runtime_errors += (
                    module.get_counter(library.CTR_SRC_SOURCES, library.CTR_ACT_ERRORED) +
                    module.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED) +
                    module.get_counter(library.CTR_SRC_DATA, library.CTR_ACT_ERRORED) +
                    module.get_counter(library.CTR_SRC_EGRESS, library.CTR_ACT_ERRORED)
            )
    return runtime_errors


if __name__ == "__main__":
    sys.exit(main(sys.argv))
