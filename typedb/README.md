TypeDB on LocalStack
=====================

This repo contains a [LocalStack Extension](https://github.com/localstack/localstack-extensions) that facilitates developing [TypeDB](https://typedb.com)-based applications locally.

After installing the extension, a TypeDB server instance will become available under `typedb.localhost.localstack.cloud:4566`, allowing you to create and manage TypeDB databases directly from your AWS applications running in LocalStack.

For example, you could create a microservice backed by a Lambda function that connects to a TypeDB database upon invocation. See [here](https://github.com/typedb-osi/typedb-localstack-demo) for a simple example application that makes use of this extension.

## Configuration

The following environment variables can be passed to the LocalStack container (make sure to prefix them with `LOCALSTACK_...` when using the `localstack start` CLI), to steer the behavior of the extension:

* `TYPEDB_FLAGS`: Additional user-defined command args to pass to the TypeDB container.
* `TYPEDB_HTTP2_PROXY`: Flag to enable/disable HTTP2 proxy for gRPC traffic (use this if you experience network issues, and use the HTTP variant of the TypeDB driver).

## Prerequisites

* Docker
* LocalStack Pro (free trial available)
* `localstack` CLI
* `make`

## Install from GitHub repository

This extension can be installed directly from this Github repo via:

```bash
localstack extensions install "git+https://github.com/localstack/localstack-extensions.git#egg=typedb&subdirectory=typedb"
```

## Install local development version

Please refer to the docs [here](https://github.com/localstack/localstack-extensions?tab=readme-ov-file#start-localstack-with-the-extension) for instructions on how to start the extension in developer mode.

## License

The code in this repo is available under the Apache 2.0 license.
