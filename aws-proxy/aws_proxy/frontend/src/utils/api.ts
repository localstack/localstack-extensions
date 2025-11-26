import axios, { Axios } from "axios";

const API_PATH_PROXIES = "/proxies"
const API_PATH_PROXIES_STATUS = `${API_PATH_PROXIES}/status`

type AWSCredentials = {
  AWS_ACCESS_KEY_ID: string,
  AWS_SECRET_ACCESS_KEY: string,
  AWS_SESSION_TOKEN: string,
}
type SetConfigRequest = {
  env_vars: AWSCredentials,
  config: string
}

type GetStatusResponse = {
  status: string | null,
  config: string,
}

export class AwsProxyApiClient {
  private client: Axios;

  constructor(endpoint: string) {
    this.client = axios.create({ baseURL: endpoint });

    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        const status = error.response?.status;
        const data = error.response?.data;
        throw new Error(
          `Invalid API response (${status}): ${JSON.stringify(data)}`
        );
      }
    );
  }

  public async disableProxy(): Promise<void> {
    const response = await this.client.post(API_PATH_PROXIES_STATUS, { status: "disabled" });
    return response.data;
  }

  public async getStatus(): Promise<GetStatusResponse> {
    const response =  await this.client.get<GetStatusResponse>(API_PATH_PROXIES_STATUS)
    return response.data;
  }

  public async setConfig(params: SetConfigRequest): Promise<void> {
    const response = await this.client.post(API_PATH_PROXIES, params);
    return response.data;
  }
}