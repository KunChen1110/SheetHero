import { app, BrowserWindow, ipcMain, dialog, shell } from "electron";
import { fileURLToPath } from "url";
import { spawn, ChildProcess } from "child_process";
import path from "path";
import http from "http";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

let backendProcess: ChildProcess | null = null;

// Is exposed through the preload files,
// It is used for opening file dialog with specific file extensions
ipcMain.handle("dialog:selectFiles", async () => {
  const result = await dialog.showOpenDialog({
    properties: ["openFile", "multiSelections"],
    filters: [
      {
        name: "Spreadsheets",
        extensions: ["xlsx", "xlsm", "xltx", "xltm", "csv"], // TODO: Importing from interfaces doesnt work for some reason, make this not suck
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
  return app.getPath("documents");
});

// Is exposed through the preload files,
// It is used to open the folder containing the file, with the file highlighted
ipcMain.handle("app:openPath", async (_, filePath: string) => {
  shell.showItemInFolder(path.normalize(filePath));
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

  if (app.isPackaged) {
    win.loadFile(path.join(__dirname, "../../dist/renderer/index.html"));
  } else {
    win.loadURL("http://localhost:3480");
  }
}

function waitForBackend(retries = 20): Promise<void> {
  return new Promise((resolve, reject) => {
    const attempt = () => {
      http
        .get("http://localhost:8000/docs", (res) => {
          if (res.statusCode === 200) resolve();
          else retry();
        })
        .on("error", retry);
    };
    const retry = () => {
      if (retries-- > 0) setTimeout(attempt, 500);
      else reject(new Error("Backend failed to start"));
    };
    attempt();
  });
}

function getBackendPath(): string {
  if (app.isPackaged) {
    const binaryName =
      process.platform === "win32"
        ? "sheet-hero-backend.exe"
        : "sheet-hero-backend";
    return path.join(process.resourcesPath, "backend", binaryName);
  }
  return "";
}

function startBackend() {
  if (app.isPackaged) {
    const backendPath = getBackendPath();
    backendProcess = spawn(backendPath, [], { stdio: "ignore" });
  }
}

// Creates the main window when the app is ready
app.on("ready", async () => {
  startBackend();
  if (app.isPackaged) await waitForBackend();
  createWindow();
});

app.on("will-quit", () => {
  if (backendProcess) backendProcess.kill();
});

// Creates the main window when the app is clicked and there are no other windows open
app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

// Quit the application when all windows are closed
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
