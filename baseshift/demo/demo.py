"""
Baseshift on LocalStack - end-to-end demo.

Walks through the flow of masked production data, fully local:

  source    - "production" PostgreSQL database in LocalStack RDS, seeded with PII
  snapshot  - create a masked Docker snapshot of the database, pushed to LocalStack ECR
  clone     - start a clone from the snapshot image, via the extension's clones API
  pipeline  - export the clone data to S3, and load it into Snowflake (LocalStack Snowflake emulator)
  compare   - show the same record in the source, the clone, and Snowflake side by side

Note: the `snapshot` step is a stand-in for the Baseshift replication server (connector + masking +
snapshot image creation), until the demo can run the Baseshift self-hosted components. Its masking
rules are deliberately simple, and only serve to illustrate the flow.

Requires LocalStack with the Snowflake emulator (e.g., `lstk` with `type = "snowflake"`) and the
Baseshift extension installed.
"""

import argparse
import csv
import hashlib
import io
import os
import subprocess
import sys
import tempfile
import time

import boto3
import psycopg2
import requests
import snowflake.connector

LOCALSTACK_HOST = os.environ.get("LOCALSTACK_HOST", "localhost.localstack.cloud:4566")
ENDPOINT_URL = f"http://{LOCALSTACK_HOST}"
GATEWAY_HOST, GATEWAY_PORT = LOCALSTACK_HOST.split(":")
CLONES_API = f"http://baseshift.{LOCALSTACK_HOST}/clones"

DB_INSTANCE = "prod-db"
DB_NAME = "shop"
DB_USER = "admin"
DB_PASSWORD = "prod-secret-123"
SNAPSHOT_REPO = "baseshift/shop-dub"
CLONE_NAME = "shop-dev"
EXPORT_BUCKET = "shop-analytics-export"
CUSTOMER_ID = 1

CUSTOMERS = [
    (
        "Jane Roe",
        "jane.roe@gmail.com",
        "078-05-1120",
        "+1 415 555 0142",
        "221B Baker Street, London",
    ),
    (
        "Max Mustermann",
        "max.mustermann@web.de",
        "219-09-9999",
        "+49 30 1234567",
        "Unter den Linden 1, Berlin",
    ),
    (
        "Priya Patel",
        "priya.patel@outlook.com",
        "457-55-5462",
        "+1 212 555 0199",
        "350 5th Ave, New York",
    ),
    (
        "Kenji Sato",
        "kenji.sato@yahoo.co.jp",
        "123-45-6789",
        "+81 3 1234 5678",
        "1-1 Chiyoda, Tokyo",
    ),
]
ORDERS = [(1, 129.99), (1, 42.50), (2, 18.00), (3, 999.00), (3, 12.75), (4, 64.20)]


