import { app, BrowserWindow, ipcMain, dialog } from "electron";
import { fileURLToPath } from "url";
import path from "path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Is exposed through the preload files,
// It is used for opening file dialog with specific file extensions
ipcMain.handle("dialog:selectFiles", async () => {
  const result = await dialog.showOpenDialog({
    properties: ["openFile", "multiSelections"],
    filters: [
      {
        name: "Spreadsheets",
        extensions: ["xlsx", "xls", "csv"], // TODO: Importing from interfaces doesnt work for some reason, make this not suck
      },
    ],
  });

  return result.filePaths;
});

// Is exposed through the preload files,
// It is used to select a directory for output
ipcMain.handle("dialog:selectDirectory", async () => {
  const result = await dialog.showOpenDialog({
    properties: ["openDirectory"],
  });
  return result.canceled ? null : result.filePaths[0];
});

// Is exposed through the preload files,
// It is used to get the operating systems default documents path
ipcMain.handle("app:getDocumentsPath", () => {
  const path = app.getPath("documents");
  console.log("Documents path:", path);
  return path;
});

// Creates the main window
// This will load the preload file into the browser window
// And also renders the app from local host
function createWindow() {
  const preloadPath = path.join(__dirname, "preload.js");
  const win = new BrowserWindow({
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: preloadPath,
    },
  });

  win.setMenuBarVisibility(false);
  win.loadURL("http://localhost:3480");
}

// Creates the main window when the app is ready
app.on("ready", createWindow);

// Creates the main window when the app is clicked and there are no other windows open
app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

// Quit the application when all windows are closed
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
