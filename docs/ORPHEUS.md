# Orpheus TTS

Mina now expects an Orpheus-compatible TTS server by default.

## Why a separate server

The `legraphista/Orpheus:3b-ft-q4_k_m` Ollama model is a text completion model. It generates audio tokens, not WAV audio directly. Those tokens must be decoded with SNAC before the browser can play them.

The clean integration path is:

```text
Mina UI
  -> Mina backend /api/tts
  -> Orpheus-FastAPI /v1/audio/speech
  -> WAV bytes
  -> Mina stores /audio/*.wav
```

## Expected endpoint

Mina calls:

```text
POST http://127.0.0.1:5005/v1/audio/speech
```

with:

```json
{
  "model": "orpheus",
  "input": "Hello world.",
  "voice": "tara",
  "response_format": "wav",
  "speed": 1.0
}
```

## Environment

```powershell
MINA_TTS_PROVIDER=orpheus
MINA_TTS_VOICE=tara
MINA_ORPHEUS_BASE_URL=http://127.0.0.1:5005
MINA_ORPHEUS_MODEL=orpheus
MINA_ORPHEUS_RESPONSE_FORMAT=wav
```

## Orpheus-FastAPI

Recommended upstream:

```text
https://github.com/Lex-au/Orpheus-FastAPI
```

It exposes an OpenAI-compatible `/v1/audio/speech` endpoint and supports voices such as `tara`, `leah`, `jess`, `leo`, `dan`, `mia`, `zac`, and `zoe`.

## Local Docker startup

On this machine the repository already exists at:

```powershell
C:\Users\rferm\ProyectosF\Orpheus-FastAPI
```

Start Orpheus with GPU support:

```powershell
cd C:\Users\rferm\ProyectosF\Orpheus-FastAPI
docker compose -f docker-compose-gpu.yml up -d
```

Check status:

```powershell
docker compose -f docker-compose-gpu.yml ps
Invoke-RestMethod http://127.0.0.1:5005/v1/audio/voices
```

Stop Orpheus:

```powershell
cd C:\Users\rferm\ProyectosF\Orpheus-FastAPI
docker compose -f docker-compose-gpu.yml down
```

The first generation after startup can fail or return an empty WAV while llama.cpp is still loading the model. Wait until `/v1/audio/voices` responds and retry.

Notes:

- Native install currently targets Python 3.8-3.11.
- Your local Python is 3.13, so use a separate Python 3.10/3.11 env or Docker/WSL for Orpheus-FastAPI.
- The Orpheus service may use your existing local inference server, but it still needs SNAC decoding.

## Fallback

Windows SAPI is still available if needed:

```powershell
MINA_TTS_PROVIDER=windows_sapi
```

but it is no longer the default.
