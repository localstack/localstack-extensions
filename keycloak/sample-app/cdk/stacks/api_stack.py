from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as lambda_,
    aws_apigateway as apigw,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    RemovalPolicy,
)
from constructs import Construct
import os


class KeycloakSampleApiStack(Stack):
    """
    Sample API stack demonstrating Keycloak integration with AWS services.

    Creates:
    - DynamoDB table for user data
    - Lambda authorizer for JWT validation
    - Lambda function for user CRUD operations
    - API Gateway REST API
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # DynamoDB table for users
        users_table = dynamodb.Table(
            self,
            "UsersTable",
            table_name="keycloak-sample-users",
            partition_key=dynamodb.Attribute(
                name="username", type=dynamodb.AttributeType.STRING
            ),
            removal_policy=RemovalPolicy.DESTROY,
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        )

        # Lambda layer directory (relative to cdk directory)
        lambda_dir = os.path.join(os.path.dirname(__file__), "..", "..", "lambda")

        # Lambda authorizer for JWT validation
        authorizer_fn = lambda_.Function(
            self,
            "AuthorizerFunction",
            function_name="keycloak-jwt-authorizer",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.handler",
            code=lambda_.Code.from_asset(os.path.join(lambda_dir, "authorizer")),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "KEYCLOAK_URL": "http://keycloak.localhost.localstack.cloud:4566",
                "KEYCLOAK_REALM": "localstack",
                "EXPECTED_AUDIENCE": "localstack-client",
            },
        )

        # Lambda function for user CRUD operations
        users_fn = lambda_.Function(
            self,
            "UsersFunction",
            function_name="keycloak-sample-users",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="handler.handler",
            code=lambda_.Code.from_asset(os.path.join(lambda_dir, "users")),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "USERS_TABLE": users_table.table_name,
            },
        )

        # Grant DynamoDB access to users function
        users_table.grant_read_write_data(users_fn)

        # API Gateway REST API
        api = apigw.RestApi(
            self,
            "KeycloakSampleApi",
            rest_api_name="Keycloak Sample API",
            description="Sample API demonstrating Keycloak JWT authentication",
            deploy_options=apigw.StageOptions(stage_name="prod"),
        )

        # Token authorizer
        authorizer = apigw.TokenAuthorizer(
            self,
            "KeycloakAuthorizer",
            handler=authorizer_fn,
            identity_source="method.request.header.Authorization",
            results_cache_ttl=Duration.seconds(0),  # Disable caching for testing
        )

        # Lambda integration for users
        users_integration = apigw.LambdaIntegration(users_fn)

        # /users resource
        users_resource = api.root.add_resource("users")

        # GET /users - List all users
        users_resource.add_method(
            "GET",
            users_integration,
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.CUSTOM,
        )

        # POST /users - Create user
        users_resource.add_method(
            "POST",
            users_integration,
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.CUSTOM,
        )

        # /users/{username} resource
        user_resource = users_resource.add_resource("{username}")

        # GET /users/{username} - Get specific user
        user_resource.add_method(
            "GET",
            users_integration,
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.CUSTOM,
        )

        # PUT /users/{username} - Update user
        user_resource.add_method(
            "PUT",
            users_integration,
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.CUSTOM,
        )

        # DELETE /users/{username} - Delete user
        user_resource.add_method(
            "DELETE",
            users_integration,
            authorizer=authorizer,
            authorization_type=apigw.AuthorizationType.CUSTOM,
        )
