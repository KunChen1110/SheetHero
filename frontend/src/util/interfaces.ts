export const FILE_EXTENSIONS = ["xlsx", "xlsm", "xltx", "xltm", "csv"] as const;

export enum Role {
  USER,
  ASSISTANT,
}

export interface Chat {
  id: string;
  title: string;
  messages: Message[];
}

export interface UiThought {
  stage: string;
  status: string;
  content: unknown;
}

export interface ClarificationControlInput {
  name: string;
  type: "number" | "text";
  placeholder?: string;
  min?: number;
  max?: number;
  validation_message?: string;
}

export interface ClarificationControl {
  decision_kind: string;
  label: string;
  input?: ClarificationControlInput;
}

export interface ClarificationResponseSchema {
  kind: string;
  metadata?: Record<string, unknown>;
  controls: ClarificationControl[];
}

export interface Message {
  id: string;
  role: Role;
  content: string;
  hasOutputFile?: boolean;
  outputPath?: string | null;
  detailsMarkdown?: string;
  uiThoughts?: UiThought[];
  responseSchema?: ClarificationResponseSchema;
}

export interface ExcelFile {
  id: string;
  name: string;
  index: number;
  path: string;
}

export interface AppSettings {
  apiKey: string;
  maxTurns: number;
  model: string;
  outputDir: string;
  baseURL: string;
}
