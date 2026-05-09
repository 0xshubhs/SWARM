export interface LLMCompleteParams {
  system: string;
  user: string;
  maxTokens?: number;
  responseFormat?: "text" | "json";
}

export interface LLMClient {
  complete(params: LLMCompleteParams): Promise<string>;
}
