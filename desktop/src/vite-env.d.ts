/// <reference types="vite/client" />

interface MinaDesktopBridge {
  backendUrl: string;
  platform: string;
}

interface Window {
  minaDesktop?: MinaDesktopBridge;
}
