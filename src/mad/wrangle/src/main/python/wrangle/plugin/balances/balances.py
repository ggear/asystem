import time
import uuid
from datetime import datetime
from os.path import *
from typing import Any

import polars as pl
import polars.selectors as cs

from wrangle import plugin
from wrangle.plugin.logger import dataframe_print

BALANCES_SCHEMA = {
    "Date": pl.Date,
    "Time": pl.Utf8,
    "Account Name": pl.Utf8,
    "Account Number": pl.Utf8,
    "Institution": pl.Utf8,
    "Balance": pl.Float64,
    "Balance ID": pl.Utf8,
}

ACCOUNT_METADATA = {
    "xxxx1000": "AMEX Graham",
    "xxxx1009": "AMEX Jane",
    "xxxx1842": "BWST Current",
    "xxxx3885": "BWST Joint",
    "xxxx8536": "BWST Savings",
    "xxxx7415": "BWST Budgeted",
    "xxxx3103": "CBA Savings",
    "xxxx8552": "CBA Funds",
    "xxxx5418": "HSBC Credit",
    "xxxx6118": "HSBC Savings",
}

BALANCE_MAX_AGE_HOURS = 4


class Balances(plugin.Plugin):
    _repos = plugin.Repos(
        preview={
            "drive_folder": "PLACEHOLDER",
            "sheet_balances": "PLACEHOLDER",
        },
        release={
            "drive_folder": "1VAwVLV6OykFFLqapwFnJUXB6msQOlAsZ",
            "sheet_balances": "1m-NUkd3_uCiM5of6m1M57bvgkHXOL9NtgAXTDDDxgt8",
        },
    )

    def _run(self):
        started_time = time.time()
        new_data = False
        balance_files = {}
        balances_df = self.dataframe_new(schema=BALANCES_SCHEMA, print_rows=-1)
        if not plugin.config.disable_downloads:

            # Download and join account/balance data
            started_time_inner = time.time()
            today_datetime = datetime.today()
            today = today_datetime.date()
            monthly_file = abspath(f"{self.local_cache}/Redbark_Balances_{today.year}_{today.month:02d}.csv")
            existing_df = None
            if isfile(monthly_file):
                existing_df = self.csv_read(monthly_file, schema=BALANCES_SCHEMA)
                if len(existing_df) == 0:
                    existing_df = None
            needs_download = True
            if existing_df is not None:
                latest_row = existing_df.sort(["Date", "Time"]).tail(1)
                latest_datetime = datetime.combine(latest_row["Date"][0], datetime.strptime(latest_row["Time"][0].zfill(8), "%H:%M:%S").time())
                if (today_datetime - latest_datetime).total_seconds() / 3600 <= BALANCE_MAX_AGE_HOURS:
                    needs_download = False
            if needs_download:
                accounts_result = self.bank_download("Accounts", data="accounts")
                balances_result = self.bank_download("Balances", data="balances")
                if accounts_result.status != plugin.DownloadStatus.FAILED and balances_result.status != plugin.DownloadStatus.FAILED:
                    try:
                        rows = []
                        accounts_df = self.csv_read(accounts_result.file_path).with_columns(
                            pl.col("id").cast(pl.Utf8, strict=False).fill_null("")
                        )
                        balances_raw_df = self.csv_read(balances_result.file_path).with_columns(
                            pl.col("accountId").cast(pl.Utf8, strict=False).fill_null("")
                        )
                        time_str = today_datetime.strftime("%H:%M:%S")
                        account_lookup: dict[str, dict[str, Any]] = {
                            str(row["id"]): row for row in accounts_df.rows(named=True)
                        }
                        for balance_row in balances_raw_df.rows(named=True):
                            account_id = str(balance_row["accountId"])
                            account = account_lookup.get(account_id, {})
                            balance = balance_row.get("currentBalance")
                            account_number = str(account.get("accountNumber") or "")
                            account_name = str(account.get("name") or "")
                            institution = str(account.get("institutionName") or "")
                            balance_id = uuid.uuid5(uuid.NAMESPACE_OID, f"{account_id}|{today}|{time_str}").hex
                            rows.append({
                                "Date": today,
                                "Time": time_str,
                                "Account Name": account_name,
                                "Account Number": account_number,
                                "Balance ID": balance_id,
                                "Institution": institution,
                                "Balance": balance,
                            })
                        today_df = pl.DataFrame(rows, schema=BALANCES_SCHEMA) if rows else self.dataframe_new(schema=BALANCES_SCHEMA)
                        dataframe_print(self.name, today_df, print_label="Balances", print_verb="transformed", started=started_time_inner)

                        # Detect new balance data
                        balances_changed = (existing_df is None or existing_df.filter(pl.col("Date") == pl.lit(today).cast(pl.Date)).height == 0)
                        if existing_df is not None and not balances_changed:
                            account_key_columns = ["Institution", "Account Number", "Account Name"]
                            latest_per_account = (
                                existing_df.sort(["Date", "Time"])
                                .unique(subset=account_key_columns, keep="last")
                                .select([*account_key_columns, "Balance"])
                                .rename({"Balance": "Previous Balance"})
                            )
                            check_df = today_df.select([*account_key_columns, "Balance"]).join(latest_per_account, on=account_key_columns, how="left")
                            balances_changed = check_df.filter(
                                pl.col("Previous Balance").is_null() | (pl.col("Balance") != pl.col("Previous Balance"))
                            ).height > 0
                        if balances_changed:
                            combined_df = (pl.concat([existing_df, today_df], how="diagonal") if existing_df is not None else today_df).sort(["Date", "Time", "Account Name"])
                            self.csv_write(combined_df, monthly_file)
                            balance_files[monthly_file] = plugin.DownloadResult(plugin.DownloadStatus.DOWNLOADED, monthly_file)
                        else:
                            balance_files[monthly_file] = plugin.DownloadResult(plugin.DownloadStatus.CACHED, monthly_file)
                    except Exception as exception:
                        self.print_log("Unexpected error processing balances dataframe", exception=exception)
                else:
                    pass
            else:
                balance_files[monthly_file] = plugin.DownloadResult(plugin.DownloadStatus.CACHED, monthly_file)
            for file_name in self.file_list(self.local_cache, "Redbark_Balances"):
                if file_name not in balance_files:
                    balance_files[file_name] = plugin.DownloadResult(plugin.DownloadStatus.CACHED, file_name)
            new_data = plugin.config.force_reprocessing or (
                    all(s.status != plugin.DownloadStatus.FAILED for s in balance_files.values()) and any(s.status == plugin.DownloadStatus.DOWNLOADED for s in balance_files.values()))
        if plugin.config.force_reprocessing:
            balance_files = {f: plugin.DownloadResult(plugin.DownloadStatus.DOWNLOADED, f) for f in self.file_list(self.local_cache, "Redbark_Balances")}
            new_data = len(balance_files) > 0
        self.print_log(f"Files downloaded or cached [{len(balance_files)}] files", started=started_time)

        # Process balance data
        started_time = time.time()
        for file_name in sorted(balance_files):
            if balance_files[file_name].status != plugin.DownloadStatus.FAILED:
                if plugin.config.force_reprocessing or balance_files[file_name].status == plugin.DownloadStatus.DOWNLOADED:
                    try:
                        monthly_df = self.csv_read(file_name, schema=BALANCES_SCHEMA)
                        balances_df = pl.concat([balances_df, monthly_df], how="diagonal")
                    except Exception as exception:
                        self.print_log(f"Unexpected error reading [{file_name}]", exception=exception)
        if len(balances_df) > 0:
            balances_df = balances_df.sort(["Date", "Time", "Account Name"])
        dataframe_print(self.name, balances_df, print_label="Balances", print_verb="collected", started=started_time)

        # State checkpoint boundary
        if new_data:
            try:
                def _aggregate_function(_data_df):
                    keep_cols = [c for c in BALANCES_SCHEMA.keys() if c in _data_df.columns]
                    return _data_df.select(keep_cols).with_columns(cs.float().round(2))

                # Checkpoint the data
                balances_delta_df, balances_current_df, _ = self.state_cache(balances_df, _aggregate_function, key_columns=["Date", "Time", "Account Name"])

                # Sheet upload
                started_time = time.time()
                if len(balances_delta_df):
                    # TODO
                    self.sheet_download(self.remote_repos.sheet_balances, "Bank", sheet_name="Balances")

                    # TODO
                    balances_current_df = balances_current_df.sort(["Date", "Time", "Account Name"], descending=True).with_columns(pl.col("Date").cast(pl.Utf8))
                    self.sheet_upload(balances_current_df, self.remote_repos.sheet_balances, workbook_name="Bank", sheet_name="Balances", add_filter=True)

                self.print_log("Upload complete", started=started_time)


            except Exception as exception:
                self.print_log("Unexpected error processing balances data", exception=exception)
        else:
            self.print_log("No new data found")
        self.counter_write()

    def __init__(self):
        super().__init__("Balances", Balances._repos)
