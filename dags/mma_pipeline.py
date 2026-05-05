"""
MMA Pipeline DAG — runs weekly every Monday 06:00 UTC.
Flow: scrape → MinIO → load_events → load_rounds → dbt → verify
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

sys.path.insert(0, "/opt/airflow")

default_args = {
    "owner":            "mma-pipeline",
    "retries":          2,
    "retry_delay":      timedelta(minutes=5),
    "email_on_failure": False,
}


def task_scrape(**context):
    from ingestion.main import scrape_all
    scrape_all(limit=5, fights_only=False, use_minio=True)


def task_load_events(**context):
    import boto3
    import json
    from botocore.client import Config
    from warehouse.loader.load_events import load_event_file
    from warehouse.loader.db import get_conn

    client = boto3.client(
        "s3",
        endpoint_url=os.environ["MINIO_ENDPOINT"],
        aws_access_key_id=os.environ["MINIO_ACCESS_KEY"],
        aws_secret_access_key=os.environ["MINIO_SECRET_KEY"],
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )
    bucket    = os.environ["MINIO_BUCKET"]
    paginator = client.get_paginator("list_objects_v2")
    conn      = get_conn()
    loaded = skipped = 0

    for page in paginator.paginate(Bucket=bucket, Prefix="events/"):
        for obj in page.get("Contents", []):
            body = client.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read()
            tmp  = Path(f"/tmp/evt_{obj['Key'].split('/')[-1]}")
            tmp.write_bytes(body)
            l, s = load_event_file(conn, tmp)
            loaded += l
            skipped += s
            tmp.unlink()

    conn.close()
    print(f"Events: {loaded} fights loaded, {skipped} skipped")


def task_load_rounds(**context):
    import boto3
    from botocore.client import Config
    from warehouse.loader.load_rounds import load_fight_file
    from warehouse.loader.db import get_conn

    client = boto3.client(
        "s3",
        endpoint_url=os.environ["MINIO_ENDPOINT"],
        aws_access_key_id=os.environ["MINIO_ACCESS_KEY"],
        aws_secret_access_key=os.environ["MINIO_SECRET_KEY"],
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )
    bucket    = os.environ["MINIO_BUCKET"]
    paginator = client.get_paginator("list_objects_v2")
    conn      = get_conn()
    total     = 0

    for page in paginator.paginate(Bucket=bucket, Prefix="fights/"):
        for obj in page.get("Contents", []):
            body = client.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read()
            tmp  = Path(f"/tmp/fgt_{obj['Key'].split('/')[-1]}")
            tmp.write_bytes(body)
            inserted, _ = load_fight_file(conn, tmp)
            total += inserted
            tmp.unlink()

    conn.close()
    print(f"Rounds inserted: {total}")


def task_verify(**context):
    from warehouse.loader.db import get_conn
    conn = get_conn()
    with conn.cursor() as cur:
        for t in ["dim_event", "dim_fighter", "fact_fight", "fact_fight_round"]:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            print(f"{t}: {cur.fetchone()[0]:,} rows")
    conn.close()


with DAG(
    dag_id="mma_weekly_pipeline",
    default_args=default_args,
    description="Scrape UFC stats → MinIO → PostgreSQL → dbt",
    schedule_interval="0 6 * * 1",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["mma", "etl"],
) as dag:

    scrape      = PythonOperator(task_id="scrape_and_upload", python_callable=task_scrape)
    load_events = PythonOperator(task_id="load_events",       python_callable=task_load_events)
    load_rounds = PythonOperator(task_id="load_rounds",       python_callable=task_load_rounds)
    run_dbt     = BashOperator(
        task_id="run_dbt",
        bash_command="cd /opt/airflow/transforms && dbt run --profiles-dir . && dbt test --profiles-dir ."
    )
    verify      = PythonOperator(task_id="verify", python_callable=task_verify)

    scrape >> load_events >> load_rounds >> run_dbt >> verify
