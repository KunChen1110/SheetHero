import { app, BrowserWindow } from "electron";

// Creates a window
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

// Creates a window when the app is ready
app.on("ready", createWindow);

// Creates a window when the app is clicked and there are no other windows open
app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
})

// Quit the application when all windows are closed
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});