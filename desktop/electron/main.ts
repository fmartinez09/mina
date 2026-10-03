import { app, BrowserWindow, Menu, shell } from "electron";
import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { appendFileSync, existsSync, mkdirSync } from "node:fs";
import http from "node:http";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const isDev = !app.isPackaged;
const backendHost = "127.0.0.1";
const backendPort = Number(process.env.MINA_BACKEND_PORT || "8000");
const backendUrl = `http://${backendHost}:${backendPort}`;
const rendererUrl = process.env.VITE_DEV_SERVER_URL || "http://127.0.0.1:5174";
const projectRoot = isDev ? path.resolve(__dirname, "../..") : path.dirname(process.resourcesPath);
const dataDir = process.env.MINA_DATA_DIR
  ? path.resolve(process.env.MINA_DATA_DIR)
  : isDev
    ? path.join(projectRoot, "data")
    : path.join(app.getPath("userData"), "data");
const logsDir = path.join(dataDir, "logs");
const backendStdoutLog = path.join(logsDir, "mina-backend.log");
const backendStderrLog = path.join(logsDir, "mina-backend.err");

let mainWindow: BrowserWindow | null = null;
let backendProcess: ChildProcessWithoutNullStreams | null = null;
let ownsBackendProcess = false;

async function createWindow(): Promise<void> {
  await ensureBackend();

  mainWindow = new BrowserWindow({
    width: 1240,
    height: 820,
    minWidth: 960,
    minHeight: 640,
    title: "Mina",
    backgroundColor: "#0d0f12",
    autoHideMenuBar: true,
    titleBarStyle: "hidden",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });
  Menu.setApplicationMenu(null);

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url);
    return { action: "deny" };
  });

  if (isDev) {
    await mainWindow.loadURL(rendererUrl);
  } else {
    await mainWindow.loadFile(path.join(__dirname, "../dist/index.html"));
  }
}

async function ensureBackend(): Promise<void> {
  if (await isBackendHealthy()) {
    return;
  }

  startBackend();
  await waitForBackend();
}

async function isBackendHealthy(): Promise<boolean> {
  return new Promise((resolve) => {
    const request = http.get(`${backendUrl}/`, (response) => {
      response.resume();
      resolve(Boolean(response.statusCode && response.statusCode < 400));
    });
    request.setTimeout(1500, () => {
      request.destroy();
      resolve(false);
    });
    request.on("error", () => resolve(false));
  });
}

async function waitForBackend(): Promise<void> {
  const startedAt = Date.now();
  while (Date.now() - startedAt < 30_000) {
    if (await isBackendHealthy()) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }

  throw new Error(`Mina backend did not start at ${backendUrl}`);
}

function startBackend(): void {
  const command = backendCommand();
  mkdirSync(logsDir, { recursive: true });
  backendProcess = spawn(command.executable, command.args, command.options);
  ownsBackendProcess = true;

  backendProcess.stdout.on("data", (data) => {
    const text = data.toString();
    console.log(`[mina-backend] ${text.trim()}`);
    appendBackendLog(backendStdoutLog, text);
  });
  backendProcess.stderr.on("data", (data) => {
    const text = data.toString();
    console.error(`[mina-backend] ${text.trim()}`);
    appendBackendLog(backendStderrLog, text);
  });
  backendProcess.on("exit", (code) => {
    const text = `exited with code ${code ?? "unknown"}\n`;
    console.log(`[mina-backend] ${text.trim()}`);
    appendBackendLog(backendStdoutLog, text);
    backendProcess = null;
  });
}

function backendCommand() {
  if (isDev) {
    const pythonExecutable = process.platform === "win32"
      ? path.join(projectRoot, ".venv", "Scripts", "python.exe")
      : path.join(projectRoot, ".venv", "bin", "python");

    return {
      executable: pythonExecutable,
      args: [
        "-m",
        "uvicorn",
        "mina_assistant.app.main:app",
        "--host",
        backendHost,
        "--port",
        String(backendPort),
      ],
      options: {
        cwd: projectRoot,
        env: {
          ...process.env,
          MINA_DATA_DIR: dataDir,
          MINA_DATABASE_PATH: process.env.MINA_DATABASE_PATH || path.join(dataDir, "assistant.sqlite"),
          MINA_AUDIO_DIR: process.env.MINA_AUDIO_DIR || path.join(dataDir, "audio"),
          PYTHONUNBUFFERED: "1",
        },
      },
    };
  }

  const executableName = process.platform === "win32" ? "mina-backend.exe" : "mina-backend";
  const executable = path.join(process.resourcesPath, "backend", executableName);
  if (!existsSync(executable)) {
    throw new Error(`Packaged backend was not found at ${executable}`);
  }

  return {
    executable,
    args: ["--host", backendHost, "--port", String(backendPort)],
    options: {
      cwd: path.dirname(executable),
      env: {
        ...process.env,
        MINA_DATA_DIR: dataDir,
        MINA_DATABASE_PATH: process.env.MINA_DATABASE_PATH || path.join(dataDir, "assistant.sqlite"),
        MINA_AUDIO_DIR: process.env.MINA_AUDIO_DIR || path.join(dataDir, "audio"),
        PYTHONUNBUFFERED: "1",
      },
    },
  };
}

function appendBackendLog(filePath: string, text: string): void {
  const stamp = new Date().toISOString();
  appendFileSync(filePath, `[${stamp}] ${text}`, { encoding: "utf8" });
}

function stopBackend(): void {
  if (ownsBackendProcess && backendProcess && !backendProcess.killed) {
    backendProcess.kill();
  }
}

app.whenReady().then(() => {
  process.env.MINA_BACKEND_URL = backendUrl;
  void createWindow();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    void createWindow();
  }
});

app.on("before-quit", stopBackend);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
