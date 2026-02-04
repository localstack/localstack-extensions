import * as cdk from "aws-cdk-lib";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as apigateway from "aws-cdk-lib/aws-apigateway";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as s3deploy from "aws-cdk-lib/aws-s3-deployment";
import * as path from "path";
import { Construct } from "constructs";

export class MovieSearchStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const dataBucket = new s3.Bucket(this, "MovieDataBucket", {
      bucketName: "movie-search-data",
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    new s3deploy.BucketDeployment(this, "DeployMovieData", {
      sources: [s3deploy.Source.asset(path.join(__dirname, "../data"))],
      destinationBucket: dataBucket,
    });

    const paradeDbEnv = {
      PARADEDB_HOST: "paradedb.localhost.localstack.cloud",
      PARADEDB_PORT: "4566",
      PARADEDB_DATABASE: "mydatabase",
      PARADEDB_USER: "myuser",
      PARADEDB_PASSWORD: "mypassword",
      DATA_BUCKET: dataBucket.bucketName,
    };

    const lambdaDir = path.join(__dirname, "../lambda");
    const getLambdaCode = () => {
      return lambda.Code.fromAsset(lambdaDir, {
        bundling: {
          image: lambda.Runtime.NODEJS_22_X.bundlingImage,
          command: [
            "bash",
            "-c",
            [
              "npm install --prefix /asset-input",
              "npx esbuild /asset-input/index.ts --bundle --platform=node --target=node22 --outfile=/asset-output/index.js",
            ].join(" && "),
          ],
          local: {
            tryBundle(outputDir: string) {
              const { spawnSync } = require("child_process");
              try {
                const npmResult = spawnSync("npm", ["install"], {
                  cwd: lambdaDir,
                  stdio: "inherit",
                });
                if (npmResult.status !== 0) return false;

                const esbuildResult = spawnSync(
                  "npx",
                  [
                    "esbuild",
                    "index.ts",
                    "--bundle",
                    "--platform=node",
                    "--target=node22",
                    `--outfile=${outputDir}/index.js`,
                  ],
                  { cwd: lambdaDir, stdio: "inherit" }
                );
                return esbuildResult.status === 0;
              } catch {
                return false;
              }
            },
          },
        },
      });
    };

    const searchHandler = new lambda.Function(this, "SearchHandler", {
      runtime: lambda.Runtime.NODEJS_22_X,
      handler: "index.searchHandler",
      code: getLambdaCode(),
      environment: paradeDbEnv,
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
    });

    const movieDetailHandler = new lambda.Function(this, "MovieDetailHandler", {
      runtime: lambda.Runtime.NODEJS_22_X,
      handler: "index.movieDetailHandler",
      code: getLambdaCode(),
      environment: paradeDbEnv,
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
    });

    const initHandler = new lambda.Function(this, "InitHandler", {
      runtime: lambda.Runtime.NODEJS_22_X,
      handler: "index.initHandler",
      code: getLambdaCode(),
      environment: paradeDbEnv,
      timeout: cdk.Duration.seconds(60),
      memorySize: 256,
    });

    const seedHandler = new lambda.Function(this, "SeedHandler", {
      runtime: lambda.Runtime.NODEJS_22_X,
      handler: "index.seedHandler",
      code: getLambdaCode(),
      environment: paradeDbEnv,
      timeout: cdk.Duration.seconds(120),
      memorySize: 512,
    });

    dataBucket.grantRead(seedHandler);

    const api = new apigateway.RestApi(this, "MovieSearchApi", {
      restApiName: "Movie Search API",
      description: "API for searching movies using ParadeDB",
      deployOptions: {
        stageName: "dev",
      },
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
      },
    });

    // Custom ID for consistent API Gateway URL across deployments
    cdk.Tags.of(api).add("_custom_id_", "movie-search-api");

    const searchResource = api.root.addResource("search");
    searchResource.addMethod(
      "GET",
      new apigateway.LambdaIntegration(searchHandler)
    );

    const moviesResource = api.root.addResource("movies");
    const movieIdResource = moviesResource.addResource("{id}");
    movieIdResource.addMethod(
      "GET",
      new apigateway.LambdaIntegration(movieDetailHandler)
    );

    const adminResource = api.root.addResource("admin");
    const initResource = adminResource.addResource("init");
    initResource.addMethod(
      "POST",
      new apigateway.LambdaIntegration(initHandler)
    );

    const seedResource = adminResource.addResource("seed");
    seedResource.addMethod(
      "POST",
      new apigateway.LambdaIntegration(seedHandler)
    );

    new cdk.CfnOutput(this, "ApiEndpoint", {
      value: api.url,
    });

    new cdk.CfnOutput(this, "SearchEndpoint", {
      value: `${api.url}search`,
    });

    new cdk.CfnOutput(this, "MoviesEndpoint", {
      value: `${api.url}movies/{id}`,
    });

    new cdk.CfnOutput(this, "InitEndpoint", {
      value: `${api.url}admin/init`,
    });

    new cdk.CfnOutput(this, "SeedEndpoint", {
      value: `${api.url}admin/seed`,
    });

    new cdk.CfnOutput(this, "DataBucketName", {
      value: dataBucket.bucketName,
    });
  }
}
