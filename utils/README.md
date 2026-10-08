LocalStack Extensions Utils
===========================

A utility library providing common functionality for building [LocalStack Extensions](https://github.com/localstack/localstack-extensions).

## Usage

To use this library in your LocalStack extension, add it to the `dependencies` in your extension's `pyproject.toml`:

```toml
[project]
dependencies = [
    "localstack-extensions-utils",
]
```

Then import the utilities in your extension code, for example:

```python
from localstack_extensions.utils import ProxiedDockerContainerExtension

...
```

## Dependencies

This library requires LocalStack to be installed as it uses various LocalStack utilities for Docker management and networking.

## License

The code in this repo is available under the Apache 2.0 license.
