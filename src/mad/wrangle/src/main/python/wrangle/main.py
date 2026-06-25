import argparse
import contextlib
import ctypes
import datetime
import faulthandler
import gc
import glob
import importlib
import os
import signal
import sys
import time
from os.path import basename, dirname, isdir, join, realpath

from wrangle import plugin
from wrangle import server as web_server
from wrangle.plugin import database, print_log
from wrangle.plugin.config import STACK_DUMP_FILE
from wrangle.plugin.counters import *

try:
    import pyarrow
except Exception:
    pyarrow = None


def _release_memory():
    gc.collect()
    if pyarrow is not None:
        with contextlib.suppress(Exception):
            pyarrow.default_memory_pool().release_unused()
    if sys.platform.startswith("linux"):
        with contextlib.suppress(Exception):
            ctypes.CDLL("libc.so.6").malloc_trim(0)


def configure(argv=None):
    parser = argparse.ArgumentParser(
        prog="wrangle",
        description=(
            "Wrangle external data required by ASystem"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Common switches
    parser.add_argument(
        "-p", "--filter-plugins",
        default=None,
        metavar="CSV",
        help=(
            "run only plugins listed in CSV (example: balances,equity)"
        ),
    )
    parser.add_argument(
        "-r", "--force-reprocessing",
        action="store_true",
        help="flush each plugin's cached state and reprocess all files",
    )
    parser.add_argument(
        "-d", "--force-downloads",
        action="store_true",
        help="force all files to be re-downloaded even if cached",
    )
    parser.add_argument(
        "-u", "--enable-uploads",
        action="store_true",
        help="enable all upload targets",
    )

    # Uncommon switches
    parser.add_argument(
        "--enable-drive-uploads",
        action="store_true",
        help="enable Google Drive uploads",
    )
    parser.add_argument(
        "--enable-sheet-uploads",
        action="store_true",
        help="enable Google Sheets uploads",
    )
    parser.add_argument(
        "--enable-database-uploads",
        action="store_true",
        help="enable database uploads",
    )
    parser.add_argument(
        "--disable-downloads",
        action="store_true",
        help="disable all download sources",
    )
    parser.add_argument(
        "--disable-drive-downloads",
        action="store_true",
        help="skip Google Drive downloads and read from local cache only",
    )
    parser.add_argument(
        "--disable-source-downloads",
        action="store_true",
        help="skip remote source data downloads and read from local cache only",
    )
    parser.add_argument(
        "--disable-database-downloads",
        action="store_true",
        help="skip database downloads and read from local cache only",
    )
    parser.add_argument(
        "--disable-sheet-downloads",
        action="store_true",
        help="skip sheet downloads and read from local cache only",
    )

    # System switches
    parser.add_argument(
        "--poll-period",
        type=int,
        default=0,
        metavar="MINUTES",
        help=(
            "run continuously on a fixed cadence; 0 runs once and exits with debug logging (default: 0); "
            f"if greater than 0 must be one of {sorted(HISTORY_RAW_LABELS)}"
        ),
    )
    parser.add_argument(
        "--cache-dir",
        default="/asystem/mnt/data",
        metavar="DIR",
        help="base directory for plugin data caches (default: /asystem/mnt/data)",
    )
    parser.add_argument(
        "--repo-scope",
        choices=["release", "preview", "local"],
        default="release",
        help="scope data repository uploads and downloads (default: release)",
    )
    parser.add_argument(
        "--disable-loop",
        action="store_true",
        help="start the HTTP server but skip the polling loop, accepting runs via API",
    )
    parser.add_argument(
        "--dump-database-queries",
        action="store_true",
        help="print common SQL queries for all plugins that query the database, then exit",
    )
    parser.add_argument(
        "--log",
        choices=["debug", "info", "warning", "error", "fatal"],
        default=None,
        help="logging verbosity (default: info; debug when running once)",
    )

    args = parser.parse_args(argv)
    if args.poll_period != 0 and args.poll_period not in HISTORY_RAW_LABELS:
        parser.error(f"argument -p/--poll-period: MINUTES must be 0 or one of {sorted(HISTORY_RAW_LABELS)}")
    filter_plugins = None
    if args.filter_plugins is not None:
        filter_plugins_csv: str = args.filter_plugins
        filter_plugins = []
        for plugin_name in (name.strip() for name in filter_plugins_csv.split(",")):
            if plugin_name and plugin_name not in filter_plugins:
                filter_plugins.append(plugin_name)
        available_plugins = set(_get_plugins())
        missing_plugins = [plugin_name for plugin_name in filter_plugins if plugin_name not in available_plugins]
        if missing_plugins:
            parser.error("\n".join(f"argument --filter-plugins: plugin '{plugin_name}' does not exist" for plugin_name in missing_plugins))
    args.filter_plugins = filter_plugins
    if args.enable_uploads:
        args.enable_drive_uploads = True
        args.enable_sheet_uploads = True
        args.enable_database_uploads = True
    if args.disable_downloads:
        args.disable_drive_downloads = True
        args.disable_source_downloads = True
        args.disable_database_downloads = True
        args.disable_sheet_downloads = True
    if args.log is None:
        args.log = "debug" if args.poll_period == 0 else "info"
    plugin.config.log_level = args.log
    plugin.config.poll_period = args.poll_period
    plugin.config.repo_scope = plugin.RepoScope(args.repo_scope)
    plugin.config.cache_dir = args.cache_dir
    plugin.config.force_reprocessing = args.force_reprocessing
    plugin.config.force_downloads = args.force_downloads
    plugin.config.disable_drive_uploads = not args.enable_drive_uploads
    plugin.config.disable_sheet_uploads = not args.enable_sheet_uploads
    plugin.config.disable_database_uploads = not args.enable_database_uploads
    plugin.config.disable_drive_downloads = args.disable_drive_downloads
    plugin.config.disable_sheet_downloads = args.disable_sheet_downloads
    plugin.config.disable_database_downloads = args.disable_database_downloads
    plugin.config.disable_source_downloads = args.disable_source_downloads
    return args


_SECRET_ENV_SUFFIXES = ("PASSWORD", "KEY", "TOKEN", "SECRET")


def _dump_database_queries():
    psql_prefix = (
        "PGPASSWORD=$WRANGLE_DATABASE_PASSWORD \\\n"
        "  psql \\\n"
        "    --host=$WRANGLE_DATABASE_HOST \\\n"
        "    --port=$WRANGLE_DATABASE_PORT \\\n"
        "    --username=$WRANGLE_DATABASE_USER \\\n"
        "    --dbname=$WRANGLE_DATABASE_USER"
    )
    for plugin_name in _get_plugins():
        instance = _instantiate_plugin(plugin_name)
        if instance.database:
            print(f"# {plugin_name}")
            for template in database.DATABASE_QUERY_TEMPLATES:
                print(f"{psql_prefix} \\\n    --command=\"\n{template.format(table=plugin_name)};\n\"")
                print()
            print()


def main(argv=None):
    args = configure(argv)
    if args.dump_database_queries:
        _dump_database_queries()
        return
    init_start = time.perf_counter()
    print_log("Wrangle", "Starting ...")
    wrangle_env_lines = [
        f"  {name}={'***' if any(name.endswith(suffix) for suffix in _SECRET_ENV_SUFFIXES) else value}"
        for name, value in sorted(os.environ.items())
        if name.startswith("WRANGLE_")
    ]
    if wrangle_env_lines:
        print_log("Wrangle", ["Environment:"] + wrangle_env_lines)
    stack_dump_file = None
    stack_dump_file = open(STACK_DUMP_FILE, "a", buffering=1)  # noqa: SIM115
    faulthandler.enable(file=stack_dump_file, all_threads=True)
    faulthandler.register(signal.SIGINT, file=stack_dump_file, all_threads=True, chain=True)
    faulthandler.register(signal.SIGUSR1, file=stack_dump_file, all_threads=True, chain=False)
    active_plugins = args.filter_plugins or _get_plugins()
    history = None
    if args.poll_period or args.disable_loop:
        http_port_str = os.environ.get("WRANGLE_HTTP_PORT")
        if http_port_str:
            try:
                http_port = int(http_port_str)
            except ValueError:
                print_log("wrangle", f"WRANGLE_HTTP_PORT '{http_port_str}' is not a valid port number, HTTP server disabled", level="warning")
                http_port = None
            if http_port is not None:
                poll_period_minutes = args.poll_period or 30
                history = RunHistory(
                    plugins=active_plugins,
                    cache_dir=plugin.config.cache_dir,
                    poll_period_minutes=poll_period_minutes,
                    raw_label=HISTORY_RAW_LABELS[poll_period_minutes],
                )
                history.load()
                bound_history = history

                def run_callback(force_reprocessing=False):
                    def _do_run():
                        callback_start = time.perf_counter()
                        plugin.config.force_reprocessing = force_reprocessing
                        _, callback_results, callback_plugin_count, callback_errored_count = _run_plugins(filter_plugins=args.filter_plugins)
                        plugin.config.force_reprocessing = False
                        callback_counters, _ = _record_plugin_run(
                            callback_results, callback_plugin_count, callback_errored_count, callback_start, "adhoc",
                            lambda counters, overhead: bound_history.add_adhoc_run(ts=datetime.datetime.now(tz=CTR_TZ), plugin_counters=counters, overhead_ms=overhead),
                        )
                        return {"ts": datetime.datetime.now(tz=CTR_TZ).isoformat(), "counters": callback_counters}

                    try:
                        return bound_history.execute_adhoc(_do_run)
                    except TimeoutError as exception:
                        print_log("wrangle", "Timed out acquiring run lock, recording errored run", exception=exception, level="error")
                        failed_results = _failed_run_results(active_plugins)
                        callback_counters, _ = _record_plugin_run(
                            failed_results, len(failed_results), len(failed_results), time.perf_counter(), "adhoc",
                            lambda counters, overhead: bound_history.add_adhoc_run(ts=datetime.datetime.now(tz=CTR_TZ), plugin_counters=counters, overhead_ms=overhead),
                        )
                        return {"ts": datetime.datetime.now(tz=CTR_TZ).isoformat(), "counters": callback_counters}

                web_server.start_server(http_port, history, run_callback)
                print_log("Wrangle", f"HTTP server listening on port [{http_port}]")
    elif args.poll_period == 0:
        history = RunHistory(
            plugins=active_plugins,
            cache_dir=plugin.config.cache_dir,
            poll_period_minutes=0,
            raw_label="",
        )
    print_log("Wrangle", f"Finished init in [{int(time.perf_counter() - init_start)}s], "
                         f"{"listening for API plugin run calls" if args.disable_loop else "starting plugin run loop"}")
    try:
        plugin.database_open()
        if args.disable_loop:
            while True:
                time.sleep(3600)
        prev_add_run_ms = 0
        while True:
            cycle_start = time.perf_counter()
            cycle_start_dt = datetime.datetime.now(tz=CTR_TZ)
            try:
                lock_cm = history.acquire_run_lock() if history is not None else contextlib.nullcontext()
                with lock_cm:
                    success, plugin_results, plugin_count, plugin_errored_count = _run_plugins(filter_plugins=args.filter_plugins)
                    plugin.config.force_reprocessing = False
                    if history is not None and args.poll_period > 0:
                        _, prev_add_run_ms = _record_plugin_run(
                            plugin_results, plugin_count, plugin_errored_count, cycle_start, "loop",
                            lambda counters, overhead, h=history, s=cycle_start_dt: h.add_run(ts=datetime.datetime.now(tz=CTR_TZ), plugin_counters=counters, loop_overhead_ms=overhead, start_ts=s),
                            extra_overhead_ms=prev_add_run_ms,
                        )
                        success = not history.is_errored()
            except TimeoutError as exception:
                print_log("wrangle", "Timed out acquiring run lock, recording errored run", exception=exception, level="error")
                success, plugin_results, plugin_count, plugin_errored_count = False, _failed_run_results(active_plugins), len(active_plugins), len(active_plugins)
                if history is not None and args.poll_period > 0:
                    _, prev_add_run_ms = _record_plugin_run(
                        plugin_results, plugin_count, plugin_errored_count, cycle_start, "loop",
                        lambda counters, overhead, h=history, s=cycle_start_dt: h.add_run(ts=datetime.datetime.now(tz=CTR_TZ), plugin_counters=counters, loop_overhead_ms=overhead, start_ts=s),
                        extra_overhead_ms=prev_add_run_ms,
                    )
            if not args.poll_period:
                if history is not None:
                    _record_plugin_run(
                        plugin_results, plugin_count, plugin_errored_count, cycle_start, "adhoc",
                        lambda counters, overhead, h=history: h.add_adhoc_run(ts=datetime.datetime.now(tz=CTR_TZ), plugin_counters=counters, overhead_ms=overhead),
                    )
                sys.exit(0 if success else 1)
            poll_period_seconds = args.poll_period * 60
            elapsed_seconds = time.perf_counter() - cycle_start
            sleep_seconds = poll_period_seconds - elapsed_seconds
            if sleep_seconds <= 0:
                print_log("wrangle", f"Run took [{elapsed_seconds:.0f}s] which exceeds poll period [{poll_period_seconds:.0f}s], starting next cycle immediately", level="warning")
            else:
                _release_memory()
                time.sleep(sleep_seconds)
    except KeyboardInterrupt as exception:
        print_log("wrangle", "Interrupted, exiting", exception=exception)
        sys.exit(0)
    finally:
        plugin.database_close()
        if stack_dump_file is not None:
            faulthandler.unregister(signal.SIGINT)
            faulthandler.unregister(signal.SIGUSR1)
            faulthandler.disable()
            stack_dump_file.close()


def _run_plugins(filter_plugins=None):
    plugin_count = 0
    plugin_errored_count = 0
    plugin_results = {}
    plugin_names = _get_plugins()
    if filter_plugins is not None:
        filter_plugin_set = set(filter_plugins)
        plugin_names = [name for name in plugin_names if name in filter_plugin_set]
    for plugin_name in plugin_names:
        plugin_count += 1
        plugin_errored = False
        plugin_instance = None
        plugin_started = time.perf_counter()
        counters = {}
        try:
            plugin_instance = _instantiate_plugin(plugin_name)
            plugin_instance.run()
            counters = plugin_instance.get_counters()
            for source in counters:
                for action in counters[source]:
                    if action == CTR_ACT_ERRORED and counters[source][action] > 0:
                        plugin_errored = True
        except Exception as exception:
            if isinstance(plugin_instance, plugin.Plugin):
                plugin_instance.print_log("Plugin threw unexpected exception", exception=exception)
                counters = plugin_instance.get_counters()
            else:
                print_log(plugin_name, "Plugin failed to load or initialise", exception=exception)
            plugin_errored = True
        plugin_results[plugin_name] = {"counters": counters, "runtime_sec": time.perf_counter() - plugin_started, "errored": plugin_errored}
        if plugin_errored:
            plugin_errored_count += 1
    return plugin_count != 0 and plugin_errored_count == 0, plugin_results, plugin_count, plugin_errored_count


def _get_plugins():
    plugin_dir = join(dirname(realpath(__file__)), "plugin")
    active = []
    for plugin_path in glob.glob(join(plugin_dir, "*")):
        plugin_name = basename(plugin_path)
        if not isdir(plugin_path) or plugin_name.startswith("_"):
            continue
        instance = _instantiate_plugin(plugin_name)
        if not instance.disabled:
            active.append((instance.order, plugin_name))
    return [name for _, name in sorted(active)]


def _instantiate_plugin(plugin_name):
    plugin_class = "".join(part.capitalize() for part in plugin_name.split("_"))
    return getattr(importlib.import_module(f"wrangle.plugin.{plugin_name}"), plugin_class)()


def _failed_run_results(plugin_names):
    plugin_results = {}
    for plugin_name in plugin_names:
        counters = {}
        for (source, action) in COUNTERS:
            counters.setdefault(source, {})[action] = 0
        counters[CTR_SRC_SOURCES][CTR_ACT_ERRORED] = 1
        plugin_results[plugin_name] = {"counters": counters, "runtime_sec": 0.0, "errored": True}
    return plugin_results


def _record_plugin_run(plugin_results, plugin_count, plugin_errored_count, run_start, run_label, record_fn, extra_overhead_ms=0):
    plugin_counters = {name: data["counters"] for name, data in plugin_results.items()}
    sum_plugin_ms = sum(data["counters"].get(CTR_SRC_TIMING, {}).get(CTR_ACT_TOTAL_MILLIS, 0) for data in plugin_results.values())
    overhead_ms = int((time.perf_counter() - run_start) * 1000) - sum_plugin_ms + extra_overhead_ms
    print_log("Wrangle", "Starting ...")
    record_started = time.perf_counter()
    record_fn(plugin_counters, overhead_ms)
    record_elapsed_ms = int((time.perf_counter() - record_started) * 1000)
    print_log("Wrangle", f"Finished {run_label} run of [{plugin_count}] plugins, with [{plugin_errored_count}] erroring, in [{int(time.perf_counter() - run_start)}s]")
    return plugin_counters, record_elapsed_ms


if __name__ == "__main__":
    main()
