# AWS Proxy Example

This simple example illustrates how to use the AWS proxy in this extension to transparently run API requests against real AWS.

1. First, make sure that the extension is installed and LocalStack is up and running

2. Open a new terminal, configure the AWS credentials of your real AWS account, then start the proxy to forward requests for S3 and SQS to real AWS:
```
$ DEBUG=1 localstack aws proxy -s s3,sqs
```

3. In another terminal, again configure the credentials to point to real AWS, then create an SQS queue (alternatively you can create the queue via the AWS Web console):
```
$ aws sqs create-queue --queue-name test-queue1
```

4. Use `tflocal` to deploy the sample Terraform script against LocalStack:
```
$ tflocal init
$ tflocal apply -
```

5. Open the AWS console (or use the CLI) and put a new message to the `test-queue1` SQS queue.

6. The last command should have triggered a Lambda function invocation in LocalStack, via the SQS event source mapping defined in the Terraform script. If we take a close look at the Lambda output, it should print the S3 buckets of the real AWs account (as S3 requests are also forwarded by the proxy).
```
>START RequestId: 4692b634-ccf1-1e23-0cd1-8831ddf8c35f Version: $LATEST
> [{'Name': 'my-bucket-1', ...}, {'Name': 'my-bucket-2', ...}]
> END RequestId: 4692b634-ccf1-1e23-0cd1-8831ddf8c35f
```