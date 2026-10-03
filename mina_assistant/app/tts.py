from __future__ import annotations

import os
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from mina_assistant.app.config import Settings


class TTSError(RuntimeError):
    pass


@dataclass(frozen=True)
class TTSResult:
    audio_id: str
    file_path: Path
    audio_url: str
    provider: str
    voice: str | None


@dataclass(frozen=True)
class TTSVoice:
    id: str
    name: str
    culture: str | None = None


@dataclass(frozen=True)
class TTSProviderStatus:
    name: str
    label: str
    available: bool
    default_voice: str | None
    voices: list[TTSVoice]
    requires_api_key: bool = False
    detail: str | None = None


class TTSService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.audio_dir = settings.audio_dir

    def initialize(self) -> None:
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    def synthesize(
        self,
        text: str,
        *,
        provider: str | None = None,
        voice: str | None = None,
    ) -> TTSResult:
        normalized_text = " ".join(text.split()).strip()
        if not normalized_text:
            raise TTSError("No text was provided for speech synthesis.")

        self.initialize()
        active_provider = _normalize_provider(provider or self.settings.tts_provider)
        selected_voice = voice or self.default_voice(active_provider)
        audio_id = f"tts_{uuid.uuid4().hex}.{self._audio_extension(active_provider)}"
        file_path = self.audio_dir / audio_id

        if active_provider == "orpheus":
            _run_orpheus_http(
                settings=self.settings,
                text=normalized_text,
                output_path=file_path,
                voice=selected_voice or "tara",
            )
        elif active_provider == "elevenlabs":
            _run_elevenlabs_http(
                settings=self.settings,
                text=normalized_text,
                output_path=file_path,
                voice_id=selected_voice,
            )
        elif active_provider == "windows_sapi":
            _run_windows_sapi(
                text=normalized_text,
                output_path=file_path,
                voice=selected_voice,
                rate=self.settings.tts_rate,
            )
        else:
            raise TTSError(f"Unsupported TTS provider: {active_provider}")

        if not file_path.exists() or file_path.stat().st_size <= 44:
            raise TTSError("The TTS provider did not generate a valid audio file.")

        return TTSResult(
            audio_id=audio_id,
            file_path=file_path,
            audio_url=f"/audio/{audio_id}",
            provider=active_provider,
            voice=selected_voice,
        )

    def provider_statuses(self) -> list[TTSProviderStatus]:
        providers = [
            ("orpheus", "Orpheus", False),
            ("elevenlabs", "ElevenLabs", True),
            ("windows_sapi", "Windows SAPI", False),
        ]
        statuses: list[TTSProviderStatus] = []
        for name, label, requires_api_key in providers:
            detail: str | None = None
            try:
                if name == "orpheus":
                    voices, available = self._orpheus_voices_and_availability()
                    if not available:
                        detail = f"Start Orpheus-FastAPI at {self.settings.orpheus_base_url}."
                elif name == "elevenlabs":
                    voices = self.list_voices(name)
                    available = bool(self.settings.elevenlabs_api_key and (self.default_voice(name) or voices))
                else:
                    voices = self.list_voices(name)
                    available = self.is_available(name)
            except TTSError as exc:
                voices = []
                available = False
                detail = str(exc)

            if requires_api_key and not self.settings.elevenlabs_api_key:
                detail = "Set MINA_ELEVENLABS_API_KEY in .env."
            elif name == "elevenlabs" and self.settings.elevenlabs_api_key and not voices:
                detail = "Set MINA_ELEVENLABS_VOICE_ID or make sure the API key can list voices."

            statuses.append(
                TTSProviderStatus(
                    name=name,
                    label=label,
                    available=available,
                    default_voice=self.default_voice(name),
                    voices=voices,
                    requires_api_key=requires_api_key,
                    detail=detail,
                )
            )
        return statuses

    def default_voice(self, provider: str | None = None) -> str | None:
        active_provider = _normalize_provider(provider or self.settings.tts_provider)
        if active_provider == "orpheus":
            return self.settings.tts_voice or "tara"
        if active_provider == "elevenlabs":
            return self.settings.elevenlabs_voice_id
        if active_provider == "windows_sapi":
            return self.settings.tts_voice
        return None

    def list_voices(self, provider: str | None = None) -> list[TTSVoice]:
        active_provider = _normalize_provider(provider or self.settings.tts_provider)
        if active_provider == "orpheus":
            voices, _ = self._orpheus_voices_and_availability()
            return voices

        if active_provider == "elevenlabs":
            return self._list_elevenlabs_voices()

        if active_provider != "windows_sapi":
            return []

        script = """
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.GetInstalledVoices() | ForEach-Object {
  $_.VoiceInfo.Name + "|" + $_.VoiceInfo.Culture.Name
}
$synth.Dispose()
"""
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            raise TTSError(_format_powershell_error(result.stderr))

        voices: list[TTSVoice] = []
        for line in result.stdout.splitlines():
            if "|" not in line:
                continue
            name, culture = line.split("|", 1)
            voice_name = name.strip()
            voices.append(TTSVoice(id=voice_name, name=voice_name, culture=culture.strip()))
        return voices

    def is_available(self, provider: str | None = None) -> bool:
        active_provider = _normalize_provider(provider or self.settings.tts_provider)
        if active_provider == "orpheus":
            try:
                response = httpx.get(
                    f"{self.settings.orpheus_base_url}/v1/audio/voices",
                    timeout=1.5,
                )
                return response.status_code < 400
            except httpx.HTTPError:
                return False

        if active_provider == "elevenlabs":
            return bool(self.settings.elevenlabs_api_key and self.settings.elevenlabs_voice_id)

        if active_provider == "windows_sapi":
            try:
                return len(self.list_voices("windows_sapi")) > 0
            except TTSError:
                return False

        return False

    def _list_elevenlabs_voices(self) -> list[TTSVoice]:
        fallback = (
            [TTSVoice(self.settings.elevenlabs_voice_id, self.settings.elevenlabs_voice_id, "elevenlabs")]
            if self.settings.elevenlabs_voice_id
            else []
        )
        if not self.settings.elevenlabs_api_key:
            return fallback

        try:
            response = httpx.get(
                f"{self.settings.elevenlabs_base_url}/v2/voices",
                headers={"xi-api-key": self.settings.elevenlabs_api_key},
                timeout=4,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return fallback

        voices: list[TTSVoice] = []
        for voice in response.json().get("voices", []):
            voice_id = str(voice.get("voice_id") or "")
            if not voice_id:
                continue
            name = str(voice.get("name") or voice_id)
            culture = _voice_culture(voice)
            voices.append(TTSVoice(id=voice_id, name=name, culture=culture))
        return voices or fallback

    def _orpheus_voices_and_availability(self) -> tuple[list[TTSVoice], bool]:
        fallback = [
            TTSVoice("tara", "tara", "en-US"),
            TTSVoice("leah", "leah", "en-US"),
            TTSVoice("jess", "jess", "en-US"),
            TTSVoice("leo", "leo", "en-US"),
            TTSVoice("dan", "dan", "en-US"),
            TTSVoice("mia", "mia", "en-US"),
            TTSVoice("zac", "zac", "en-US"),
            TTSVoice("zoe", "zoe", "en-US"),
        ]
        try:
            response = httpx.get(
                f"{self.settings.orpheus_base_url}/v1/audio/voices",
                timeout=1.5,
            )
            if response.status_code < 400:
                voices = response.json().get("voices", [])
                return [TTSVoice(id=str(voice), name=str(voice), culture="orpheus") for voice in voices], True
        except httpx.HTTPError:
            pass

        return fallback, False

    def _audio_extension(self, provider: str) -> str:
        active_provider = _normalize_provider(provider)
        if active_provider == "elevenlabs":
            output_format = self.settings.elevenlabs_output_format.lower()
            if output_format.startswith("mp3"):
                return "mp3"
            if output_format.startswith("wav"):
                return "wav"
            if output_format.startswith("pcm"):
                return "pcm"
            return "audio"
        return "wav"


def _run_orpheus_http(*, settings: Settings, text: str, output_path: Path, voice: str) -> None:
    payload = {
        "model": settings.orpheus_model,
        "input": text,
        "voice": voice,
        "response_format": settings.orpheus_response_format,
        "speed": 1.0,
    }

    try:
        with httpx.Client(timeout=settings.request_timeout_seconds) as client:
            response = client.post(f"{settings.orpheus_base_url}/v1/audio/speech", json=payload)
    except httpx.HTTPError as exc:
        raise TTSError(
            "Orpheus server is not reachable. Start Orpheus-FastAPI at "
            f"{settings.orpheus_base_url} and try again. Details: {exc}"
        ) from exc

    if response.status_code >= 400:
        raise TTSError(
            "Orpheus server returned an error: "
            f"{response.status_code} {response.text[:500]}"
        )

    if not response.content:
        raise TTSError("Orpheus server returned an empty audio response.")

    output_path.write_bytes(response.content)


def _run_elevenlabs_http(
    *,
    settings: Settings,
    text: str,
    output_path: Path,
    voice_id: str | None,
) -> None:
    if not settings.elevenlabs_api_key:
        raise TTSError("ElevenLabs API key is not configured. Set MINA_ELEVENLABS_API_KEY in .env.")
    if not voice_id:
        raise TTSError("ElevenLabs voice is not configured. Set MINA_ELEVENLABS_VOICE_ID in .env.")

    payload: dict[str, Any] = {
        "text": text,
        "model_id": settings.elevenlabs_model,
    }
    if settings.elevenlabs_language_code:
        payload["language_code"] = settings.elevenlabs_language_code

    try:
        with httpx.Client(timeout=settings.request_timeout_seconds) as client:
            response = client.post(
                f"{settings.elevenlabs_base_url}/v1/text-to-speech/{voice_id}",
                params={"output_format": settings.elevenlabs_output_format},
                headers={
                    "xi-api-key": settings.elevenlabs_api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise TTSError(f"Could not complete the ElevenLabs TTS request: {exc}") from exc

    if response.status_code >= 400:
        raise TTSError(
            "ElevenLabs returned an error: "
            f"{response.status_code} {response.text[:500]}"
        )

    if not response.content:
        raise TTSError("ElevenLabs returned an empty audio response.")

    output_path.write_bytes(response.content)


def _run_windows_sapi(*, text: str, output_path: Path, voice: str | None, rate: int) -> None:
    script = """
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voice = $env:MINA_TTS_VOICE
if ($voice) {
  $synth.SelectVoice($voice)
} else {
  $spanish = $synth.GetInstalledVoices() |
    Where-Object { $_.VoiceInfo.Culture.Name -like "es-*" } |
    Select-Object -First 1
  if ($spanish) {
    $synth.SelectVoice($spanish.VoiceInfo.Name)
  }
}
$rateText = $env:MINA_TTS_RATE
if ($rateText) {
  $synth.Rate = [Math]::Max(-10, [Math]::Min(10, [int]$rateText))
}
$synth.SetOutputToWaveFile($env:MINA_TTS_OUTPUT)
$synth.Speak($env:MINA_TTS_TEXT)
$synth.Dispose()
"""
    env = os.environ.copy()
    env["MINA_TTS_TEXT"] = text
    env["MINA_TTS_OUTPUT"] = str(output_path)
    env["MINA_TTS_VOICE"] = voice or ""
    env["MINA_TTS_RATE"] = str(rate)

    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        raise TTSError(_format_powershell_error(result.stderr))


def _voice_culture(voice: dict[str, Any]) -> str | None:
    verified_languages = voice.get("verified_languages") or []
    if verified_languages:
        language = verified_languages[0]
        if isinstance(language, dict):
            return str(language.get("locale") or language.get("language") or "") or None

    labels = voice.get("labels") or {}
    if isinstance(labels, dict):
        parts = [str(value) for value in labels.values() if value]
        return ", ".join(parts[:2]) or None
    return None


def _normalize_provider(provider: str) -> str:
    return provider.strip().lower()


def _format_powershell_error(stderr: str) -> str:
    message = " ".join(stderr.split()).strip()
    return message or "Unknown error while running Windows SAPI."