def aws_client(service: str):
    return boto3.client(
        service,
        endpoint_url=ENDPOINT_URL,
        region_name="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


def log(message: str):
    print(f"==> {message}", flush=True)


# ---------- source: "production" database in RDS ----------


def get_source_endpoint() -> tuple[str, int]:
    instance = aws_client("rds").describe_db_instances(DBInstanceIdentifier=DB_INSTANCE)
    endpoint = instance["DBInstances"][0]["Endpoint"]
    return endpoint["Address"], endpoint["Port"]


def connect_source():
    host, port = get_source_endpoint()
    return psycopg2.connect(
        host=host, port=port, user=DB_USER, password=DB_PASSWORD, dbname=DB_NAME
    )


def wait_for_db_instance():
    rds = aws_client("rds")
    for _ in range(100):
        status = rds.describe_db_instances(DBInstanceIdentifier=DB_INSTANCE)[
            "DBInstances"
        ][0]
        if status["DBInstanceStatus"] == "available":
            return
        time.sleep(3)
    raise TimeoutError(f"RDS instance {DB_INSTANCE} did not become available")


def retry_connect(connect_fn, retries: int = 20):
    for _ in range(retries - 1):
        try:
            return connect_fn()
        except psycopg2.OperationalError:
            time.sleep(2)
    return connect_fn()


def cmd_source(_args):
    rds = aws_client("rds")
    log(f"Creating 'production' RDS PostgreSQL instance {DB_INSTANCE}")
    rds.create_db_instance(
        DBInstanceIdentifier=DB_INSTANCE,
        Engine="postgres",
        EngineVersion="17",
        DBInstanceClass="db.t3.micro",
        MasterUsername=DB_USER,
        MasterUserPassword=DB_PASSWORD,
        DBName=DB_NAME,
        AllocatedStorage=20,
    )
    wait_for_db_instance()

    # Baseshift uses logical replication for continuous snapshots. On AWS, this is enabled via the
    # `rds.logical_replication` parameter - LocalStack RDS does not apply it (yet), hence we set the
    # WAL level directly (the RDS master user is a superuser in LocalStack) and reboot the instance.
    log("Enabling logical replication (wal_level=logical)")
    conn = retry_connect(connect_source)
    conn.autocommit = True
    conn.cursor().execute("ALTER SYSTEM SET wal_level = 'logical'")
    conn.close()
    rds.reboot_db_instance(DBInstanceIdentifier=DB_INSTANCE)
    time.sleep(3)
    wait_for_db_instance()

    log("Seeding customer data (with PII) and orders")
    with retry_connect(connect_source) as conn, conn.cursor() as cursor:
        cursor.execute("SHOW wal_level")
        print(f"    wal_level: {cursor.fetchone()[0]}")
        cursor.execute(
            """
            CREATE TABLE customers (
                id SERIAL PRIMARY KEY, name TEXT, email TEXT, ssn TEXT, phone TEXT, address TEXT
            );
            CREATE TABLE orders (
                id SERIAL PRIMARY KEY, customer_id INT REFERENCES customers(id), amount NUMERIC(10, 2)
            );
            """
        )
        cursor.executemany(
            "INSERT INTO customers (name, email, ssn, phone, address) VALUES (%s, %s, %s, %s, %s)",
            CUSTOMERS,
        )
        cursor.executemany(
            "INSERT INTO orders (customer_id, amount) VALUES (%s, %s)", ORDERS
        )
    host, port = get_source_endpoint()
    print(f"    source database: postgresql://{DB_USER}@{host}:{port}/{DB_NAME}")


# ---------- snapshot: masked Docker snapshot in ECR (stand-in for the Baseshift replication server) ----------


def mask_value(column: str, value: str) -> str:
    """Deterministic masking - the same input always yields the same output, preserving joins."""
    digest = hashlib.sha256(value.encode()).hexdigest()
    if column == "name":
        return f"Customer {digest[:6]}"
    if column == "email":
        return f"user-{digest[:8]}@example.com"
    if column == "ssn":
        return f"***-**-{value[-4:]}"
    if column == "phone":
        return f"+1 555 {int(digest[:6], 16) % 10000000:07d}"
    if column == "address":
        return f"{int(digest[:4], 16) % 999 + 1} Masked Street"
    return value


def cmd_snapshot(_args):
    log(
        "Reading source data and applying masking policy (name, email, ssn, phone, address)"
    )
    with connect_source() as conn, conn.cursor() as cursor:
        cursor.execute(
            "SELECT id, name, email, ssn, phone, address FROM customers ORDER BY id"
        )
        customers = cursor.fetchall()
        cursor.execute("SELECT id, customer_id, amount FROM orders ORDER BY id")
        orders = cursor.fetchall()
    columns = ["name", "email", "ssn", "phone", "address"]
    masked = [
        (
            row[0],
            *[mask_value(col, val) for col, val in zip(columns, row[1:], strict=True)],
        )
        for row in customers
    ]

    def sql_literal(value) -> str:
        return "'" + str(value).replace("'", "''") + "'"

    init_sql = [
        "CREATE TABLE customers (id INT PRIMARY KEY, name TEXT, email TEXT, ssn TEXT, phone TEXT, address TEXT);",
        "CREATE TABLE orders (id INT PRIMARY KEY, customer_id INT REFERENCES customers(id), amount NUMERIC(10, 2));",
    ]
    init_sql += [
        f"INSERT INTO customers VALUES ({', '.join(map(sql_literal, row))});"
        for row in masked
    ]
    init_sql += [
        f"INSERT INTO orders VALUES ({', '.join(map(sql_literal, row))});"
        for row in orders
    ]

    ecr = aws_client("ecr")
    try:
        repo = ecr.create_repository(repositoryName=SNAPSHOT_REPO)["repository"]
    except ecr.exceptions.RepositoryAlreadyExistsException:
        repo = ecr.describe_repositories(repositoryNames=[SNAPSHOT_REPO])[
            "repositories"
        ][0]
    image = f"{repo['repositoryUri']}:latest"

    log(f"Building snapshot image {image}")
    with tempfile.TemporaryDirectory() as build_dir:
        with open(os.path.join(build_dir, "init.sql"), "w") as f:
            f.write("\n".join(init_sql) + "\n")
        with open(os.path.join(build_dir, "Dockerfile"), "w") as f:
            f.write(
                "FROM postgres:17\n"
                # like Baseshift local clones, the snapshot accepts connections without a password
                f"ENV POSTGRES_HOST_AUTH_METHOD=trust POSTGRES_DB={DB_NAME}\n"
                "COPY init.sql /docker-entrypoint-initdb.d/\n"
            )
        subprocess.run(["docker", "build", "-q", "-t", image, build_dir], check=True)
    log("Pushing snapshot image to LocalStack ECR")
    subprocess.run(["docker", "push", "-q", image], check=True)
    # remove the local tag, so that the clone is actually pulled from the registry
    subprocess.run(["docker", "rmi", image], check=True, capture_output=True)
    print(f"    snapshot image: {image}")


# ---------- clone: start a clone from the snapshot, via the extension ----------


def get_clone() -> dict:
    return requests.get(f"{CLONES_API}/{CLONE_NAME}").json()


def connect_clone():
    clone = get_clone()
    host, port = clone["endpoints"][-1].split(":")
    return psycopg2.connect(host=host, port=int(port), user="postgres", dbname=DB_NAME)


def cmd_clone(_args):
    image = aws_client("ecr").describe_repositories(repositoryNames=[SNAPSHOT_REPO])[
        "repositories"
    ][0]
    image = f"{image['repositoryUri']}:latest"
    log(f"Starting clone {CLONE_NAME} from {image}")
    response = requests.post(CLONES_API, json={"name": CLONE_NAME, "image": image})
    if response.status_code == 409:
        print(f"    clone {CLONE_NAME} already exists")
    else:
        response.raise_for_status()
    clone = get_clone()
    for _ in range(90):
        clone = get_clone()
        if clone["status"] in ("running", "failed"):
            break
        time.sleep(2)
    print(
        f"    clone status: {clone['status']}, endpoints: {', '.join(clone['endpoints'])}"
    )
    if clone["status"] != "running":
        sys.exit(f"Clone failed to start: {clone.get('error')}")


# ---------- pipeline: clone -> S3 -> Snowflake ----------


def connect_snowflake():
    return snowflake.connector.connect(
        user="test",
        password="test",
        account="test",
        database="test",
        schema="public",
        host=f"snowflake.{GATEWAY_HOST}",
        port=int(GATEWAY_PORT),
        protocol="http",
    )


def cmd_pipeline(_args):
    s3 = aws_client("s3")
    try:
        s3.create_bucket(Bucket=EXPORT_BUCKET)
    except s3.exceptions.BucketAlreadyOwnedByYou:
        pass

    log("Exporting tables from the clone to S3 (CSV)")
    with retry_connect(connect_clone) as conn, conn.cursor() as cursor:
        for table in ("customers", "orders"):
            cursor.execute(f"SELECT * FROM {table} ORDER BY id")
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow([col.name for col in cursor.description])
            writer.writerows(cursor.fetchall())
            s3.put_object(
                Bucket=EXPORT_BUCKET, Key=f"{table}/data.csv", Body=buffer.getvalue()
            )
            print(f"    s3://{EXPORT_BUCKET}/{table}/data.csv")

    log("Loading the data into Snowflake (S3 stage + COPY INTO)")
    conn = connect_snowflake()
    cursor = conn.cursor()
    statements = [
        "CREATE OR REPLACE TABLE customers (id INT, name TEXT, email TEXT, ssn TEXT, phone TEXT, address TEXT)",
        "CREATE OR REPLACE TABLE orders (id INT, customer_id INT, amount NUMBER(10, 2))",
    ]
    for table in ("customers", "orders"):
        statements += [
            f"CREATE OR REPLACE STAGE {table}_stage URL='s3://{EXPORT_BUCKET}/{table}/' "
            "CREDENTIALS=(AWS_KEY_ID='test' AWS_SECRET_KEY='test')",
            f"COPY INTO {table} FROM @{table}_stage FILE_FORMAT=(TYPE=CSV SKIP_HEADER=1)",
        ]
    for statement in statements:
        cursor.execute(statement)
    cursor.execute(
        "SELECT c.id, c.name, COUNT(o.id), SUM(o.amount) FROM customers c "
        "JOIN orders o ON o.customer_id = c.id GROUP BY c.id, c.name ORDER BY c.id"
    )
    print("    revenue per customer (Snowflake):")
    for row in cursor.fetchall():
        print(f"      {row[0]}  {row[1]:<18} orders={row[2]}  total={row[3]}")
    conn.close()


# ---------- compare: the same record at every stage ----------


def cmd_compare(_args):
    query = f"SELECT name, email, ssn, phone, address FROM customers WHERE id = {CUSTOMER_ID}"
    with connect_source() as conn, conn.cursor() as cursor:
        cursor.execute(query)
        source = cursor.fetchone()
    with connect_clone() as conn, conn.cursor() as cursor:
        cursor.execute(query)
        clone = cursor.fetchone()
    sf_conn = connect_snowflake()
    snowflake_row = sf_conn.cursor().execute(query).fetchone()
    sf_conn.close()

    columns = ["name", "email", "ssn", "phone", "address"]
    widths = [8, 28, 28, 28]
    header = ["column", "source (RDS)", "Baseshift clone", "Snowflake"]
    print(f"\nCustomer {CUSTOMER_ID} at every stage of the pipeline:\n")
    print("  ".join(h.ljust(w) for h, w in zip(header, widths, strict=True)))
    print("  ".join("-" * w for w in widths))
    for i, column in enumerate(columns):
        values = [column, source[i], clone[i], snowflake_row[i]]
        print(
            "  ".join(str(v)[:w].ljust(w) for v, w in zip(values, widths, strict=True))
        )
    leaked = [
        c for i, c in enumerate(columns) if source[i] in (clone[i], snowflake_row[i])
    ]
    print()
    if leaked:
        sys.exit(f"PII leaked into downstream stages: {leaked}")
    print("No raw PII values reached the clone or Snowflake.")


def cmd_all(args):
    for step in (cmd_source, cmd_snapshot, cmd_clone, cmd_pipeline, cmd_compare):
        step(args)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = {
        "source": cmd_source,
        "snapshot": cmd_snapshot,
        "clone": cmd_clone,
        "pipeline": cmd_pipeline,
        "compare": cmd_compare,
        "all": cmd_all,
    }
    parser.add_argument("command", choices=commands)
    args = parser.parse_args()
    commands[args.command](args)


if __name__ == "__main__":
    main()
