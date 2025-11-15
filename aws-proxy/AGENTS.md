# AI Agent Instructions for AWS Proxy Extension

This repo is a LocalStack extension (plugin) that enables a "proxy mode" - proxying requests for certain AWS services (e.g., S3) to the upstream real AWS cloud, while handling the remaining services locally.

## Testing

The proxy functionality is covered by integration tests in the `tests/` folder, one file for each different service.

To add a test, follow the pattern in the existing tests.
It usually involves creating two boto3 clients, one for the LocalStack connection, and one for the real upstream AWS cloud.
We then run API requests with both clients and assert that the results are identical, thereby ensuring that the proxy functionality is working properly.

You can assume that test AWS credentials are configured in the shell environment where the AI agent is running.
