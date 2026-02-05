# Keycloak on LocalStack

This repo contains a [LocalStack Extension](https://github.com/localstack/localstack-extensions) that runs [Keycloak](https://www.keycloak.org/) alongside LocalStack for identity and access management with local AWS applications.

This Extension:

- Spins up a Keycloak instance on LocalStack startup.
- Auto-registers Keycloak as an OIDC identity provider in LocalStack IAM.
- Ships with a default realm (`localstack`) ready for OAuth2/OIDC flows.
- Exchanges Keycloak JWTs for temporary AWS credentials via `AssumeRoleWithWebIdentity`.

## Prerequisites

- Docker
- LocalStack Pro
- `localstack` CLI
- `make`

## Installation

```bash
localstack extensions install "git+https://github.com/localstack/localstack-extensions.git#egg=localstack-keycloak&subdirectory=keycloak"
```

## Install local development version

To install the extension into LocalStack in developer mode, you will need Python 3.11, and create a virtual environment in the extensions project.

```bash
make install
```

Then, to enable the extension for LocalStack, run

```bash
localstack extensions dev enable .
```

You can then start LocalStack with `EXTENSION_DEV_MODE=1` to load all enabled extensions:

```bash
EXTENSION_DEV_MODE=1 localstack start
```

## Usage

Start LocalStack:

```bash
localstack start
```

Keycloak will be available at:

| Endpoint | URL |
|----------|-----|
| Admin Console | http://localhost:8080/admin |
| Token Endpoint | http://keycloak.localhost.localstack.cloud:4566/realms/localstack/protocol/openid-connect/token |
| JWKS URL | http://keycloak.localhost.localstack.cloud:4566/realms/localstack/protocol/openid-connect/certs |

Keycloak ports are exposed directly on the host for easy access:

- **Admin Console & HTTP (8080)**: `http://localhost:8080` - Use this for the admin UI and direct API access
- **Management (9000)**: `http://localhost:9000` - Health and metrics endpoints (Keycloak 26+)

The gateway URL (`keycloak.localhost.localstack.cloud:4566`) is available for token endpoints and OIDC flows.

- **Default Admin Credentials**: `admin` / `admin`
- **Health check**: `curl http://localhost:9000/health/ready`

### Get an Access Token

```bash
TOKEN=$(curl -s -X POST \
  "http://keycloak.localhost.localstack.cloud:4566/realms/localstack/protocol/openid-connect/token" \
  -d "grant_type=client_credentials" \
  -d "client_id=localstack-client" \
  -d "client_secret=localstack-client-secret" | jq -r '.access_token')
```

### Exchange Token for AWS Credentials

```bash
# Create IAM role that trusts Keycloak
cat > trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::000000000000:oidc-provider/keycloak.localhost.localstack.cloud:4566/realms/localstack"
    },
    "Action": "sts:AssumeRoleWithWebIdentity"
  }]
}
EOF

awslocal iam create-role \
  --role-name KeycloakAuthRole \
  --assume-role-policy-document file://trust-policy.json

# Exchange Keycloak token for AWS credentials
awslocal sts assume-role-with-web-identity \
  --role-arn arn:aws:iam::000000000000:role/KeycloakAuthRole \
  --role-session-name test-session \
  --web-identity-token "$TOKEN"
```

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `KEYCLOAK_REALM` | `localstack` | Name of the default realm |
| `KEYCLOAK_VERSION` | `26.0` | Keycloak Docker image version |
| `KEYCLOAK_REALM_FILE` | - | Path to custom realm JSON file |
| `KEYCLOAK_DEFAULT_USER` | - | Username for auto-created test user |
| `KEYCLOAK_DEFAULT_PASSWORD` | - | Password for auto-created test user |
| `KEYCLOAK_OIDC_AUDIENCE` | `localstack-client` | Audience claim for OIDC provider |
| `KEYCLOAK_FLAGS` | - | Additional flags for Keycloak start command |

> **Note**: When using `localstack start`, prefix environment variables with `LOCALSTACK_` (e.g., `LOCALSTACK_KEYCLOAK_REALM`).

### Custom Realm Configuration

Use your own realm JSON file with pre-configured users, roles, and clients.

```bash
# The path must be an absolute HOST path for Docker mount
# Use LOCALSTACK_ prefix when running via CLI
LOCALSTACK_KEYCLOAK_REALM_FILE=/path/to/my-realm.json localstack start
```

See [`quickstart/sample-realm.json`](quickstart/sample-realm.json) for a realm template and [`quickstart/README.md`](quickstart/README.md) for a step-by-step guide.

### Create Test Users

```bash
# Auto-create a test user on startup (use LOCALSTACK_ prefix with CLI)
LOCALSTACK_KEYCLOAK_DEFAULT_USER=testuser LOCALSTACK_KEYCLOAK_DEFAULT_PASSWORD=password123 localstack start
```

## Default Client

The extension creates a default client `localstack-client` with:

- **Client Secret**: `localstack-client-secret`
- **Flows**: Authorization Code, Client Credentials, Direct Access Grants
- **Service Account Roles**: `admin`, `user`

The service account for `localstack-client` is automatically assigned the `admin` realm role, enabling full access when using client credentials flow.

## Sample Application

See the `sample-app/` directory for a complete example demonstrating:

- API Gateway with Lambda Authorizer
- JWT validation with Keycloak
- Role-based access control
- DynamoDB user management

## Troubleshooting

### Keycloak takes a long time to start

Keycloak typically takes 30-60 seconds to fully start. The extension waits for the health check to pass before marking LocalStack as ready.

### Health check endpoint returns 404

In Keycloak 26+, the health endpoint is on port 9000:

```bash
curl http://localhost:9000/health/ready
```

### View Keycloak logs

```bash
docker logs ls-ext-keycloak
```

## Development

```bash
# Install dependencies
make install

# Run tests (requires LocalStack with extension running)
make test

# Format code
make format

# Lint
make lint
```

## License

Apache License 2.0
