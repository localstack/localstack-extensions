import { APIGatewayProxyEvent, APIGatewayProxyResult } from "aws-lambda";

const WIREMOCK_BASE_URL =
  process.env.WIREMOCK_BASE_URL ||
  "http://wiremock.localhost.localstack.cloud:4566";

interface ChatMessage {
  role: string;
  content: string;
}

interface ChatChoice {
  index: number;
  message: ChatMessage;
  finish_reason: string;
}

interface ChatCompletionResponse {
  id: string;
  model: string;
  created: number;
  choices: ChatChoice[];
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

interface Model {
  id: string;
  object: string;
  created: number;
  owned_by: string;
}

interface ModelsResponse {
  object: string;
  data: Model[];
}

/**
 * Fetches available models from the WireMock OpenAI API
 */
async function getModels(): Promise<ModelsResponse> {
  const response = await fetch(`${WIREMOCK_BASE_URL}/models`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch models: ${response.statusText}`);
  }

  return response.json() as Promise<ModelsResponse>;
}

/**
 * Sends a chat completion request to the WireMock OpenAI API
 */
async function getChatCompletion(
  message: string
): Promise<ChatCompletionResponse> {
  const response = await fetch(`${WIREMOCK_BASE_URL}/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "gpt-3.5-turbo",
      messages: [
        {
          role: "user",
          content: message,
        },
      ],
    }),
  });

  if (!response.ok) {
    throw new Error(`Chat completion request failed: ${response.statusText}`);
  }

  return response.json() as Promise<ChatCompletionResponse>;
}

/**
 * Handles GET /models requests
 */
async function handleGetModels(): Promise<APIGatewayProxyResult> {
  try {
    const models = await getModels();

    return {
      statusCode: 200,
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
      },
      body: JSON.stringify({
        success: true,
        data: models.data.map((model) => ({
          id: model.id,
          object: model.object,
          created: model.created,
          owned_by: model.owned_by,
        })),
      }),
    };
  } catch (error) {
    console.error("Error fetching models:", error);
    return {
      statusCode: 500,
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
      },
      body: JSON.stringify({
        success: false,
        error: "Failed to fetch models",
        message: error instanceof Error ? error.message : "Unknown error",
      }),
    };
  }
}

/**
 * Handles POST /chat requests
 */
async function handlePostChat(
  body: string | null
): Promise<APIGatewayProxyResult> {
  try {
    if (!body) {
      return {
        statusCode: 400,
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*",
        },
        body: JSON.stringify({
          success: false,
          error: "Request body is required",
        }),
      };
    }

    const { message } = JSON.parse(body);

    if (!message || typeof message !== "string") {
      return {
        statusCode: 400,
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*",
        },
        body: JSON.stringify({
          success: false,
          error: "Message field is required and must be a string",
        }),
      };
    }

    // Get chat completion
    console.log("Getting chat completion for message:", message);
    const chatResponse = await getChatCompletion(message);

    const assistantMessage =
      chatResponse.choices[0]?.message?.content || "No response generated";

    return {
      statusCode: 200,
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
      },
      body: JSON.stringify({
        success: true,
        data: {
          message: assistantMessage,
          model: chatResponse.model,
          usage: chatResponse.usage,
        },
      }),
    };
  } catch (error) {
    console.error("Error processing chat request:", error);
    return {
      statusCode: 500,
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
      },
      body: JSON.stringify({
        success: false,
        error: "Failed to process chat request",
        message: error instanceof Error ? error.message : "Unknown error",
      }),
    };
  }
}

/**
 * Main Lambda handler
 */
export async function handler(
  event: APIGatewayProxyEvent
): Promise<APIGatewayProxyResult> {
  console.log("Received event:", JSON.stringify(event, null, 2));

  const { httpMethod, path, resource } = event;

  // Route requests based on method and path
  if (httpMethod === "GET" && (path === "/models" || resource === "/models")) {
    return handleGetModels();
  }

  if (httpMethod === "POST" && (path === "/chat" || resource === "/chat")) {
    return handlePostChat(event.body);
  }

  // Handle unknown routes
  return {
    statusCode: 404,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
    },
    body: JSON.stringify({
      success: false,
      error: "Not Found",
      message: `Unknown route: ${httpMethod} ${path}`,
    }),
  };
}
