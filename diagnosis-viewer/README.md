Diagnosis Viewer
===============================

View the diagnostics endpoint directly in localstack

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

You can then start LocalStack with `EXTENSION_DEV_MODE=1` to load all enabled extensions.
Make sure to also set `DEBUG=1` so the diagnose endpoint necessary to populate the report is loaded.

```bash
EXTENSION_DEV_MODE=1 DEBUG=1 localstack start
```

## Access Diagnosis Data

The extension is a web UI for the diagnosis endpoint of LocalStack, which is enabled when LocalStack is started with `DEBUG=1` and available at `curl -s localhost:4566/_localstack/diagnose`.
The web UI can then be reached at `http://localhost:4566/diapretty`.

## Install from GitHub repository

To distribute your extension, simply upload it to your github account. Your extension can then be installed via:

```bash
localstack extensions install "git+https://github.com/localstack/diagnosis-viewer/#egg=diagnosis-viewer"
```