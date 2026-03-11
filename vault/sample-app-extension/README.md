# Vault Lambda Extension Sample App

A sample Lambda application demonstrating the [HashiCorp Vault Lambda Extension](https://github.com/hashicorp/vault-lambda-extension) with LocalStack.

## Overview

This sample app deploys a Lambda function that:

- Uses the official Vault Lambda Extension layer
- Authenticates with Vault via IAM auth
- Reads secrets written by the extension to `/tmp/secrets/`

## Prerequisites

- [LocalStack](https://localstack.cloud/) with the Vault extension installed
- `awslocal` CLI
- Vault CLI

## Setup

### 1. Start LocalStack with Vault Extension

```bash
EXTENSION_DEV_MODE=1 localstack start
```

### 2. Create Secrets in Vault

```bash
make setup-vault
```

Or manually:

```bash
export VAULT_ADDR=http://vault.localhost.localstack.cloud:4566
export VAULT_TOKEN=root

vault kv put secret/myapp/config api_key=secret123 db_password=hunter2
```

### 3. Deploy the Lambda

```bash
make deploy
```

### 4. Test the Function

```bash
make test
```

## Environment Variables

The Lambda function requires these environment variables for the extension:

| Variable | Description |
|----------|-------------|
| `VAULT_ADDR` | Vault server address |
| `VAULT_AUTH_PROVIDER` | Auth method (`aws` for IAM auth) |
| `VAULT_AUTH_ROLE` | Vault role name for IAM auth |
| `VAULT_SECRET_PATH_*` | Secret path to fetch |
| `VAULT_SECRET_FILE_*` | File path where extension writes secrets |

## Usage

```bash
# Run everything at once
make run

# Or step by step
make setup-vault
make deploy
make test
```

## How It Works

1. Lambda is deployed with the Vault Lambda Extension layer
2. Extension authenticates to Vault via IAM auth
3. Extension fetches secrets and writes to `/tmp/secrets/`
4. Lambda handler reads secrets from the file
