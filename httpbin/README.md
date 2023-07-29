LocalStack httpbin extension
===============================

A simple HTTP Request & Response Service directly in LocalStack
using [httpbin](https://github.com/postmanlabs/httpbin).
Get the full httpbin experience directly in LocalStack without connecting to httpbin.org!

The httpbin API is served through the hostname `http://httpbin.localhost.localstack.cloud:4566`.

## Install

Install the extension by running:

```bash
localstack extensions install localstack-extension-httpbin
```

## Usage

Opening http://httpbin.localhost.localstack.cloud:4566 in the browser will show you the flasgger UI:
![Screenshot at 2023-07-27 14-33-03](https://github.com/localstack/localstack-extensions/assets/3996682/68442f91-13b8-4308-8f04-966340cff082)

And you can call the API endpoints just as you would httpbin.org.
![Screenshot at 2023-07-27 14-34-15](https://github.com/localstack/localstack-extensions/assets/3996682/bebe444a-d6f9-4953-87ef-cca79daa00e8)

## Development

### Install local development version

To install the extension into localstack in developer mode, you will need Python 3.10, and create a virtual
environment in the extensions project.

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

## Licensing

* httpbin is licensed under the ISC license: https://github.com/postmanlabs/httpbin/blob/master/LICENSE
* The httpbin source code is vendored with this extension, slight modifications were made to make it
  compatible with the latest Python and Werkzeug version.
  The modifications retain the ISC license
* The extension code is licensed under the Apache 2.0 License
