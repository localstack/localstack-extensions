Miniflare LocalStack extension (experimental)
=============================================
[![Install LocalStack Extension](https://localstack.cloud/gh/extension-badge.svg)](https://app.localstack.cloud/extensions/remote?url=git+https://github.com/localstack/localstack-extensions/#egg=localstack-extension-miniflare&subdirectory=miniflare)

This extension makes [Miniflare](https://miniflare.dev) (dev environment for Cloudflare workers) available directly in LocalStack!

⚠️ Please note that this extension is experimental and currently under active development.

## Installing

```bash
localstack extensions install "git+https://github.com/localstack/localstack-extensions/#egg=localstack-extension-miniflare&subdirectory=miniflare"
```

## How to use

To publish the sample application to Miniflare running in LocalStack, we can use the `wrangler` CLI with the following environment variables for local dev mode:
```
export CLOUDFLARE_API_TOKEN=test
export CLOUDFLARE_API_BASE_URL=http://localhost:4566/miniflare
wrangler publish
```

Note: if you're having troubles with this configuration, e.g., seeing "Fetch failed" error messages on `wrangler publish`, try using this API endpoint instead:
```
export CLOUDFLARE_API_BASE_URL=https://localhost.localstack.cloud:4566/miniflare
```

Once deployed, the Cloudflare worker can be easily invoked via `curl`:
```
$ curl http://hello.miniflare.localhost.localstack.cloud:4566/test
Hello World!
```

## Change Log

* `0.1.2`: Pin wrangler version to fix hanging miniflare invocations; fix encoding headers for invocation responses
* `0.1.1`: Adapt for LocalStack v3.0
* `0.1.0`: Upgrade to Miniflare 3.0
* `0.0.1`: Initial version.

## License

The `cloudflare/miniflare` package and related tooling is licensed under the MIT License.

The code of this LocalStack Extension is published under the Apache 2.0 license.
