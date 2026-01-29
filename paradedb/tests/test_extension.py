import psycopg2
from localstack.utils.strings import short_uid


# Connection details for ParadeDB
HOST = "localhost"
PORT = 5432
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
