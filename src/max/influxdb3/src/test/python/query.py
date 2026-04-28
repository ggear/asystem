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
    "SHOW COLUMNS FROM supervisor",
    """
    SELECT DISTINCT host
    FROM supervisor
    """,
    """
    SELECT COUNT(used_processor)
    FROM supervisor""",
    """
    SELECT DISTINCT
    ON (host) host, time, used_processor_trend
    FROM supervisor
    ORDER BY host, time DESC""",
    """
    SELECT DISTINCT
    ON (host) host, time + INTERVAL '8 hours' AS time, used_processor, used_processor_trend
    FROM supervisor
    ORDER BY host, time DESC
    """,
    """
    SELECT time + INTERVAL '8 hours' AS time, host, used_processor, used_processor_trend
    FROM supervisor
    WHERE time >= CURRENT_TIMESTAMP - INTERVAL '10 seconds'
    ORDER BY time DESC
    """,
    """
    SELECT DATE_TRUNC('day', time + INTERVAL '8 hours') AS bin,
           host                                         AS host,
           AVG(used_processor)                            AS used_processor,
           AVG(used_processor_trend)                              AS used_processor_trend
    FROM supervisor
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
