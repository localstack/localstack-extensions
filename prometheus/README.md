# LocalStack Prometheus Metrics
[![Install LocalStack Extension](https://localstack.cloud/gh/extension-badge.svg)](https://app.localstack.cloud/extensions/remote?url=git+https://github.com/localstack/localstack-extensions/#egg=localstack-extension-prometheus-metrics&subdirectory=prometheus)

Instruments, collects, and exposes LocalStack metrics via a [Prometheus](https://prometheus.io/) endpoint.

## Installing

```bash
localstack extensions install localstack-extension-prometheus-metrics
```

**Note**: This plugin only supports LocalStack `>=v4.2`

## Usage

Scrape metrics via the endpoint:
```bash
curl localhost.localstack.cloud:4566/_extension/metrics
```

## Quickstart (Docker-Compose)

See the documentation on [Automating extension installation](https://docs.localstack.cloud/user-guide/extensions/managing-extensions/#automating-extensions-installation) for more details.

First, enable the extension by adding it to your LocalStack environment:

```yaml
services:
  localstack:
    environment:
      - EXTENSION_AUTO_INSTALL=localstack-extension-prometheus
```

Next, you'll need to spin up a Prometheus instance to run alongside your LocalStack container. A [configuration file](https://prometheus.io/docs/prometheus/latest/configuration/configuration/#configuration-file) is required.

### Option 1: Using a Volume Mount (Recommended)

Create `prometheus_config.yml`:
```yaml
global:
  scrape_interval: 15s # Set the scrape interval to every 15 seconds
  scrape_timeout: 5s   # Set the scrape request timeout to 5 seconds
# Scrape configuration for LocalStack metrics
scrape_configs:
  - job_name: 'localstack'
    static_configs:
      - targets: ['localstack:4566']    # Target the LocalStack Gateway
    metrics_path: '/_extension/metrics' # Metrics are exposed via `/_extension/metrics` endpoint
```

And mount it on startup to your `docker-compose.yml`:
```yaml
services:
  # ... LocalStack container should be defined
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - "./prometheus_config.yml:/etc/prometheus/prometheus.yml"
```

### Option 2: Inline Configuration

Using the Docker Compose top-level [configs](https://docs.docker.com/reference/compose-file/configs/):
```yaml
services:
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    configs:
      - source: prometheus_config
        target: /etc/prometheus/prometheus.yml

configs:
  prometheus_config:
    content: |
      global:
        scrape_interval: 15s
        scrape_timeout: 5s
      scrape_configs:
        - job_name: 'localstack'
          static_configs:
            - targets: ['localstack:4566']
          metrics_path: '/_extension/metrics'
```

### Full Example

```yaml
services:
  localstack:
    container_name: "${LOCALSTACK_DOCKER_NAME:-localstack-main}"
    image: localstack/localstack-pro  # required for Pro
    ports:
      - "4566:4566"            # LocalStack Gateway
      - "4510-4559:4510-4559"  # external services port range
      - "443:443"              # LocalStack HTTPS Gateway (Pro)
    environment:
      - LOCALSTACK_AUTH_TOKEN=${LOCALSTACK_AUTH_TOKEN:?}  # required for Pro
      - DEBUG=${DEBUG:-0}
      - PERSISTENCE=${PERSISTENCE:-0}
      - EXTENSION_AUTO_INSTALL=localstack-extension-prometheus
    volumes:
      - "${LOCALSTACK_VOLUME_DIR:-./volume}:/var/lib/localstack"
      - "/var/run/docker.sock:/var/run/docker.sock"
      - "conf.d:/etc/localstack/conf.d"

  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - "./prometheus_config.yml:/etc/prometheus/prometheus.yml" # Assumes prometheus_config.yml exists in your CWD
```

## Available Metrics

The Prometheus extension exposes various LocalStack metrics through the `/_extension/metrics` endpoint, including:
- Request counts by service
- Request latencies
- Resource utilization
- Error rates

For a complete list of available metrics, visit the endpoint directly at `localhost.localstack.cloud:4566/_extension/metrics` when LocalStack is running.

## Licensing

* [client_python](https://github.com/prometheus/client_python) is licensed under the Apache License version 2.