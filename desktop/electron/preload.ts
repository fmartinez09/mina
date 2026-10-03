import { contextBridge } from "electron";

contextBridge.exposeInMainWorld("minaDesktop", {
  backendUrl: process.env.MINA_BACKEND_URL || "http://127.0.0.1:8000",
  platform: process.platform,
});
