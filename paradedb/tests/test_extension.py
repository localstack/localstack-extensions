import boto3
import psycopg2
from localstack.utils.strings import short_uid


# Connection details for ParadeDB
# Connect through LocalStack gateway with TCP proxying
HOST = "paradedb.localhost.localstack.cloud"
PORT = 4566
USER = "myuser"
PASSWORD = "mypassword"
DATABASE = "mydatabase"


def get_connection():
    """Create a connection to ParadeDB."""
    return psycopg2.connect(
        host=HOST,
        port=PORT,
        user=USER,
        password=PASSWORD,
        database=DATABASE,
    )


def test_connect_to_paradedb():
    """Test basic connection to ParadeDB."""
    conn = get_connection()
    cursor = conn.cursor()

    # Check PostgreSQL version
    cursor.execute("SELECT version();")
    version = cursor.fetchone()[0]
    assert "PostgreSQL" in version

    cursor.close()
    conn.close()


def test_paradedb_quickstart():
    """Test some of ParadeDB's quickstart examples."""
    conn = get_connection()
    cursor = conn.cursor()

    table_name = f"mock_items_{short_uid()}"
    index_name = f"{table_name}_idx"

    try:
        # Load sample data
        cursor.execute(f"""
            CALL paradedb.create_bm25_test_table(
                schema_name => 'public',
                table_name => '{table_name}'
            );
        """)

        # Create search index
        cursor.execute(f"""
            CREATE INDEX search_idx ON {table_name}
            USING bm25 (id, description, category, rating, in_stock, created_at, metadata, weight_range)
            WITH (key_field='id');
        """)

        cursor.execute(f"""
            SELECT description, rating, category
              FROM {table_name}
             LIMIT 3;
        """)
        results = cursor.fetchall()
        assert results == [
            ("Ergonomic metal keyboard", 4, "Electronics"),
            ("Plastic Keyboard", 4, "Electronics"),
            ("Sleek running shoes", 5, "Footwear"),
        ]

        # Match conjunction
        cursor.execute(f"""
            SELECT description, rating, category
            FROM {table_name}
            WHERE description &&& 'running shoes' AND rating > 2
            ORDER BY rating
            LIMIT 5;
        """)
        results = cursor.fetchall()
        assert results == [("Sleek running shoes", 5, "Footwear")]

        # BM25 scoring
        cursor.execute(f"""
            SELECT description, pdb.score(id)
            FROM {table_name}
            WHERE description ||| 'running shoes' AND rating > 2
            ORDER BY score DESC
            LIMIT 5;
        """)
        results = cursor.fetchall()
        assert results == [
            ("Sleek running shoes", 6.817111),
            ("Generic shoes", 3.8772602),
            ("White jogging shoes", 3.4849067),
        ]
    finally:
        # Cleanup - drop index first, then table
        cursor.execute(f"DROP INDEX IF EXISTS {index_name};")
        cursor.execute(f"DROP TABLE IF EXISTS {table_name};")
        conn.commit()
        cursor.close()
        conn.close()


def test_mixed_tcp_and_http_traffic():
    """
    Test that mixed TCP (ParadeDB) and HTTP (AWS) traffic works correctly.

    This verifies that the ParadeDB extension only intercepts PostgreSQL wire
    protocol connections and doesn't interfere with regular HTTP-based AWS
    API requests to LocalStack.
    """
    # First, verify ParadeDB TCP connection works
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 as test_value;")
    result = cursor.fetchone()
    assert result[0] == 1, "ParadeDB TCP connection should work"
    cursor.close()
    conn.close()

    # Now verify AWS HTTP requests still work (S3 and STS)
    # These should NOT be intercepted by the ParadeDB extension
    endpoint_url = f"http://localhost:{PORT}"

    # Test S3 HTTP requests
    s3_client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
    )

    bucket_name = f"test-bucket-{short_uid()}"
    s3_client.create_bucket(Bucket=bucket_name)

    # List buckets to verify HTTP API is working
    buckets = s3_client.list_buckets()
    bucket_names = [b["Name"] for b in buckets["Buckets"]]
    assert bucket_name in bucket_names, "S3 HTTP API should work alongside ParadeDB TCP"

    # Put and get an object
    test_key = "test-object.txt"
    test_content = b"Hello from mixed TCP/HTTP test!"
    s3_client.put_object(Bucket=bucket_name, Key=test_key, Body=test_content)
    response = s3_client.get_object(Bucket=bucket_name, Key=test_key)
    retrieved_content = response["Body"].read()
    assert retrieved_content == test_content, "S3 object operations should work"

    # Clean up S3
    s3_client.delete_object(Bucket=bucket_name, Key=test_key)
    s3_client.delete_bucket(Bucket=bucket_name)

    # Test STS HTTP requests
    sts_client = boto3.client(
        "sts",
        endpoint_url=endpoint_url,
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
    )

    caller_identity = sts_client.get_caller_identity()
    assert "Account" in caller_identity, (
        "STS HTTP API should work alongside ParadeDB TCP"
    )
    assert "Arn" in caller_identity, "STS should return valid caller identity"

    # Finally, verify ParadeDB still works after HTTP requests
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 'tcp_works_after_http' as verification;")
    result = cursor.fetchone()
    assert result[0] == "tcp_works_after_http", (
        "ParadeDB should still work after HTTP requests"
    )
    cursor.close()
    conn.close()
