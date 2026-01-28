ParadeDB on LocalStack
======================

This repo contains a [LocalStack Extension](https://github.com/localstack/localstack-extensions) that facilitates developing [ParadeDB](https://www.paradedb.com)-based applications locally.

ParadeDB is an Elasticsearch alternative built on Postgres. It provides full-text search with BM25 scoring, hybrid search combining semantic and keyword search, and real-time analytics capabilities.

After installing the extension, a ParadeDB server instance will become available and can be accessed using standard PostgreSQL clients.

## Connection Details

Once the extension is running, you can connect to ParadeDB using any PostgreSQL client with the following default credentials:

- **Host**: `localhost` (or the Docker host if running in a container)
- **Port**: `5432` (mapped from the container)
- **Database**: `mydatabase`
- **Username**: `myuser`
- **Password**: `mypassword`

Example connection using `psql`:
```bash
psql -h localhost -p 5432 -U myuser -d mydatabase
```

Example connection using Python:
```python
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="mydatabase",
    user="myuser",
    password="mypassword"
)
```

## ParadeDB Features

ParadeDB includes the **pg_search** extension, for both search and
analytics workloads.

Example using pg_search:
```sql
-- Create a table with search index
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name TEXT,
    description TEXT
);

-- Create a BM25 search index
CALL paradedb.create_bm25(
    index_name => 'products_idx',
    table_name => 'products',
    key_field => 'id',
    text_fields => paradedb.field('name') || paradedb.field('description')
);

-- Search with BM25 scoring
SELECT * FROM products.search('description:electronics');
```

## Configuration

The following environment variables can be passed to the LocalStack container to configure the extension:

* `PARADEDB_POSTGRES_USER`: PostgreSQL username (default: `myuser`)
* `PARADEDB_POSTGRES_PASSWORD`: PostgreSQL password (default: `mypassword`)
* `PARADEDB_POSTGRES_DB`: Default database name (default: `mydatabase`)

## Prerequisites

* Docker
* LocalStack Pro (free trial available)
* `localstack` CLI
* `make`

## Install from GitHub repository

This extension can be installed directly from this Github repo via:

```bash
localstack extensions install "git+https://github.com/localstack/localstack-extensions.git#egg=localstack-extension-paradedb&subdirectory=paradedb"
```

## Install local development version

Please refer to the docs [here](https://github.com/localstack/localstack-extensions?tab=readme-ov-file#start-localstack-with-the-extension) for instructions on how to start the extension in developer mode.

## Change Log

* `0.1.0`: Initial version of the extension

## License

The code in this repo is available under the Apache 2.0 license.
