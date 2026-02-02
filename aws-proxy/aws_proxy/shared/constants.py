# header name for the original request host name forwarded in the request to the target proxy handler
HEADER_HOST_ORIGINAL = "x-ls-host-original"

# Mapping from AWS service signing names to boto3 client names
SERVICE_NAME_MAPPING = {
    "monitoring": "cloudwatch",
    "sqs-query": "sqs",
}
