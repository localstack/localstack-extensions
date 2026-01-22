WireMock on LocalStack
========================

This repo contains a [LocalStack Extension](https://github.com/localstack/localstack-extensions) that facilitates developing [WireMock](https://wiremock.org)-based applications locally.

The extension supports two modes:
- **OSS WireMock**: Uses the open-source `wiremock/wiremock` image (default)
- **WireMock Runner**: Uses `wiremock/wiremock-runner` with WireMock Cloud integration (requires API token)

## Prerequisites

* Docker
* LocalStack Pro (free trial available)
* `localstack` CLI
* `make`
* [WireMock CLI](https://docs.wiremock.io/cli/overview) (for WireMock Runner mode)

## Install from GitHub repository

This extension can be installed directly from this Github repo via:

```bash
localstack extensions install "git+https://github.com/localstack/localstack-extensions.git#egg=localstack-wiremock&subdirectory=wiremock"
```

## Install local development version

To install the extension into localstack in developer mode, you will need Python 3.11, and create a virtual environment in the extensions project.

In the newly generated project, simply run

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

### OSS WireMock Mode (Default)

Start LocalStack without any special configuration:

```bash
localstack start
```

The WireMock server will be available at `http://wiremock.localhost.localstack.cloud:4566`.

You can import stubs using the WireMock Admin API:

```bash
curl -X POST -H "Content-Type: application/json" \
  --data-binary "@stubs.json" \
  "http://wiremock.localhost.localstack.cloud:4566/__admin/mappings/import"
```

### WireMock Runner Mode (Cloud Integration)

To use WireMock Runner with WireMock Cloud, you need:
1. A WireMock Cloud API token
2. A `.wiremock` directory with your mock API configuration

#### Step 1: Get your WireMock Cloud API Token

1. Sign up at [WireMock Cloud](https://app.wiremock.cloud)
2. Go to Settings → API Tokens
3. Create a new token

#### Step 2: Create your Mock API configuration

First, create a Mock API in WireMock Cloud, then pull the configuration locally:

```bash
# Install WireMock CLI if not already installed
npm install -g wiremock

# Login with your API token
wiremock login

# Pull your Mock API configuration
# Find your Mock API ID from the WireMock Cloud URL (e.g., https://app.wiremock.cloud/mock-apis/zwg1l/...)
wiremock pull mock-api <mock-api-id>
```

This creates a `.wiremock` directory with your `wiremock.yaml` configuration.

#### Step 3: Start LocalStack with WireMock Runner

```bash
LOCALSTACK_WIREMOCK_API_TOKEN="your-api-token" \
LOCALSTACK_WIREMOCK_CONFIG_DIR="/path/to/your/project" \
localstack start
```

**Environment Variables:**
- `WIREMOCK_API_TOKEN`: Your WireMock Cloud API token (required for runner mode)
- `WIREMOCK_CONFIG_DIR`: Path to the directory containing your `.wiremock` folder (required for runner mode)

Note: When using the LocalStack CLI, prefix environment variables with `LOCALSTACK_` to forward them to the container.

## Sample Application

See the `sample-app/` directory for a complete example using Terraform that demonstrates:
- Creating an API Gateway
- Lambda function that calls WireMock stubs
- Integration testing with mocked external APIs
