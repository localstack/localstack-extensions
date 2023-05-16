#!/bin/bash

export AWS_DEFAULT_REGION="us-east-1"
export CLOUDFLARE_API_TOKEN=test
export CLOUDFLARE_API_BASE_URL=http://localhost:4566/miniflare

# create resources in LocalStack
# awslocal rds create-db-instance AWS_AURORA_TABLE ...
queueUrl=$(awslocal sqs create-queue --queue-name q1 | jq -r .QueueUrl)

# set wrangler secrets
echo "test" | wrangler secret put AWS_AURORA_RESOURCE_ARN
echo "test" | wrangler secret put AWS_AURORA_SECRET_ARN
echo "test" | wrangler secret put AWS_ACCESS_KEY_ID
echo "test" | wrangler secret put AWS_SECRET_ACCESS_KEY
echo "$queueUrl" | wrangler secret put AWS_SQS_QUEUE_URL

# publish worker script
wrangler publish

workerEndpoint=http://worker-aws.miniflare.localhost.localstack.cloud:4566/test
echo "Deployment done. You can now invoke the worker via:"
echo "curl $workerEndpoint"

curl $workerEndpoint
awslocal sqs receive-message --queue-url $queueUrl
