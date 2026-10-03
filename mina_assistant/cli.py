from __future__ import annotations

import argparse
import asyncio
import sys

from mina_assistant.app.config import get_settings
from mina_assistant.app.db import SQLiteStore
from mina_assistant.app.llm import LLMError, LLMService
from mina_assistant.app.orchestrator import AssistantOrchestrator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI local para Mina Assistant.")
    parser.add_argument("prompt", nargs="*", help="Mensaje a enviar al asistente.")
    parser.add_argument("--session-id", help="Sesion existente para continuar la conversacion.")
    parser.add_argument(
        "--provider",
        choices=["ollama", "openai", "anthropic"],
        help="Proveedor de texto a usar para este turno.",
    )
    parser.add_argument("--model", help="Modelo a usar para este turno.")
    parser.add_argument(
        "--output-mode",
        choices=["text", "voice", "both"],
        default="text",
        help="Modo de salida registrado para el turno.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Inicia un loop interactivo de texto.",
    )
    return parser


async def run_once(
    prompt: str,
    *,
    session_id: str | None,
    provider: str | None,
    model: str | None,
    output_mode: str,
    show_status: bool = False,
) -> str:
    settings = get_settings()
    db = SQLiteStore(settings.database_path)
    db.initialize()
    llm = LLMService(settings)
    orchestrator = AssistantOrchestrator(settings=settings, db=db, llm=llm)

    if show_status:
        active_provider = provider or llm.default_provider()
        active_model = model or llm.default_model(active_provider)
        print(
            f"Mina esta pensando con {active_provider}/{active_model}...",
            file=sys.stderr,
            flush=True,
        )

    result = await orchestrator.chat(
        prompt,
        session_id=session_id,
        input_mode="text",
        output_mode=output_mode,
        provider=provider,
        model=model,
    )
    return f"[session: {result.session_id}]\n{result.content}"


async def run_interactive(
    *,
    session_id: str | None,
    provider: str | None,
    model: str | None,
    output_mode: str,
) -> int:
    active_session_id = session_id
    print("Mina Assistant CLI. Escribe /salir para terminar.")
    while True:
        try:
            prompt = input("\nTu: ").strip()
        except EOFError:
            print()
            return 0

        if prompt in {"/salir", "/exit", "/quit"}:
            return 0
        if not prompt:
            continue

        try:
            output = await run_once(
                prompt,
                session_id=active_session_id,
                provider=provider,
                model=model,
                output_mode=output_mode,
                show_status=True,
            )
        except (LLMError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            continue

        first_line, _, body = output.partition("\n")
        active_session_id = first_line.removeprefix("[session: ").removesuffix("]")
        print(f"\nMina: {body}")

    return 0


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    prompt = " ".join(args.prompt).strip()

    try:
        if args.interactive or not prompt:
            raise SystemExit(
                asyncio.run(
                    run_interactive(
                        session_id=args.session_id,
                        provider=args.provider,
                        model=args.model,
                        output_mode=args.output_mode,
                    )
                )
            )

        output = asyncio.run(
            run_once(
                prompt,
                session_id=args.session_id,
                provider=args.provider,
                model=args.model,
                output_mode=args.output_mode,
                show_status=True,
            )
        )
        print(output)
    except KeyboardInterrupt:
        print("\nCancelado.", file=sys.stderr)
        raise SystemExit(130)
    except LLMError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
