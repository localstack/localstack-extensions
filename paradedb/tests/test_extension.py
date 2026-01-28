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


def test_create_table_and_insert():
    """Test creating a table and inserting data."""
    conn = get_connection()
    cursor = conn.cursor()

    table_name = f"test_table_{short_uid()}"

    try:
        # Create table
        cursor.execute(f"""
            CREATE TABLE {table_name} (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT
            );
        """)
        conn.commit()

        # Insert data
        cursor.execute(f"""
            INSERT INTO {table_name} (name, description)
            VALUES ('Product A', 'A great product'),
                   ('Product B', 'Another product'),
                   ('Product C', 'Yet another product');
        """)
        conn.commit()

        # Query data
        cursor.execute(f"SELECT * FROM {table_name} ORDER BY id;")
        results = cursor.fetchall()

        assert len(results) == 3
        assert results[0][1] == "Product A"
        assert results[1][1] == "Product B"
        assert results[2][1] == "Product C"

    finally:
        # Cleanup
        cursor.execute(f"DROP TABLE IF EXISTS {table_name};")
        conn.commit()
        cursor.close()
        conn.close()


def test_paradedb_pg_search_extension():
    """Test ParadeDB's pg_search extension for full-text search using v2 API."""
    conn = get_connection()
    cursor = conn.cursor()

    table_name = f"products_{short_uid()}"
    index_name = f"{table_name}_idx"

    try:
        # Create table
        cursor.execute(f"""
            CREATE TABLE {table_name} (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT
            );
        """)
        conn.commit()

        # Insert sample data
        cursor.execute(f"""
            INSERT INTO {table_name} (name, description) VALUES
            ('Laptop', 'High performance laptop with 16GB RAM and SSD storage'),
            ('Smartphone', 'Latest smartphone with advanced camera features'),
            ('Headphones', 'Wireless noise-canceling headphones for music lovers'),
            ('Tablet', 'Portable tablet with retina display'),
            ('Smartwatch', 'Fitness tracking smartwatch with heart rate monitor');
        """)
        conn.commit()

        # Create BM25 search index using ParadeDB v2 API (CREATE INDEX syntax)
        cursor.execute(f"""
            CREATE INDEX {index_name} ON {table_name}
            USING bm25 (id, name, description)
            WITH (key_field='id');
        """)
        conn.commit()

        # Search for products containing 'wireless' using ||| operator (disjunction/OR)
        cursor.execute(f"""
            SELECT id, name, description
            FROM {table_name}
            WHERE description ||| 'wireless';
        """)
        results = cursor.fetchall()

        assert len(results) >= 1
        assert any("Headphones" in row[1] for row in results)

        # Search for products containing 'laptop' in name or description
        cursor.execute(f"""
            SELECT id, name, description
            FROM {table_name}
            WHERE name ||| 'laptop' OR description ||| 'laptop';
        """)
        results = cursor.fetchall()

        assert len(results) >= 1
        assert any("Laptop" in row[1] for row in results)

    finally:
        # Cleanup - drop index first, then table
        cursor.execute(f"DROP INDEX IF EXISTS {index_name};")
        cursor.execute(f"DROP TABLE IF EXISTS {table_name};")
        conn.commit()
        cursor.close()
        conn.close()


def test_paradedb_search_with_scoring():
    """Test ParadeDB's BM25 search with relevance scoring."""
    conn = get_connection()
    cursor = conn.cursor()

    table_name = f"docs_{short_uid()}"
    index_name = f"{table_name}_idx"

    try:
        # Create table with text content
        cursor.execute(f"""
            CREATE TABLE {table_name} (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT
            );
        """)
        conn.commit()

        # Insert sample documents
        cursor.execute(f"""
            INSERT INTO {table_name} (title, content) VALUES
            ('Introduction to Python', 'Python is a versatile programming language used for web development, data science, and automation.'),
            ('JavaScript Basics', 'JavaScript is essential for front-end web development and can also be used on the server side with Node.js.'),
            ('Database Design', 'Good database design is crucial for application performance and data integrity.'),
            ('Machine Learning 101', 'Machine learning enables computers to learn from data without explicit programming.'),
            ('Cloud Computing', 'Cloud computing provides on-demand access to computing resources over the internet.');
        """)
        conn.commit()

        # Create search index using v2 API
        cursor.execute(f"""
            CREATE INDEX {index_name} ON {table_name}
            USING bm25 (id, title, content)
            WITH (key_field='id');
        """)
        conn.commit()

        # Search for programming-related documents with scoring
        cursor.execute(f"""
            SELECT id, title, pdb.score(id) as score
            FROM {table_name}
            WHERE content ||| 'programming'
            ORDER BY score DESC;
        """)
        results = cursor.fetchall()

        assert len(results) >= 1
        # Python and Machine Learning docs should match
        titles = [row[1] for row in results]
        assert any("Python" in t or "Machine Learning" in t for t in titles)

    finally:
        # Cleanup
        cursor.execute(f"DROP INDEX IF EXISTS {index_name};")
        cursor.execute(f"DROP TABLE IF EXISTS {table_name};")
        conn.commit()
        cursor.close()
        conn.close()


