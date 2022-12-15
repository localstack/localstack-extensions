Miniflare LocalStack extension
================================

This extension makes [Miniflare](https://miniflare.dev) (dev environment for Cloudflare workers) available directly in LocalStack!

## Installing

```bash
localstack extensions install "git+https://github.com/localstack/localstack-extensions/#egg=localstack-extension-hello-world&subdirectory=miniflare"
```

## How to use

To publish the sample application to Miniflare running in LocalStack, we can use the `wrangler` CLI with the following environment variables for local dev mode:
```
export CLOUDFLARE_API_TOKEN=test CLOUDFLARE_API_BASE_URL=http://localhost:4566/miniflare
wrangler publish
```

Once deployed, the Cloudflare worker can be easily invoked via `curl`:
```
$ curl http://hello.miniflare.localhost.localstack.cloud:4566/test
Hello World!
```