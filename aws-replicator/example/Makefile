usage:           ## Show this help
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sed -e 's/:.*##\s*/##/g' | awk -F'##' '{ printf "%-15s %s\n", $$1, $$2 }'

test:            ## Run the end-to-end test with a simple sample app
	echo "Deploying sample application ..."; \
		echo "Creating SQS queue in real AWS"; \
		aws sqs create-queue --queue-name test-queue1; \
		queueUrl=$$(aws sqs get-queue-url --queue-name test-queue1 | jq -r .QueueUrl); \
		echo "Starting AWS replicator proxy"; \
		(DEBUG=1 localstack aws proxy -s s3,sqs & ); \
		echo "Deploying Terraform template locally"; \
		tflocal init; \
		tflocal apply -auto-approve; \
		echo "Puting a message to the queue in real AWS"; \
		aws sqs send-message --queue-url $$queueUrl --message-body '{"test":"foobar 123"}'; \
		echo "Waiting a bit for Lambda to be triggered by SQS message ..."; \
		sleep 7 # ; \
	# TODO: Lambda invocation currently failing in CI:
	#    [lambda e4cbf96395d8b7d8a94596f96de9ef7d] time="2023-09-16T22:12:04Z" level=panic msg="Post
	#    \"http://172.17.0.2:443/_localstack_lambda/e4cbf96395d8b7d8a94596f96de9ef7d/status/e4cbf96395d8b7d8a94596f96de9ef7d/ready\":
	#    dial tcp 172.17.0.2:443: connect: connection refused" func=go.amzn.com/lambda/rapid.handleStart
	#    file="/home/runner/work/lambda-runtime-init/lambda-runtime-init/lambda/rapid/start.go:473"
#		logStream=$$(awslocal logs describe-log-streams --log-group-name /aws/lambda/func1 | jq -r '.logStreams[0].logStreamName'); \
#		awslocal logs get-log-events --log-stream-name "$$logStream" --log-group-name /aws/lambda/func1 | grep "foobar 123"; \
#		exitCode=$$?; \
#		echo "Cleaning up ..."; \
#		aws sqs delete-queue --queue-url $$queueUrl; \
#		exit $$exitCode

.PHONY: usage test
