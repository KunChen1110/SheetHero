// This declares that the preload.js api exists to the typescript type system
export interface IElectronAPI {
  selectFiles: () => Promise<string[]>;
  selectDirectory: () => Promise<string | null>;
  getDocumentsPath: () => Promise<string>;
  openPath: (filePath: string) => Promise<void>;
}

declare global {
  interface Window {
    electronAPI: IElectronAPI;
  }
}
