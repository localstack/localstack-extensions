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

By default, the `snapshot` step is a **stand-in** for the Baseshift replication server: it reads the source database, applies a simple deterministic masking policy, and builds a PostgreSQL image with the masked data. Its purpose is to illustrate the flow - the actual Baseshift components provide PII scanning, masking policies, subsetting, and continuous snapshots via logical replication.

## Running with the Baseshift self-hosted components

With `--selfhosted`, the demo uses the actual Baseshift self-hosted components (agent and replication server) instead of the stand-in, via the [self-hosted Dubs](../README.md#self-hosted-dubs) API of the extension: the extension creates a Dub in Baseshift Cloud for the RDS source database, and runs its components as containers next to LocalStack. They replicate the source database, and push encrypted Docker snapshots to LocalStack ECR.

Start LocalStack with the credentials of a Baseshift user:

```bash
LOCALSTACK_BASESHIFT_USER_EMAIL=<email> LOCALSTACK_BASESHIFT_USER_PASSWORD=<password> \
  lstk start --type snowflake   # with LOCALSTACK_EXTENSION_AUTO_INSTALL set, see the extension README
```

Then run all steps with `make demo-selfhosted`, or one by one:

```bash
python demo/demo.py source                 # create the "production" RDS database, and seed it with PII
python demo/demo.py dub                    # create a self-hosted Dub, running in LocalStack EKS (takes a few minutes)
python demo/demo.py clone --selfhosted     # start a clone from the latest snapshot of the Dub
python demo/demo.py pipeline               # export the clone data to S3, and load it into Snowflake
python demo/demo.py compare                # show the same record at every stage
python demo/demo.py snapshot --selfhosted  # (optional) take a new snapshot of the Dub
```

Set `BASESHIFT_DUB_NAME` to use a different Dub name (default: `localstack-shop`), and `BASESHIFT_DEPLOYMENT=kubernetes` to run the components in a LocalStack EKS cluster instead of plain containers. Dubs cannot be deleted via the Baseshift CLI, so use a new name when running the demo against a fresh LocalStack instance (unless the LocalStack volume directory is persisted).

The `dub` step creates the Dub with the masking policy in [`masking-policy.json`](masking-policy.json), which covers the PII columns of the `customers` table. The `compare` step fails if any raw PII values reach the clone.

## Notes

- LocalStack RDS does not apply the `rds.logical_replication` parameter (yet) - the `source` step sets `wal_level = logical` directly, and reboots the instance.
- The ELT step is a plain script for simplicity; in a real setup, it would typically be a scheduled job (e.g., a Lambda function or an Airflow DAG) running against the clone.