def test_paradedb_conjunction_search():
    """Test ParadeDB's conjunction (AND) search using &&& operator."""
    conn = get_connection()
    cursor = conn.cursor()

    table_name = f"items_{short_uid()}"
    index_name = f"{table_name}_idx"

    try:
        # Create table
        cursor.execute(f"""
            CREATE TABLE {table_name} (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT
            );
        """)
        conn.commit()

        # Insert sample data
        cursor.execute(f"""
            INSERT INTO {table_name} (name, description) VALUES
            ('Running Shoes', 'Lightweight running shoes for marathon training'),
            ('Walking Shoes', 'Comfortable walking shoes for daily use'),
            ('Running Gear', 'Essential gear for running enthusiasts'),
            ('Basketball Shoes', 'High-top basketball shoes with ankle support');
        """)
        conn.commit()

        # Create BM25 index
        cursor.execute(f"""
            CREATE INDEX {index_name} ON {table_name}
            USING bm25 (id, name, description)
            WITH (key_field='id');
        """)
        conn.commit()

        # Search using conjunction (AND) - must contain both 'running' AND 'shoes'
        cursor.execute(f"""
            SELECT id, name, description
            FROM {table_name}
            WHERE name &&& 'running shoes';
        """)
        results = cursor.fetchall()

        assert len(results) >= 1
        # Should match "Running Shoes" but not "Running Gear" or "Walking Shoes"
        assert any("Running Shoes" in row[1] for row in results)

    finally:
        # Cleanup
        cursor.execute(f"DROP INDEX IF EXISTS {index_name};")
        cursor.execute(f"DROP TABLE IF EXISTS {table_name};")
        conn.commit()
        cursor.close()
        conn.close()


def test_standard_postgres_features():
    """Test that standard PostgreSQL features work correctly."""
    conn = get_connection()
    cursor = conn.cursor()

    table_name = f"users_{short_uid()}"

    try:
        # Create table with various PostgreSQL types
        cursor.execute(f"""
            CREATE TABLE {table_name} (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(255) UNIQUE,
                metadata JSONB,
                tags TEXT[],
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()

        # Insert data with JSONB and arrays
        cursor.execute(f"""
            INSERT INTO {table_name} (name, email, metadata, tags)
            VALUES
                ('Alice', 'alice@example.com', '{{"role": "admin", "level": 5}}', ARRAY['active', 'premium']),
                ('Bob', 'bob@example.com', '{{"role": "user", "level": 2}}', ARRAY['active']),
                ('Charlie', 'charlie@example.com', '{{"role": "user", "level": 3}}', ARRAY['inactive']);
        """)
        conn.commit()

        # Query with JSONB operators
        cursor.execute(f"""
            SELECT name FROM {table_name}
            WHERE metadata->>'role' = 'admin';
        """)
        results = cursor.fetchall()
        assert len(results) == 1
        assert results[0][0] == "Alice"

        # Query with array operators
        cursor.execute(f"""
            SELECT name FROM {table_name}
            WHERE 'premium' = ANY(tags);
        """)
        results = cursor.fetchall()
        assert len(results) == 1
        assert results[0][0] == "Alice"

    finally:
        # Cleanup
        cursor.execute(f"DROP TABLE IF EXISTS {table_name};")
        conn.commit()
        cursor.close()
        conn.close()
