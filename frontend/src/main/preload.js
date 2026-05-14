/* eslint-disable */
const { contextBridge, ipcRenderer } = require("electron");

// This exposes an api used for communication between the renderer and the main process
contextBridge.exposeInMainWorld("electronAPI", {
  selectFiles: () => ipcRenderer.invoke("dialog:selectFiles"),
  selectDirectory: () => ipcRenderer.invoke("dialog:selectDirectory"),
  getDocumentsPath: () => ipcRenderer.invoke("app:getDocumentsPath"),
  openPath: (filePath) => ipcRenderer.invoke("app:openPath", filePath),
});
