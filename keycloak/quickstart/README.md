# Custom Realm Quickstart

This guide shows how to use a custom realm configuration with the Keycloak extension.

## Step 1: Prepare Your Realm File

Use the provided `sample-realm.json` as a template. Key sections:

- **realm**: The realm name (e.g., `my-app`)
- **roles**: Define realm-level roles
- **users**: Pre-create users with credentials
- **clients**: Configure OAuth2/OIDC clients

## Step 2: Start LocalStack

```bash
# Set the path (must be absolute HOST path)
# IMPORTANT: Use LOCALSTACK_ prefix when using the CLI
export LOCALSTACK_KEYCLOAK_REALM_FILE=/path/to/your/realm.json
export LOCALSTACK_KEYCLOAK_REALM=my-app

localstack start
```

## Step 3: Verify Setup

```bash
# Health check
curl http://localhost:9000/health/ready

# Get token (client credentials)
TOKEN=$(curl -s -X POST \
  "http://keycloak.localhost.localstack.cloud:4566/realms/my-app/protocol/openid-connect/token" \
  -d "grant_type=client_credentials" \
  -d "client_id=my-app-client" \
  -d "client_secret=my-client-secret" | jq -r '.access_token')

# Or authenticate as a user
TOKEN=$(curl -s -X POST \
  "http://keycloak.localhost.localstack.cloud:4566/realms/my-app/protocol/openid-connect/token" \
  -d "grant_type=password" \
  -d "client_id=my-app-client" \
  -d "client_secret=my-client-secret" \
  -d "username=testuser" \
  -d "password=testpassword" | jq -r '.access_token')
```

## Step 4: AWS OIDC Federation

```bash
# Create trust policy
cat > trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::000000000000:oidc-provider/keycloak.localhost.localstack.cloud:4566/realms/my-app"
    },
    "Action": "sts:AssumeRoleWithWebIdentity"
  }]
}
EOF

# Create IAM role
awslocal iam create-role \
  --role-name MyAppRole \
  --assume-role-policy-document file://trust-policy.json

# Exchange token for AWS credentials
awslocal sts assume-role-with-web-identity \
  --role-arn arn:aws:iam::000000000000:role/MyAppRole \
  --role-session-name test-session \
  --web-identity-token "$TOKEN"
```

## Troubleshooting

### Realm not loading

1. Use `LOCALSTACK_` prefix for env vars with CLI
2. Ensure file path is absolute HOST path
3. Check logs: `docker logs ls-ext-keycloak`

### Token issues

1. Verify client credentials match realm config
2. Check realm name in token URL
3. Ensure client has required flows enabled
