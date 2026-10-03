# Mina Desktop

Electron + React shell for Mina Assistant. The desktop app reuses the existing Python/FastAPI backend instead of duplicating provider logic in the renderer.

## Development

Install dependencies:

```powershell
cd C:\Users\rferm\ProyectosF\mina\desktop
npm install
```

Run the desktop app:

```powershell
npm run dev
```

This starts:

- Vite renderer at `http://127.0.0.1:5174`.
- Electron desktop window.
- Mina backend at `http://127.0.0.1:8000` if it is not already running.

The renderer receives the backend URL from Electron preload. API keys stay in the root `.env`; they are read by the Python backend, not by React.

## Build

Compile TypeScript and production renderer assets:

```powershell
npm run build
```

## Packaging Path

Electron Builder is wired with `npm run pack` and `npm run dist`, but a packaged app also needs a backend binary at:

```text
C:\Users\rferm\ProyectosF\mina\backend-dist\mina-backend.exe
```

Create that binary first:

```powershell
cd C:\Users\rferm\ProyectosF\mina
.venv\Scripts\python -m pip install pyinstaller
.\desktop\scripts\build-backend.ps1
```

Then package Electron:

```powershell
cd C:\Users\rferm\ProyectosF\mina\desktop
npm run pack
```

Current Windows target is `dir`, which creates an unpacked desktop app under `desktop\release`. We can switch to an installer target later once the backend binary flow is stable.
