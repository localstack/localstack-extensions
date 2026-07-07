# CockroachDB on LocalStack

This repo contains a [LocalStack Extension](https://github.com/localstack/localstack-extensions) that facilitates developing [CockroachDB](https://www.cockroachlabs.com)-based applications locally.

CockroachDB is a distributed SQL database built for cloud applications. It is PostgreSQL wire-protocol compatible, making it easy to use existing PostgreSQL drivers and tools.

After installing the extension, a CockroachDB server instance will become available and can be accessed using standard PostgreSQL clients or CockroachDB-specific drivers.

## Connection Details

Once the extension is running, you can connect to CockroachDB using any PostgreSQL-compatible client:

- **Host**: `cockroachdb.localhost.localstack.cloud`
- **Port**: `4566` (LocalStack gateway)
- **Database**: `defaultdb`
- **Username**: `root`
- **Password**: none (insecure mode)

Example connection using `psql`:
```bash
psql "postgresql://root@cockroachdb.localhost.localstack.cloud:4566/defaultdb?sslmode=disable"
```

Example connection using Python with psycopg2:
```python
import psycopg2

conn = psycopg2.connect(
    host="cockroachdb.localhost.localstack.cloud",
    port=4566,
    user="root",
    database="defaultdb",
    sslmode="disable",
)
cursor = conn.cursor()
cursor.execute("SELECT version()")
print(cursor.fetchone()[0])
conn.close()
```

## Configuration

The following environment variables can be passed to the LocalStack container to configure the extension:

* `COCKROACHDB_IMAGE`: Docker image to use (default: `cockroachdb/cockroach:latest`)
* `COCKROACHDB_FLAGS`: Extra flags appended to the CockroachDB startup command (default: none)
* `COCKROACHDB_USER`: User for connection string reference (default: `root`)
* `COCKROACHDB_DB`: Database for connection string reference (default: `defaultdb`)

Example:
```bash
COCKROACHDB_FLAGS="--cache=.25 --max-sql-memory=.25" localstack start
```

## Known Limitations

* **Single-node only** — this extension runs CockroachDB in `start-single-node` mode. Multi-node clusters are not supported.
* **Insecure mode only** — TLS and authentication are disabled. This is intentional for local development. Do not use in production.
* **Ephemeral data** — data is lost when the CockroachDB container stops, matching LocalStack's stateless default behavior.

## Prerequisites

* Docker
* LocalStack Pro (free trial available)
* `localstack` CLI
* `make`

## Install from GitHub repository

This extension can be installed directly from this Github repo via:

```bash
localstack extensions install "git+https://github.com/localstack/localstack-extensions.git#egg=localstack-extension-cockroachdb&subdirectory=cockroachdb"
```

## Install local development version

Please refer to the docs [here](https://github.com/localstack/localstack-extensions?tab=readme-ov-file#start-localstack-with-the-extension) for instructions on how to start the extension in developer mode.

## Change Log

* `0.1.0`: Initial version of the extension

## License

The code in this repo is available under the Apache 2.0 license.
