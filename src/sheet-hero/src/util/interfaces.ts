export const ACCEPTED_FILE_EXTENSIONS = ["xlsx", "xls", "csv"] as const;

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
}
