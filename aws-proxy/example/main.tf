
resource "aws_lambda_function" "test" {
  function_name = "func1"
  role          = "arn:aws:iam::000000000000:role/test-role"

  s3_bucket = "hot-reload"
  s3_key    = path.cwd

  handler       = "lambda.handler"
  runtime       = "python3.8"
}

resource "aws_sqs_queue" "test" {
  name = "test-queue1"
}

resource "aws_lambda_event_source_mapping" "test" {
  event_source_arn = aws_sqs_queue.test.arn
  function_name    = aws_lambda_function.test.arn
}
