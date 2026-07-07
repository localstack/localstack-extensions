# LocalStack Prowler Extension

Run [Prowler](https://github.com/prowler-cloud/prowler) security checks against your LocalStack environment directly from a built-in web UI.

The extension launches Prowler as a Docker sidecar container on demand, scans your LocalStack resources, and presents the findings in a filterable, sortable table with no external tooling required.

## Install

```bash
localstack extensions install localstack-prowler
```

**Requirements**: LocalStack Pro, Docker socket available (`/var/run/docker.sock`).

## Access the UI

Once LocalStack is running with the extension loaded, open:

```
http://localhost.localstack.cloud:4566/_extension/prowler
```

From there you can choose which AWS services and severity levels to scan, click **Run Scan**, and watch findings appear in real time.

## REST API

The extension also exposes a REST API at `/_extension/prowler/api`:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/status` | Current scan state and summary counts |
| `POST` | `/api/scans` | Start a new scan (body: `{"services": [], "severity": []}`) |
| `GET` | `/api/scans/latest` | Full findings from the most recent completed scan |

Starting a scan while one is already running returns `409 Conflict`.

### Example

```bash
# Start a scan for S3 at critical/high severity
curl -X POST http://localhost.localstack.cloud:4566/_extension/prowler/api/scans \
  -H "Content-Type: application/json" \
  -d '{"services": ["s3"], "severity": ["critical", "high"]}'

# Poll until completed
curl http://localhost.localstack.cloud:4566/_extension/prowler/api/status

# Retrieve findings
curl http://localhost.localstack.cloud:4566/_extension/prowler/api/scans/latest
```

## Configuration

| Environment Variable | Default | Description |
|----------------------|---------|-------------|
| `PROWLER_LOCALSTACK_ENDPOINT` | `http://host.docker.internal:4566` | LocalStack endpoint passed to the Prowler container |
| `PROWLER_DOCKER_IMAGE` | `prowlercloud/prowler:latest` | Prowler Docker image to use |

Set these as LocalStack environment variables, e.g. via `DOCKER_FLAGS` or in your `docker-compose.yml`.

## Development

### Install local development version

```bash
make install
```

Then enable dev mode and start LocalStack:

```bash
localstack extensions dev enable .
EXTENSION_DEV_MODE=1 LOCALSTACK_AUTH_TOKEN=<token> localstack start -d
```

### Build the frontend

```bash
make install-frontend
make build-frontend
```

The compiled assets are written to `backend/localstack_prowler/static/` and served by the extension automatically.

## Licensing

- [Prowler](https://github.com/prowler-cloud/prowler) is licensed under the Apache License 2.0
- This extension is licensed under the Apache License 2.0
