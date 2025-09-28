import polars as pl
from pyarrow.flight import FlightClient, Ticket, FlightCallOptions
import json
from dotenv import load_dotenv
import os
import time

load_dotenv("../../../.env")

client = FlightClient(
    f"grpc+tcp://{os.getenv('INFLUXDB3_SERVICE_PROD')}:{os.getenv('INFLUXDB3_API_PORT')}")
options = FlightCallOptions(
    headers=[(b"authorization", bytes(f"Bearer {os.getenv('INFLUXDB3_TOKEN_ADMIN')}".encode('utf-8')))])
print("\nExecuting queries:\n")
for query in [
    "SHOW TABLES",
    "SHOW COLUMNS FROM cpu",
    """
    SELECT DISTINCT host
    FROM cpu
    """,
    """
    SELECT COUNT(usage_system)
    FROM cpu""",
    """
    SELECT DISTINCT
    ON (host) host, time, usage_user
    FROM cpu
    ORDER BY host, time DESC""",
    """
    SELECT DISTINCT
    ON (host) host, time + INTERVAL '8 hours' AS time, usage_system, usage_user
    FROM cpu
    ORDER BY host, time DESC
    """,
    """
    SELECT time + INTERVAL '8 hours' AS time, host, usage_system, usage_user
    FROM cpu
    WHERE time >= CURRENT_TIMESTAMP - INTERVAL '10 seconds'
    ORDER BY time DESC
    """,
    """
    SELECT DATE_TRUNC('day', time + INTERVAL '8 hours') AS bin,
           host                                         AS host,
           AVG(usage_system)                            AS usage_system,
           AVG(usage_user)                              AS usage_user
    FROM cpu
    GROUP BY bin, host
    ORDER BY bin DESC
    """
]:
    print(f"\nExecuting query:\n{query}")
    start_time = time.time()
    result = pl.from_arrow(
        client.do_get(Ticket(json.dumps({
            "namespace_name": "host_private",
            "query_type": "sql",
            "sql_query": query
        })), options).read_all()
    )
    execution_time = time.time() - start_time
    print(f"Execution time: {execution_time:.3f} seconds with result:\n")
    print(result)
