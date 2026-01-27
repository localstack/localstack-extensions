LocalStack Extensions Utils
===========================

A utility library providing common functionality for building [LocalStack Extensions](https://github.com/localstack/localstack-extensions).

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
from localstack_extensions.utils import ProxiedDockerContainerExtension
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
