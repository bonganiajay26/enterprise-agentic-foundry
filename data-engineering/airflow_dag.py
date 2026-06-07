"""
Data Engineering Pipeline — Apache Airflow DAG Template
Universal Platform — Production-ready with retry logic, alerting, data quality checks,
SLA monitoring, and Great Expectations validation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.providers.common.sql.operators.sql import SQLCheckOperator
from airflow.utils.email import send_email
from airflow.utils.trigger_rule import TriggerRule

log = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────
DAG_ID = "universal_data_pipeline"
SCHEDULE = "0 2 * * *"          # Daily at 02:00 UTC
PIPELINE_OWNER = "data-team"
SLA_MINUTES = 120                # Alert if pipeline doesn't complete in 2h
MAX_ACTIVE_RUNS = 1
CATCHUP = False

# Read sensitive config from Airflow Variables (backed by Key Vault in production)
SOURCE_CONN_ID = "source_postgres"
DEST_CONN_ID = "destination_snowflake"
S3_BUCKET = Variable.get("data_lake_bucket", default_var="your-data-lake-bucket")
GREAT_EXPECTATIONS_CONTEXT = Variable.get("ge_context_root", default_var="/opt/airflow/great_expectations")


def on_failure_callback(context: dict[str, Any]) -> None:
    """Notify on pipeline failure via Slack and email."""
    task_instance = context["task_instance"]
    dag_id = context["dag"].dag_id
    task_id = task_instance.task_id
    execution_date = context["execution_date"]
    log_url = task_instance.log_url

    log.error("Pipeline failed: %s.%s on %s", dag_id, task_id, execution_date)

    # Slack notification (requires slack_http Airflow connection)
    try:
        from airflow.providers.slack.operators.slack_webhook import SlackWebhookOperator
        slack = SlackWebhookOperator(
            task_id="slack_notify",
            slack_webhook_conn_id="slack_webhook",
            message=f":red_circle: *Pipeline Failed*\n"
                    f"DAG: `{dag_id}`\nTask: `{task_id}`\nDate: {execution_date}\n"
                    f"<{log_url}|View Logs>",
        )
        slack.execute(context)
    except Exception as e:
        log.warning("Slack notification failed: %s", e)


def on_sla_miss_callback(dag, task_list, blocking_task_list, slas, blocking_tis) -> None:
    """Alert when pipeline SLA is missed."""
    log.warning("SLA missed for DAG %s. Tasks: %s", dag.dag_id, task_list)


# ─── Task Functions ────────────────────────────────────────────────────
def extract_data(**context) -> dict:
    """Extract data from source system."""
    from airflow.providers.postgres.hooks.postgres import PostgresHook

    log.info("Starting extraction for %s", context["ds"])
    hook = PostgresHook(postgres_conn_id=SOURCE_CONN_ID)

    query = """
    SELECT *
    FROM orders
    WHERE created_at >= %(start_date)s
      AND created_at < %(end_date)s
    """
    df = hook.get_pandas_df(
        query,
        parameters={
            "start_date": context["data_interval_start"],
            "end_date": context["data_interval_end"],
        },
    )

    log.info("Extracted %d records", len(df))

    # Push row count to XCom for downstream validation
    context["ti"].xcom_push(key="extracted_row_count", value=len(df))

    # Write to intermediate storage (S3/Azure Blob)
    output_path = f"s3://{S3_BUCKET}/raw/orders/{context['ds']}/data.parquet"
    df.to_parquet(output_path, index=False, engine="pyarrow", compression="snappy")

    log.info("Saved to %s", output_path)
    return {"path": output_path, "rows": len(df)}


def validate_data(**context) -> None:
    """Run Great Expectations data quality checks."""
    try:
        import great_expectations as gx

        context_ge = gx.get_context(context_root_dir=GREAT_EXPECTATIONS_CONTEXT)
        result = context_ge.run_checkpoint(checkpoint_name="orders_checkpoint")

        if not result["success"]:
            failed = [v for v in result["run_results"].values() if not v["success"]]
            raise ValueError(f"Data quality checks FAILED: {len(failed)} failures")

        log.info("All data quality checks passed")
    except ImportError:
        log.warning("great-expectations not installed — skipping validation")


def transform_data(**context) -> dict:
    """Transform and enrich data."""
    import pandas as pd

    input_path = context["ti"].xcom_pull(task_ids="extract", key="path")

    df = pd.read_parquet(input_path)

    # Business transformations
    df["order_date"] = pd.to_datetime(df["created_at"]).dt.date
    df["order_month"] = pd.to_datetime(df["created_at"]).dt.to_period("M").astype(str)
    df["total_with_tax"] = df["total_amount"] * 1.1
    df["is_large_order"] = df["total_amount"] > 1000

    output_path = f"s3://{S3_BUCKET}/transformed/orders/{context['ds']}/data.parquet"
    df.to_parquet(output_path, index=False)

    context["ti"].xcom_push(key="transformed_row_count", value=len(df))
    return {"path": output_path, "rows": len(df)}


def load_to_warehouse(**context) -> None:
    """Load transformed data to data warehouse."""
    from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook

    input_path = context["ti"].xcom_pull(task_ids="transform", key="path")
    rows = context["ti"].xcom_pull(task_ids="transform", key="transformed_row_count")

    hook = SnowflakeHook(snowflake_conn_id=DEST_CONN_ID)

    # COPY INTO command for efficient bulk loading
    hook.run(f"""
    COPY INTO ANALYTICS.ORDERS
    FROM '{input_path}'
    FILE_FORMAT = (TYPE = PARQUET)
    MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
    PURGE = FALSE;
    """)

    log.info("Loaded %d rows to ANALYTICS.ORDERS", rows)


def record_metrics(**context) -> None:
    """Record pipeline metrics to Prometheus pushgateway."""
    try:
        from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

        registry = CollectorRegistry()
        g = Gauge("data_pipeline_rows_processed", "Rows processed by pipeline",
                  ["dag_id", "execution_date"], registry=registry)
        g.labels(
            dag_id=DAG_ID,
            execution_date=context["ds"],
        ).set(context["ti"].xcom_pull(task_ids="transform", key="transformed_row_count") or 0)

        pushgateway_url = Variable.get("prometheus_pushgateway", default_var="http://pushgateway:9091")
        push_to_gateway(pushgateway_url, job="airflow_pipeline", registry=registry)
    except Exception as e:
        log.warning("Metrics push failed (non-critical): %s", e)


# ─── DAG Definition ────────────────────────────────────────────────────
default_args = {
    "owner": PIPELINE_OWNER,
    "depends_on_past": False,
    "email": ["data-alerts@your-org.com"],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
    "on_failure_callback": on_failure_callback,
    "sla": timedelta(minutes=SLA_MINUTES),
}

with DAG(
    dag_id=DAG_ID,
    description="Universal data engineering pipeline: extract → validate → transform → load",
    schedule=SCHEDULE,
    start_date=datetime(2024, 1, 1),
    catchup=CATCHUP,
    max_active_runs=MAX_ACTIVE_RUNS,
    default_args=default_args,
    on_sla_miss_callback=on_sla_miss_callback,
    tags=["data-engineering", "orders", "daily"],
    doc_md=__doc__,
) as dag:

    start = EmptyOperator(task_id="start")

    extract = PythonOperator(
        task_id="extract",
        python_callable=extract_data,
    )

    validate = PythonOperator(
        task_id="validate_quality",
        python_callable=validate_data,
    )

    transform = PythonOperator(
        task_id="transform",
        python_callable=transform_data,
    )

    row_count_check = SQLCheckOperator(
        task_id="row_count_check",
        conn_id=DEST_CONN_ID,
        sql="""
        SELECT COUNT(*) > 0
        FROM ANALYTICS.ORDERS
        WHERE order_date = '{{ ds }}'
        """,
    )

    load = PythonOperator(
        task_id="load",
        python_callable=load_to_warehouse,
    )

    metrics = PythonOperator(
        task_id="record_metrics",
        python_callable=record_metrics,
        trigger_rule=TriggerRule.ALL_DONE,
    )

    end = EmptyOperator(task_id="end")

    # ─── DAG Flow ────────────────────────────────────────────────────
    start >> extract >> validate >> transform >> load >> row_count_check >> metrics >> end
