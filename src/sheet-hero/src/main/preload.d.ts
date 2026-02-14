// This declares that the preload.js api exists to the typescript type system
export interface IElectronAPI {
  openFileDialog: () => Promise<string[]>;
}

declare global {
  interface Window {
    electronAPI: IElectronAPI;
  }
}
