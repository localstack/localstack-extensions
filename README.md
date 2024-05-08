# LocalStack Extensions (Preview)

<p align="center">
  <img src="https://github.com/localstack/localstack-extensions/assets/3996682/bba99a4a-e479-4da9-ba3e-1ea9ce80f9b7" alt="LocalStack Extensions">
</p>


With LocalStack 1.0 we have introduced LocalStack Extensions that allow
developers to extend and customize LocalStack. Both the feature and the API
are currently in preview and may be subject to change.

## Using Extensions

Extensions are a LocalStack Pro feature.
To use and install extensions, use the CLI to first log in to your account

```console
$ localstack auth login
Please provide your login credentials below
Username: ...
```

```console
$ localstack extensions --help

Usage: localstack extensions [OPTIONS] COMMAND [ARGS]...

  (Preview) Manage LocalStack extensions.

  LocalStack Extensions allow developers to extend and customize LocalStack.
  The feature and the API are currently in a preview stage and may be subject to change.

  Visit https://docs.localstack.cloud/references/localstack-extensions/
  for more information on LocalStack Extensions.

Options:
  -v, --verbose  Print more output
  -h, --help     Show this message and exit.

Commands:
  dev        Developer tools for developing LocalStack extensions.
  init       Initialize the LocalStack extensions environment.
  install    Install a LocalStack extension.
  list       List installed extension.
  uninstall  Remove a LocalStack extension.

```

To install an extension, specify the name of the pip dependency that contains
the extension. For example, for the official Stripe extension, you can either
use the package distributed on pypi:

```console
$ localstack extensions install localstack-extension-httpbin
```

or you can install the latest version directly from this Git repository

```console
$ localstack extensions install "git+https://github.com/localstack/localstack-extensions/#egg=localstack-extension-httpbin&subdirectory=httpbin"
```

## Official LocalStack Extensions

Here is the current list of extensions developed by the LocalStack team and their support status.
You can install the respective extension by calling `localstack install <Install name>`.

| Extension | Install name | Version | Support status |
| --------- | ------------ | ------- | -------------- |
| [AWS replicator](https://github.com/localstack/localstack-extensions/tree/main/aws-replicator) | localstack-extension-aws-replicator | 0.1.7 | Experimental |
| [Diagnosis Viewer](https://github.com/localstack/localstack-extensions/tree/main/diagnosis-viewer) | localstack-extension-diagnosis-viewer | 0.1.0 | Stable |
| [Hello World](https://github.com/localstack/localstack-extensions/tree/main/hello-world) | localstack-extension-hello-world | 0.1.0 | Stable |
| [httpbin](https://github.com/localstack/localstack-extensions/tree/main/httpbin) | localstack-extension-httpbin | 0.1.0 | Stable |
| [MailHog](https://github.com/localstack/localstack-extensions/tree/main/mailhog) | localstack-extension-mailhog | 0.1.0 | Stable |
| [Miniflare](https://github.com/localstack/localstack-extensions/tree/main/miniflare) | localstack-extension-miniflare | 0.1.0 | Experimental |
| [Stripe](https://github.com/localstack/localstack-extensions/tree/main/stripe) | localstack-extension-stripe | 0.1.0 | Stable |


## Developing Extensions

This section provides a brief overview of how to develop your own extensions.

### The extensions API

LocalStack exposes a Python API for building extensions that can be found in
the core codebase in
[`localstack.extensions.api`](https://github.com/localstack/localstack/tree/master/localstack/extensions/api).

The basic interface to implement is as follows:

```python
class Extension(BaseExtension):
    """
    An extension that is loaded into LocalStack dynamically. The method
    execution order of an extension is as follows:

    - on_extension_load
    - on_platform_start
    - update_gateway_routes
    - update_request_handlers
    - update_response_handlers
    - on_platform_ready
    - on_platform_shutdown
    """

    namespace: str = "localstack.extensions"
    """The namespace of all basic localstack extensions."""

    name: str
    """The unique name of the extension set by the implementing class."""

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

    def on_platform_shutdown(self):
        """
        Called when LocalStack is shutting down. Can be used to close any resources (threads, processes, sockets, etc.).
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

class ReadyAnnouncerExtension(Extension):
    name = "my_ready_announcer"

    def on_platform_ready(self):
    	LOG.info("my plugin is loaded and localstack is ready to roll!")
```

### Package your Extension

Your extensions needs to be packaged as a Python distribution with a
`setup.cfg` or `setup.py` config. LocalStack uses the
[Plux](https://github.com/localstack/plux) code loading framework to load your
code from a Python [entry point](https://packaging.python.org/en/latest/specifications/entry-points/).
You can either use Plux to discover the entrypoints from your code when
building and publishing your distribution, or manually define them as in the
example below.

A minimal `setup.cfg` for the extension above could look like this:

```ini
[metadata]
name = localstack-extension-ready-announcer
description = LocalStack extension that logs when LocalStack is ready to receive requests
author = Your Name
author_email = your@email.com
url = https://link-to-your-project

[options]
zip_safe = False
packages = find:
install_requires =
    localstack>=1.0.0

[options.entry_points]
localstack.extensions =
    my_ready_announcer = localstack_announcer.extension:ReadyAnnouncerExtension
```

The entry point group is the Plux namespace `locastack.extensions`, and the
entry point name is the plugin name `my_ready_announcer`. The object
reference points to the plugin class.


### Using the extensions CLI

The extensions CLI has a set of developer commands that allow you to create new extensions, and toggle local dev mode for extensions.
Extensions that are toggled for developer mode will be mounted into the localstack container so you don't need to re-install them every time you change something.

```console
Usage: localstack extensions dev [OPTIONS] COMMAND [ARGS]...

  Developer tools for developing Localstack extensions

Options:
  --help  Show this message and exit.

Commands:
  disable  Disables an extension on the host for developer mode.
  enable   Enables an extension on the host for developer mode.
  list     List LocalStack extensions for which dev mode is enabled.
  new      Create a new LocalStack extension from the official extension...
```

#### Creating a new extensions

First, create a new extensions from a template:

```console
 % localstack extensions dev new
project_name [My LocalStack Extension]: 
project_short_description [All the boilerplate you need to create a LocalStack extension.]: 
project_slug [my-localstack-extension]: 
module_name [my_localstack_extension]: 
full_name [Jane Doe]: 
email [jane@example.com]: 
github_username [janedoe]: 
version [0.1.0]: 
```

This will create a new python project with the following layout:

```
my-localstack-extension
├── Makefile
├── my_localstack_extension
│   ├── extension.py
│   └── __init__.py
├── README.md
├── setup.cfg
└── setup.py
```

Then run `make install` in the newly created project to make a distribution package.

#### Start LocalStack with the extension

To start LocalStack with the extension in dev mode, first enable it by running:

```console
localstack extensions dev enable ./my-localstack-extension
```

Then, start LocalStack with `EXTENSION_DEV_MODE=1`

```console
EXTENSION_DEV_MODE=1 LOCALSTACK_API_KEY=... localstack start
```

In the LocalStack logs you should then see something like:
```
==================================================
👷 LocalStack extension developer mode enabled 🏗
- mounting extension /opt/code/extensions/my-localstack-extension
Resuming normal execution, ...
==================================================
```

Now, when you make changes to your extensions, you just need to restart LocalStack and the changes will be picked up by LocalStack automatically.
