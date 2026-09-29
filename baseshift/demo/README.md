# Baseshift on LocalStack - Demo

This demo shows how masked production data flows through a fully local development setup:

```
 "production" DB          masked snapshot          clone               ELT pipeline          warehouse
 LocalStack RDS    --->   LocalStack ECR    --->   Baseshift     --->  S3 (CSV export) --->  Snowflake
 (PostgreSQL + PII)       (Docker image)           extension                                 emulator
```

At the end, the same customer record is shown at every stage of the pipeline - raw in the source database, and masked in the clone and in Snowflake:

```
column    source (RDS)                  Baseshift clone               Snowflake
--------  ----------------------------  ----------------------------  ----------------------------
name      Jane Roe                      Customer 9231c1               Customer 9231c1
email     jane.roe@gmail.com            user-ae9cacc9@example.com     user-ae9cacc9@example.com
ssn       078-05-1120                   ***-**-1120                   ***-**-1120
phone     +1 415 555 0142               +1 555 3021670                +1 555 3021670
address   221B Baker Street, London     101 Masked Street             101 Masked Street

No raw PII values reached the clone or Snowflake.
```

## Prerequisites

- Docker, and the [`lstk`](https://docs.localstack.cloud/aws/developer-tools/running-localstack/lstk/) CLI
- A LocalStack license that includes the Snowflake emulator
- Python 3, with the demo dependencies: `pip install -r demo/requirements.txt`

The demo uses the LocalStack Snowflake emulator image (`lstk` emulator type `snowflake`), which also provides the AWS services used here (RDS, ECR, S3), so everything runs in a single LocalStack container.

## Running the demo

Start LocalStack with the Snowflake emulator and the extension installed:

```bash
lstk start --type snowflake   # with LOCALSTACK_EXTENSION_AUTO_INSTALL set, see the extension README
```

Then run all steps of the demo (from the `baseshift` directory):

```bash
make demo
```

Or run the steps one by one, to walk through the flow:

```bash
python demo/demo.py source     # create the "production" RDS database, and seed it with PII
python demo/demo.py snapshot   # create a masked snapshot image, and push it to LocalStack ECR
python demo/demo.py clone      # start a clone from the snapshot image, via the extension API
python demo/demo.py pipeline   # export the clone data to S3, and load it into Snowflake
python demo/demo.py compare    # show the same record at every stage
```

Set `LOCALSTACK_HOST` if LocalStack runs on a different port (default: `localhost.localstack.cloud:4566`).

## What is emulated

The `snapshot` step is currently a **stand-in** for the Baseshift replication server: it reads the source database, applies a simple deterministic masking policy, and builds a PostgreSQL image with the masked data. Its purpose is to illustrate the flow - the actual Baseshift components provide PII scanning, masking policies, subsetting, and continuous snapshots via logical replication.

The next step is to replace the stand-in with the actual Baseshift self-hosted components, running against LocalStack:

- The [`baseshift-selfhosted/`](baseshift-selfhosted/) directory contains Helm values for LocalStack (`values-localstack.yaml`, validated against the Baseshift chart schema), and a `docker-compose.yml` translated from the rendered chart, as a lightweight alternative to Kubernetes.
- The source database would be the RDS instance created by the `source` step (which already enables logical replication), and Docker snapshots would be pushed to the LocalStack ECR registry (as a plain Docker v2 registry).
- This requires access to the Baseshift replication server image, and a Dub server enrolled in Baseshift Cloud (the control plane).

## Notes

- LocalStack RDS does not apply the `rds.logical_replication` parameter (yet) - the `source` step sets `wal_level = logical` directly, and reboots the instance.
- The ELT step is a plain script for simplicity; in a real setup, it would typically be a scheduled job (e.g., a Lambda function or an Airflow DAG) running against the clone.
