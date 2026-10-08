{{ cookiecutter.project_name }}
===============================

{{ cookiecutter.project_short_description }}

## Install local development version

To install the extension into localstack in developer mode, you will need Python 3.10, and create a virtual environment in the extensions project.

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

## Publish to PyPI

To distribute your extension, publish it to PyPI with `make publish`. It can then be installed via:

```bash
localstack extensions install {{ cookiecutter.project_slug }}
```
