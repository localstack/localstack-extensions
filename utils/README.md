LocalStack Extensions Utils
===========================

A utility library providing common functionality for building [LocalStack Extensions](https://github.com/localstack/localstack-extensions).

## Features

This library provides reusable utilities for LocalStack extension development:

### ProxiedDockerContainerExtension

A base class for creating LocalStack extensions that run Docker containers and proxy requests to them through the LocalStack gateway.

Features:
- Automatic Docker container lifecycle management
- HTTP/1.1 request proxying via the LocalStack gateway
- HTTP/2 support for gRPC traffic
- Configurable host and path-based routing

### HTTP/2 Proxy Support

Utilities for proxying HTTP/2 and gRPC traffic through LocalStack:

- `TcpForwarder`: Bidirectional TCP traffic forwarding
- `apply_http2_patches_for_grpc_support`: Patches to enable gRPC proxying

## Installation

```bash
pip install localstack-extensions-utils
```

Or install directly from the GitHub repository:

```bash
pip install "git+https://github.com/localstack/localstack-extensions.git#egg=localstack-extensions-utils&subdirectory=utils"
```

## Usage

### Creating a Docker-based Extension

```python
from localstack.extensions.utils import ProxiedDockerContainerExtension
from werkzeug.datastructures import Headers

class MyExtension(ProxiedDockerContainerExtension):
    name = "my-extension"

    def __init__(self):
        super().__init__(
            image_name="my-docker-image:latest",
            container_ports=[8080],
            host="myext.localhost.localstack.cloud",
        )

    def should_proxy_request(self, headers: Headers) -> bool:
        # Define your routing logic
        return "myext" in headers.get("Host", "")
```

## Dependencies

This library requires LocalStack to be installed as it uses various LocalStack utilities for Docker management and networking.

## License

The code in this repo is available under the Apache 2.0 license.
