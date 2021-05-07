from __future__ import print_function

import glob
import importlib
import os
import sys
import time

from wrangle import library


def main(arguments=[]):
    time_start = int(time.time())
    library.print_log("Wrangle", "Started")
    runtime_errors = 0
    for module_path in glob.glob("{}/wrangle/*/*.py".format(os.path.dirname(os.path.realpath(__file__)))):
        if not module_path.endswith("__init__.py"):
            module_name = os.path.basename(os.path.dirname(module_path))
            time_start_module = int(time.time())
            library.print_log(module_name.title(), "Started")
            module = getattr(importlib.import_module("wrangle.{}".format(module_name)), module_name.title()) \
                (library.get_file(".profile") if len(arguments) <= 1 else arguments[1])
            module.run()
            runtime_errors += (
                    module.get_counter(library.CTR_SRC_RESOURCES, library.CTR_ACT_ERRORED) +
                    module.get_counter(library.CTR_SRC_FILES, library.CTR_ACT_ERRORED) +
                    module.get_counter(library.CTR_SRC_DATA, library.CTR_ACT_ERRORED) +
                    module.get_counter(library.CTR_SRC_EGRESS, library.CTR_ACT_ERRORED)
            )
            library.print_log(module_name.title(), "Completed in [{}] secs".format(int(time.time()) - time_start_module))
    library.print_log("Wrangle", "Completed in [{}] secs".format(int(time.time()) - time_start))
    return runtime_errors


if __name__ == "__main__":
    sys.exit(main(sys.argv))
