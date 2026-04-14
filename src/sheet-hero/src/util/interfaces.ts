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

export interface Message {
  id: string;
  role: Role;
  content: string;
  hasOutputFile?: boolean;
  outputPath?: string | null;
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
