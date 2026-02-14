/* eslint-disable */
const { contextBridge, ipcRenderer } = require("electron");

// This exposes an api used for communication between the renderer and the main process
contextBridge.exposeInMainWorld("electronAPI", {
  openFileDialog: () => ipcRenderer.invoke("open-file-dialog"),
});
