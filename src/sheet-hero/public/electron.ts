import { app, BrowserWindow } from "electron";

function createWindow() {
  const win = new BrowserWindow({
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });
  
  win.setMenuBarVisibility(false);
  win.loadURL("http://localhost:3480");

}

app.whenReady().then(() => {
    createWindow();

    app.on("activate", () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    })
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});