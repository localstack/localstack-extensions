import uuid

import boto3
import psycopg2
import psycopg2.extras


def short_uid() -> str:
    return str(uuid.uuid4())[:8]


# Connection details for CockroachDB
# Connect through LocalStack gateway with TCP proxying
HOST = "cockroachdb.localhost.localstack.cloud"
PORT = 4566
USER = "root"
DATABASE = "defaultdb"


def get_connection():
    """Create a psycopg2 connection to CockroachDB."""
    return psycopg2.connect(
        host=HOST,
        port=PORT,
        user=USER,
        database=DATABASE,
        sslmode="disable",
    )


def test_connect_to_cockroachdb():
    """Test basic connection to CockroachDB and verify it's actually CockroachDB."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        assert "CockroachDB" in version, f"Expected CockroachDB version, got: {version}"
        cursor.close()
    finally:
        conn.close()


def test_cockroachdb_crud():
    """Test basic CRUD operations: CREATE TABLE, INSERT, SELECT, DROP TABLE."""
    conn = get_connection()
    table = f"test_items_{short_uid()}"
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"CREATE TABLE {table} (id INT PRIMARY KEY, name STRING NOT NULL)"
        )
        cursor.execute(
            f"INSERT INTO {table} (id, name) VALUES (1, 'hello'), (2, 'world')"
        )
        cursor.execute(f"SELECT id, name FROM {table} ORDER BY id")
        rows = cursor.fetchall()

        assert len(rows) == 2
        assert rows[0][0] == 1
        assert rows[0][1] == "hello"
        assert rows[1][0] == 2
        assert rows[1][1] == "world"

        cursor.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()
        cursor.close()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def test_mixed_tcp_and_http_traffic():
    """
    Test that mixed TCP (CockroachDB) and HTTP (AWS) traffic works correctly.

    Verifies that the CockroachDB extension only intercepts PostgreSQL wire
    protocol connections and doesn't interfere with regular HTTP-based AWS
    API requests to LocalStack.
    """
    # Verify CockroachDB TCP connection works
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 AS test_value")
        assert cursor.fetchone()[0] == 1, "CockroachDB TCP connection should work"
        cursor.close()
    finally:
        conn.close()

    # Verify AWS HTTP requests still work (S3)
    endpoint_url = f"http://localhost:{PORT}"

    s3_client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
    )

    bucket_name = f"test-bucket-{short_uid()}"
    s3_client.create_bucket(Bucket=bucket_name)

    bucket_names = [b["Name"] for b in s3_client.list_buckets()["Buckets"]]
    assert bucket_name in bucket_names, "S3 HTTP API should work alongside CockroachDB TCP"

    test_key = "test-object.txt"
    test_content = b"Hello from mixed TCP/HTTP test!"
    s3_client.put_object(Bucket=bucket_name, Key=test_key, Body=test_content)
    response = s3_client.get_object(Bucket=bucket_name, Key=test_key)
    assert response["Body"].read() == test_content, "S3 object operations should work"

    s3_client.delete_object(Bucket=bucket_name, Key=test_key)
    s3_client.delete_bucket(Bucket=bucket_name)

    # Verify CockroachDB still works after HTTP requests
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 'tcp_works_after_http' AS verification")
        assert cursor.fetchone()[0] == "tcp_works_after_http"
        cursor.close()
    finally:
        conn.close()
