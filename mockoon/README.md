# Mockoon on LocalStack

This repo contains a [LocalStack Extension](https://github.com/localstack/localstack-extensions) that facilitates developing [Mockoon](https://mockoon.com)-based applications locally.

The extension runs the [Mockoon CLI](https://mockoon.com/cli/) (`mockoon/cli:9` Docker image) next to LocalStack, and makes your mock APIs available under `http://mockoon.localhost.localstack.cloud:4566`. This allows your application code (e.g., Lambda functions or ECS tasks running in LocalStack) to call mocked third-party APIs during local development and testing.

## Prerequisites

- Docker
- LocalStack Pro (free trial available)
- [`lstk`](https://docs.localstack.cloud/aws/developer-tools/running-localstack/lstk/) CLI (`npm install -g @localstack/lstk`)
- `make` and Terraform (for the sample app)
- [Mockoon desktop app](https://mockoon.com/download/) (optional, for designing your mock APIs)

## Install from PyPI

`lstk` does not have commands for managing extensions, but LocalStack can install the extension at startup via the `EXTENSION_AUTO_INSTALL` config variable:

```bash
LOCALSTACK_EXTENSION_AUTO_INSTALL="localstack-mockoon" lstk start
```

Alternatively, if you are using the legacy `localstack` CLI:

```bash
localstack extensions install localstack-mockoon
```

## Install local development version

To install the extension into LocalStack in developer mode, you will need Python 3.11, and create a virtual environment in the extensions project.

In the newly generated project, simply run

```bash
make install
```

Developer mode currently requires the legacy `localstack` CLI, as `lstk` does not support extensions yet. To enable the extension for LocalStack, run

```bash
localstack extensions dev enable .
```

You can then start LocalStack with `EXTENSION_DEV_MODE=1` to load all enabled extensions (the `localstack` CLI mounts the extension sources into the container):

```bash
EXTENSION_DEV_MODE=1 localstack start
```

## Usage

Mockoon mock APIs are defined in [environment data files](https://mockoon.com/docs/latest/mockoon-data-files/data-files-location/) (JSON), which you can create and edit with the Mockoon desktop app.

To serve your own environment, start LocalStack with `MOCKOON_DATA` pointing to the **absolute** path of your environment file on the host:

```bash
LOCALSTACK_MOCKOON_DATA=/path/to/my-environment.json lstk start
```

The mock API is then available at `http://mockoon.localhost.localstack.cloud:4566`, for example:

```bash
curl http://mockoon.localhost.localstack.cloud:4566/orders/42
```

The data file is watched for changes, so any edits you make to it (e.g., in the Mockoon desktop app) are picked up automatically, without restarting LocalStack.

Instead of a local file, `MOCKOON_DATA` can also point to a remote URL (e.g., `https://example.com/my-environment.json`), or to a [Mockoon Cloud](https://mockoon.com/cloud/) environment (`cloud://<environment-id>`, requires `MOCKOON_CLOUD_TOKEN`).

If `MOCKOON_DATA` is not set, a default environment with a single welcome route (`GET /welcome`) is served.

### Admin API

The [Mockoon admin API](https://mockoon.com/docs/latest/admin-api/overview/) is available under `http://mockoon.localhost.localstack.cloud:4566/mockoon-admin`, and requires a bearer token (default: `test`). For example, to retrieve the transaction logs:

```bash
curl -H "Authorization: Bearer test" http://mockoon.localhost.localstack.cloud:4566/mockoon-admin/logs
```

The admin API also allows to update route responses at runtime (`PUT /mockoon-admin/environment`), manage global/environment variables, and purge data buckets.

### Environment Variables

- `MOCKOON_DATA`: Absolute host path, URL, or `cloud://` reference of the Mockoon environment to serve (default: bundled welcome environment)
- `MOCKOON_ADMIN_API_TOKEN`: Bearer token for the Mockoon admin API (default: `test`)
- `MOCKOON_CLOUD_TOKEN`: Mockoon Cloud access token, required when using `cloud://` environments
- `MOCKOON_IMAGE`: Custom Docker image name for the Mockoon CLI (default: `mockoon/cli:9`)

Note: When starting LocalStack via `lstk` (or the `localstack` CLI), prefix environment variables with `LOCALSTACK_` to forward them to the container.

## Sample Application

See the `sample-app/` directory for a complete example using Terraform that demonstrates:

- Creating an API Gateway
- Lambda function that calls a mocked Orders API served by Mockoon
- Integration testing with mocked external APIs

To run the sample, start LocalStack with the sample environment, and then deploy and invoke the app (the deployment uses `lstk terraform`, override via `make sample TERRAFORM=tflocal` if needed):

```bash
LOCALSTACK_MOCKOON_DATA=$PWD/sample-app/environment.json lstk start
make sample
```

## Change Log

- `0.1.0`: Initial release of the extension

## License

This project is licensed under the Apache License, Version 2.0.
