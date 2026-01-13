terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

output "api_endpoint" {
  description = "The invoke URL for the deployed API stage."
  value       = "${aws_api_gateway_stage.dev_stage.invoke_url}/${aws_api_gateway_resource.time_off_resource.path_part}"
}

variable "aws_region" {
  description = "The AWS region to deploy the resources in."
  type        = string
  default     = "us-east-1"
}

# 1. Package the Lambda function code
resource "null_resource" "package_lambda" {
  triggers = {
    handler_hash      = filebase64sha256("${path.module}/src/handler.py")
    requirements_hash = filebase64sha256("${path.module}/src/requirements.txt")
  }

  provisioner "local-exec" {
    command = <<-EOT
      rm -rf "${path.module}/build"
      mkdir -p "${path.module}/build"
      cp "${path.module}/src/handler.py" "${path.module}/build/"
      pip install -r "${path.module}/src/requirements.txt" -t "${path.module}/build"
    EOT
    interpreter = ["/bin/bash", "-c"]
  }
}

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/build"
  output_path = "${path.module}/lambda_function.zip"
  depends_on  = [null_resource.package_lambda]
}

# 2. Create an IAM role for the Lambda function
resource "aws_iam_role" "lambda_exec_role" {
  name = "hr_info_lambda_exec_role"

  assume_role_policy = jsonencode({
    Version   = "2012-10-17",
    Statement = [{
      Action    = "sts:AssumeRole",
      Effect    = "Allow",
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

# 3. Attach the basic Lambda execution policy to the role
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# 4. Create the Lambda function
resource "aws_lambda_function" "hr_info_lambda" {
  function_name = "hr_info_lambda"
  role          = aws_iam_role.lambda_exec_role.arn

  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  handler = "handler.get_time_off"
  runtime = "python3.9"

  # Add a timeout for the function
  timeout = 10
}

# 5. Create an API Gateway REST API
resource "aws_api_gateway_rest_api" "hr_api" {
  name        = "hr_info_api"
  description = "API for retrieving company HR information"
}

# 6. Create a resource in the API (e.g., /time-off)
resource "aws_api_gateway_resource" "time_off_resource" {
  rest_api_id = aws_api_gateway_rest_api.hr_api.id
  parent_id   = aws_api_gateway_rest_api.hr_api.root_resource_id
  path_part   = "time-off"
}

# 7. Create a GET method for the /time-off resource
resource "aws_api_gateway_method" "get_method" {
  rest_api_id   = aws_api_gateway_rest_api.hr_api.id
  resource_id   = aws_api_gateway_resource.time_off_resource.id
  http_method   = "GET"
  authorization = "NONE"
}

# 8. Integrate the GET method with the Lambda function
resource "aws_api_gateway_integration" "lambda_integration" {
  rest_api_id = aws_api_gateway_rest_api.hr_api.id
  resource_id = aws_api_gateway_resource.time_off_resource.id
  http_method = aws_api_gateway_method.get_method.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.hr_info_lambda.invoke_arn
}

# 9. Grant API Gateway permission to invoke the Lambda function
resource "aws_lambda_permission" "api_gateway_permission" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.hr_info_lambda.function_name
  principal     = "apigateway.amazonaws.com"

  source_arn = "${aws_api_gateway_rest_api.hr_api.execution_arn}/*/${aws_api_gateway_method.get_method.http_method}${aws_api_gateway_resource.time_off_resource.path}"
}

# 10. Deploy the API
resource "aws_api_gateway_deployment" "api_deployment" {
  rest_api_id = aws_api_gateway_rest_api.hr_api.id

  # Terraform needs a trigger to create a new deployment
  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.time_off_resource.id,
      aws_api_gateway_method.get_method.id,
      aws_api_gateway_integration.lambda_integration.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

# 11. Create a stage for the deployment
resource "aws_api_gateway_stage" "dev_stage" {
  deployment_id = aws_api_gateway_deployment.api_deployment.id
  rest_api_id   = aws_api_gateway_rest_api.hr_api.id
  stage_name    = "dev"
}
