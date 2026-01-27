# WireMock Chat Backend Sample App

A CDK application demonstrating integration with WireMock-mocked OpenAI APIs running in LocalStack.

## Overview

This sample app deploys a serverless chat backend using:

- **AWS Lambda** - Handles API requests
- **Amazon API Gateway** - REST API endpoints
- **WireMock** - Mocks OpenAI API responses

### API Endpoints

| Method | Endpoint  | Description                              |
|--------|-----------|------------------------------------------|
| GET    | /models   | List available AI models                 |
| POST   | /chat     | Send a chat message                      |

### WireMock OpenAI Endpoints Used

- `GET /models` - Returns list of available models
- `POST /chat/completions` - Chat completion response

## Prerequisites

- [LocalStack](https://localstack.cloud/) installed
- [Node.js](https://nodejs.org/) 18+ installed
- [AWS CDK Local](https://github.com/localstack/aws-cdk-local) (`npm install -g aws-cdk-local`)
- WireMock extension configured with OpenAI stubs

## Setup

### 1. Start LocalStack with WireMock Extension

To use the OpenAI mock, you need to [create the mock API in WireMock Cloud](https://app.wiremock.cloud/mock-apis/create-flow), then pull the configuration locally. Follow the instructions in the [WireMock README](../README.md) to create the mock API and pull the configuration.

Once pulled, the configuration will be in the `.wiremock` directory.

```bash
LOCALSTACK_WIREMOCK_API_TOKEN="<your-wiremock-api-token>" \
LOCALSTACK_WIREMOCK_CONFIG_DIR="/path/to/.wiremock" \
localstack start
```

### 2. Install Dependencies

```bash
cd wiremock/sample-app-runner
npm install
```

### 3. Bootstrap CDK

```bash
cdklocal bootstrap
```

### 4. Deploy the Stack

```bash
cdklocal deploy
```

After deployment, you'll see output similar to:
```
Outputs:
WiremockChatStack.ApiEndpoint = https://<api-id>.execute-api.localhost.localstack.cloud:4566/dev/
WiremockChatStack.ChatApiEndpoint = https://<api-id>.execute-api.localhost.localstack.cloud:4566/dev/chat
WiremockChatStack.ModelsEndpoint = https://<api-id>.execute-api.localhost.localstack.cloud:4566/dev/models
```

## Usage

### List Available Models

```bash
curl https://<api-id>.execute-api.localhost.localstack.cloud:4566/dev/models
```

### Send a Chat Message

```bash
curl -X POST https://<api-id>.execute-api.localhost.localstack.cloud:4566/dev/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, how are you?"}'
```

## Testing

```bash
npm test
```

## How It Works

1. **GET /models**: Lambda fetches the list of available models from WireMock's `/models` endpoint and returns them.

2. **POST /chat**: Lambda calls WireMock's `/chat/completions` endpoint with the user's message and returns the AI response along with usage statistics.
