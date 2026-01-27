import {
  CloudFormationClient,
  DescribeStacksCommand,
} from "@aws-sdk/client-cloudformation";

const STACK_NAME = "WiremockChatStack";
const LOCALSTACK_ENDPOINT = "http://localhost:4566";

let apiEndpoint: string;

// Response types
interface ModelsResponse {
  success: boolean;
  data: Array<{
    id: string;
    object: string;
    created: number;
    owned_by: string;
  }>;
}

interface ChatResponse {
  success: boolean;
  data: {
    message: string;
    model: string;
    usage: {
      completion_tokens: number;
      prompt_tokens: number;
      total_tokens: number;
    };
  };
}

interface ErrorResponse {
  success: boolean;
  error: string;
}

/**
 * Get the API Gateway endpoint from CloudFormation stack outputs
 */
async function getApiEndpoint(): Promise<string> {
  const client = new CloudFormationClient({
    endpoint: LOCALSTACK_ENDPOINT,
    region: "us-east-1",
    credentials: {
      accessKeyId: "test",
      secretAccessKey: "test",
    },
  });

  const command = new DescribeStacksCommand({ StackName: STACK_NAME });
  const response = await client.send(command);

  const stack = response.Stacks?.[0];
  if (!stack) {
    throw new Error(`Stack ${STACK_NAME} not found`);
  }

  const apiEndpointOutput = stack.Outputs?.find(
    (output) => output.OutputKey === "ApiEndpoint"
  );

  if (!apiEndpointOutput?.OutputValue) {
    throw new Error("ApiEndpoint output not found in stack");
  }

  return apiEndpointOutput.OutputValue;
}

describe("WireMock Chat API", () => {
  beforeAll(async () => {
    apiEndpoint = await getApiEndpoint();
    console.log(`Using API endpoint: ${apiEndpoint}`);
  });

  describe("GET /models", () => {
    it("should return a list of models with correct format", async () => {
      const response = await fetch(`${apiEndpoint}models`);
      const data = (await response.json()) as ModelsResponse;

      // Validate response structure
      expect(response.status).toBe(200);
      expect(data).toHaveProperty("success", true);
      expect(data).toHaveProperty("data");
      expect(Array.isArray(data.data)).toBe(true);

      // Validate each model has required fields
      if (data.data.length > 0) {
        const model = data.data[0];
        expect(model).toHaveProperty("id");
        expect(model).toHaveProperty("object");
        expect(model).toHaveProperty("created");
        expect(model).toHaveProperty("owned_by");

        // Validate field types
        expect(typeof model.id).toBe("string");
        expect(typeof model.object).toBe("string");
        expect(typeof model.created).toBe("number");
        expect(typeof model.owned_by).toBe("string");
      }
    });
  });

  describe("POST /chat", () => {
    it("should return a chat response with correct format", async () => {
      const response = await fetch(`${apiEndpoint}chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ message: "Hello, how are you?" }),
      });
      const data = (await response.json()) as ChatResponse;

      // Validate response structure
      expect(response.status).toBe(200);
      expect(data).toHaveProperty("success", true);
      expect(data).toHaveProperty("data");

      // Validate data fields
      expect(data.data).toHaveProperty("message");
      expect(data.data).toHaveProperty("model");
      expect(data.data).toHaveProperty("usage");

      // Validate field types
      expect(typeof data.data.message).toBe("string");
      expect(typeof data.data.model).toBe("string");

      // Validate usage structure
      expect(data.data.usage).toHaveProperty("completion_tokens");
      expect(data.data.usage).toHaveProperty("prompt_tokens");
      expect(data.data.usage).toHaveProperty("total_tokens");
      expect(typeof data.data.usage.completion_tokens).toBe("number");
      expect(typeof data.data.usage.prompt_tokens).toBe("number");
      expect(typeof data.data.usage.total_tokens).toBe("number");
    });

    it("should return error when message is missing", async () => {
      const response = await fetch(`${apiEndpoint}chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({}),
      });
      const data = (await response.json()) as ErrorResponse;

      // Validate error response structure
      expect(response.status).toBe(400);
      expect(data).toHaveProperty("success", false);
      expect(data).toHaveProperty("error");
      expect(typeof data.error).toBe("string");
    });
  });
});
