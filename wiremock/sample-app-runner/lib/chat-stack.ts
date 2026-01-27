import * as cdk from "aws-cdk-lib";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as apigateway from "aws-cdk-lib/aws-apigateway";
import * as path from "path";
import { Construct } from "constructs";

export class ChatStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Lambda function for handling chat and models requests
    const chatHandler = new lambda.Function(this, "ChatHandler", {
      runtime: lambda.Runtime.NODEJS_20_X,
      handler: "index.handler",
      code: lambda.Code.fromAsset(path.join(__dirname, "../lambda"), {
        bundling: {
          image: lambda.Runtime.NODEJS_20_X.bundlingImage,
          command: [
            "bash",
            "-c",
            [
              "npm install --prefix /asset-input",
              "npx esbuild /asset-input/index.ts --bundle --platform=node --target=node20 --outfile=/asset-output/index.js",
            ].join(" && "),
          ],
          local: {
            tryBundle(outputDir: string) {
              const { execSync } = require("child_process");
              try {
                execSync(
                  `cd ${path.join(__dirname, "../lambda")} && npm install && npx esbuild index.ts --bundle --platform=node --target=node20 --outfile=${outputDir}/index.js`
                );
                return true;
              } catch {
                return false;
              }
            },
          },
        },
      }),
      environment: {
        WIREMOCK_BASE_URL: "http://wiremock.localhost.localstack.cloud:4566",
      },
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
    });

    // REST API Gateway
    const api = new apigateway.RestApi(this, "ChatApi", {
      restApiName: "WireMock Chat API",
      description: "API for chat backend using WireMock OpenAI mocks",
      deployOptions: {
        stageName: "dev",
      },
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
      },
    });

    // Lambda integration
    const lambdaIntegration = new apigateway.LambdaIntegration(chatHandler, {
      requestTemplates: { "application/json": '{ "statusCode": "200" }' },
    });

    // GET /models endpoint
    const modelsResource = api.root.addResource("models");
    modelsResource.addMethod("GET", lambdaIntegration);

    // POST /chat endpoint
    const chatResource = api.root.addResource("chat");
    chatResource.addMethod("POST", lambdaIntegration);

    // Outputs
    new cdk.CfnOutput(this, "ApiEndpoint", {
      value: api.url,
      description: "API Gateway endpoint URL",
    });

    new cdk.CfnOutput(this, "ModelsEndpoint", {
      value: `${api.url}models`,
      description: "GET /models endpoint",
    });

    new cdk.CfnOutput(this, "ChatEndpoint", {
      value: `${api.url}chat`,
      description: "POST /chat endpoint",
    });
  }
}
