AWS Cloud Proxy Extension
=========================
[![Install LocalStack Extension](https://localstack.cloud/gh/extension-badge.svg)](https://app.localstack.cloud/extensions/remote?url=git+https://github.com/localstack/localstack-extensions/#egg=localstack-extension-aws-proxy&subdirectory=aws-proxy)

A LocalStack extension to proxy and integrate AWS resources into your local machine.
This enables one flavor of "hybrid" or "remocal" setups where you can easily bridge the gap between LocalStack (local resources) and remote AWS (resources in the real cloud).

## Prerequisites

* LocalStack Pro
* Docker
* Python

## Installation

Install the extension via the LocalStack CLI:

```bash
localstack extensions install localstack-extension-aws-proxy
```

After installation, restart LocalStack for the extension to take effect.

## Usage

### Enable the proxy

Enable the proxy for specific services (e.g., DynamoDB, S3, Cognito) by posting a configuration along with your AWS credentials:

```bash
curl -X POST http://localhost:4566/_localstack/aws/proxies \
  -H 'Content-Type: application/json' \
  -d '{
    "config": {
      "services": {
        "dynamodb": {},
        "s3": {},
        "cognito-idp": {}
      }
    },
    "env_vars": {
      "AWS_ACCESS_KEY_ID": "<your-access-key-id>",
      "AWS_SECRET_ACCESS_KEY": "<your-secret-access-key>",
      "AWS_SESSION_TOKEN": "<your-session-token>"
    }
  }'
```

### Check proxy status

```bash
curl http://localhost:4566/_localstack/aws/proxies/status
```

### Disable the proxy

```bash
curl -X POST http://localhost:4566/_localstack/aws/proxies/status \
  -H 'Content-Type: application/json' \
  -d '{"status": "disabled"}'
```

Once enabled, API calls against LocalStack (e.g., via `awslocal`) are forwarded to real AWS and return data from your real cloud resources.

## Configuration

The following environment variables can be passed to the LocalStack container to customize behavior:

* `PROXY_CLEANUP_CONTAINERS`: whether to remove proxy Docker containers on shutdown (default `1`). Set to `0` to keep containers for debugging.
* `PROXY_LOCALSTACK_HOST`: the target host used by the proxy container to connect to LocalStack (auto-detected by default).
* `PROXY_DOCKER_FLAGS`: additional flags passed when creating proxy Docker containers.

## License

This extension is published under the Apache License, Version 2.0.
By using it, you also agree to the LocalStack [End-User License Agreement (EULA)](https://github.com/localstack/localstack/tree/master/doc/end_user_license_agreement).
