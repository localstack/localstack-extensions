# LocalStack Extensions (beta)

With LocalStack 1.0 we have introduced LocalStack Extensions that allow
developers to extend and customize LocalStack. Both the feature and the API
are currently experimental.

## Using Extensions

Extensions are a LocalStack Pro feature.
To use and install extensions, use the CLI to first log in to your account

```bash
localstack login
Please provide your login credentials below
...
```

```bash
localstack extensions --help

Usage: localstack extensions [OPTIONS] COMMAND [ARGS]...

  Manage LocalStack extensions (beta)

Options:
  --help  Show this message and exit.

Commands:
  init       Initialize the LocalStack extensions environment
  install    Install a LocalStack extension
  uninstall  Remove a LocalStack extension
```

## Developing Extensions

### The extensions API

LocalStack exposes a Python API for building extensions that can be found in
the core codebase in
[`localstack.extensions.api`](https://github.com/localstack/localstack/tree/v1/localstack/extensions/api).

The basic interface to implement is as follows:

```python
class Extension(BaseExtension):
    """
    An extension that is loaded into LocalStack dynamically.
    The method execution order of an extension is as follows:
    - on_extension_load
    - on_platform_start
    - update_gateway_routes
    - update_request_handlers
    - update_response_handlers
    - on_platform_ready
    """

    namespace: str = "localstack.extensions"

    name: str # needs to be set by the subclass

    def on_extension_load(self):
        """
        Called when LocalStack loads the extension.
        """
        pass

    def on_platform_start(self):
        """
        Called when LocalStack starts the main runtime.
        """
        pass

    def update_gateway_routes(self, router: Router[RouteHandler]):
        """
        Called with the Router attached to the LocalStack gateway. Overwrite this to add or update routes.
        :param router: the Router attached in the gateway
        """
        pass

    def update_request_handlers(self, handlers: CompositeHandler):
        """
        Called with the custom request handlers of the LocalStack gateway. Overwrite this to add or update handlers.
        :param handlers: custom request handlers of the gateway
        """
        pass

    def update_response_handlers(self, handlers: CompositeResponseHandler):
        """
        Called with the custom response handlers of the LocalStack gateway. Overwrite this to add or update handlers.
        :param handlers: custom response handlers of the gateway
        """
        pass

    def on_platform_ready(self):
        """
        Called when LocalStack is ready and the Ready marker has been printed.
        """
        pass
```

A minimal example would look like this:

```python
import logging
from localstack.extensions.api import Extension

LOG = logging.getLogger(__name__)

class ReadyAnnoucerExtension(Extension):
	name = "my_ready_annoucer"

    def on_platform_ready(self):
    	LOG.info("my plugin is laded and localstack is ready to roll!")
```

### Package your Extension

LocalStack uses the [Plux](https://github.com/localstack/plux) code loading
framework to load your code from a Python entrypoint. You can either use Plux
to discover the entrypoints from your code, or manually define them.

In any case, your extensions needs to be packaged as a Python distribution
with a `setup.cfg` or `setup.py` config. A minimal `setup.cfg` for your
extension would look like this:

```toml
[metadata]
name = localstack-extension-ready-announcer
description = LocalStack Extension to annouce when localstack is Ready
author = Your Name
author_email = your@email.com
url = https://link-to-your-project

[options]
zip_safe = False
packages = find:
install_requires =
    localstack>=1.0.0
```
