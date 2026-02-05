# HashiCorp Vault on LocalStack

This [LocalStack Extension](https://github.com/localstack/localstack-extensions) runs [HashiCorp Vault](https://www.vaultproject.io/) alongside LocalStack for secrets management testing.

## Prerequisites

- Docker
- LocalStack Pro (free trial available)
- `localstack` CLI

## Install from GitHub repository

```bash
localstack extensions install "git+https://github.com/localstack/localstack-extensions.git#egg=localstack-extension-vault&subdirectory=vault"
```

## Install local development version

```bash
make install
localstack extensions dev enable .
```

Start LocalStack with `EXTENSION_DEV_MODE=1`:

```bash
EXTENSION_DEV_MODE=1 localstack start
```

## Usage

Vault is available at `http://vault.localhost.localstack.cloud:4566`.

### Add Secrets

```bash
export VAULT_ADDR=http://vault.localhost.localstack.cloud:4566
export VAULT_TOKEN=root

# Add a secret
vault kv put secret/my-app/config api_key=secret123 db_password=hunter2

# Verify
vault kv get secret/my-app/config
```

### Use with Lambda

Deploy a Lambda with the [Vault Lambda Extension](https://github.com/hashicorp/vault-lambda-extension) layer and these environment variables:

| Variable | Value |
|----------|-------|
| `VAULT_ADDR` | `http://vault.localhost.localstack.cloud:4566` |
| `VAULT_AUTH_PROVIDER` | `aws` |
| `VAULT_AUTH_ROLE` | `default-lambda-role` |
| `VAULT_SECRET_PATH_*` | Path to your secret (e.g., `secret/data/my-app/config`) |
| `VAULT_SECRET_FILE_*` | Where extension writes secrets (e.g., `/tmp/secrets/myapp`) |

See `sample-app-extension/` for a complete working example.

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `VAULT_ROOT_TOKEN` | `root` | Dev mode root token |
| `VAULT_PORT` | `8200` | Vault API port (internal) |

## Pre-configured Resources

### Secrets Engines

| Path | Type | Description |
|------|------|-------------|
| `secret/` | KV v2 | Key-value secrets storage |
| `transit/` | Transit | Encryption as a service |

### Auth Methods

| Path | Type | Description |
|------|------|-------------|
| `aws/` | AWS IAM | Pre-configured for Lambda IAM auth |

### Policies

| Name | Permissions |
|------|-------------|
| `default-lambda-policy` | Full access to `secret/*` and `transit/*` |

## Sample App

See `sample-app-extension/` for a complete working example using the official Vault Lambda Extension layer.

```bash
make sample-app
```

## Limitations

- **Ephemeral**: All secrets are lost when LocalStack restarts
- **Dev mode only**: No production Vault features (seal/unseal, HA, etc.)

## Disclaimer

This extension is not affiliated with HashiCorp. Vault is a trademark of HashiCorp, Inc.
