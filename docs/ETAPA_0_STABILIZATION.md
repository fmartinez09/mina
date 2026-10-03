# Stage 0 - Operational Stabilization

Status: implemented.

## Goal

Mina needs an operational foundation that is observable and recoverable to support chat, voice, memory, and reflection without losing data.

This stage adds:

- system diagnostics;
- SQLite backups;
- log listing and reading;
- persistent backend logs when Electron starts the backend;
- a `System` view in the desktop app.

## Backend

New module:

```text
mina_assistant/app/system.py
```

Responsibilities:

- summarize paths and active configuration;
- count key SQLite records;
- create backups using SQLite's safe backup API;
- list known `.log` and `.err` files;
- return the tail of a log without loading an entire large file.

## Endpoints

```text
GET  /api/system/status
POST /api/system/backup
GET  /api/system/logs
GET  /api/system/logs/tail?name=logs/mina-backend.log
```

Quick usage:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/system/status

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/system/backup

Invoke-RestMethod http://127.0.0.1:8000/api/system/logs

Invoke-RestMethod `
  "http://127.0.0.1:8000/api/system/logs/tail?name=logs%2Fmina-backend.log"
```

## Desktop

The app now has a `System` view with:

- database status;
- SQLite file size;
- paths for `data`, `audio`, `backups`, and `logs`;
- counts for key tables;
- active configuration;
- a `Backup` button;
- a log selector;
- a log tail viewer.

## Electron Logs

When Electron starts the backend, it writes to:

```text
data/logs/mina-backend.log
data/logs/mina-backend.err
```

In development, `MINA_DATA_DIR` still points to the project's `data/` directory. In the packaged app, Electron uses a writable user directory if `MINA_DATA_DIR` is not set.

## Backups

Backups are saved in:

```text
data/backups
```

Filename format:

```text
assistant-YYYYMMDDTHHMMSSZ.sqlite
```

## Out of Scope

- automatic restoration;
- JSON export;
- log rotation;
- backup compression;
- an error panel for each subsystem;
- detailed Qdrant/Ollama health checks.

These items are deferred to a later stage if the project grows to include more demanding services.
