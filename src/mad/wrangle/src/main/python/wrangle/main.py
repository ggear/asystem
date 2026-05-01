import argparse
import glob
import importlib
import sys
import time
from os.path import *

from wrangle.plugin import library


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="wrangle",
        description=(
            "Wrangle external data required by ASystem"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-o", "--once",
        action="store_true",
        help=(
            "force-reprocessing, log-debug, and run all plugins once and exit"
        ),
    )
    parser.add_argument(
        "-p", "--poll-period",
        type=int,
        default=30,
        metavar="MINUTES",
        help=(
            "run continuously, sleeping MINUTES between cycles (default: 30)"
        ),
    )
    parser.add_argument(
        "--force-reprocessing",
        action="store_true",
        help="flush each plugin's cached state and reprocess all files",
    )
    parser.add_argument(
        "--force-downloads",
        action="store_true",
        help="force all files to be re-downloaded even if cached",
    )
    parser.add_argument(
        "--disable-uploads",
        action="store_true",
        help="skip remote system uploads and write to local cache only",
    )
    parser.add_argument(
        "--disable-downloads",
        action="store_true",
        help="skip remote system downloads and read from local cache only",
    )
    parser.add_argument(
        "--drive-scope",
        choices=["production", "staging", "testing"],
        default="production",
        help="scope remote uploads and downloads (default: production)",
    )
    parser.add_argument(
        "-l", "--log",
        choices=["debug", "info", "warning", "error", "fatal"],
        default=None,
        help="logging verbosity (default: info; debug when --once is set)",
    )
    args = parser.parse_args(argv)
    if args.once:
        args.force_reprocessing = True
    if args.log is None:
        args.log = "debug" if args.once else "info"
    return args


def configure(args):
    library.config.log_level = args.log
    library.config.drive_scope = library.DriveScope(args.drive_scope)
    library.config.force_reprocessing = args.force_reprocessing
    library.config.force_downloads = args.force_downloads
    library.config.disable_uploads = args.disable_uploads
    library.config.disable_downloads = args.disable_downloads


def run_once():
    module_count = 0
    module_errored_count = 0
    for module_path in glob.glob(f"{dirname(realpath(__file__))}/plugin/*/*.py"):
        if not module_path.endswith("__init__.py"):
            module_name = basename(dirname(module_path))
            module = getattr(importlib.import_module(f"wrangle.plugin.{module_name}"), module_name.title())()
            module_count += 1
            module_errored = False
            try:
                module.run()
                counters = module.get_counters()
                for source in counters:
                    for action in counters[source]:
                        if action == library.CTR_ACT_ERRORED and counters[source][action] > 0:
                            module_errored = True
            except Exception as exception:
                module.print_log("Module threw unexpected exception", exception=exception)
                module_errored = True
            if module_errored:
                module_errored_count += 1
    return module_count != 0 and module_count > module_errored_count


def main(argv=None):
    args = parse_args(argv)
    configure(args)
    success = True
    try:
        library.database_open()
        while True:
            success = run_once()
            library.config.force_reprocessing = False
            if args.once or not args.poll_period:
                break
            time.sleep(args.poll_period * 60)
    except KeyboardInterrupt:
        library.print_log("wrangle", "Interrupted, exiting")
        success = True
    finally:
        library.database_close()
    return success


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
