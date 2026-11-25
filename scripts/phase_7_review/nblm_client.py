#!/usr/bin/env python3
"""Fachada sobre `notebooklm-py` para consultar notebooks de NotebookLM.

POR QUÉ ESTE ARCHIVO EXISTE
===========================
A septiembre de 2026 NotebookLM **no tiene API pública**. Lo que hay es:

  - la API oficial de Gemini Notebook Enterprise, que sólo hace CRUD de
    notebooks (crear, listar, borrar, compartir): no tiene endpoint de consulta,
    y además exige Google Cloud con licencia;
  - `notebooklm-py`, una librería NO oficial que habla las APIs internas de
    Google con las cookies de tu sesión. Es la única vía que permite preguntarle
    a *tus* notebooks desde una cuenta personal, y puede romperse sin aviso.

Toda esa fragilidad vive aquí y sólo aquí. El resto del canal (`nblm_extract.py`)
depende de esta fachada, no de la librería. Si mañana Google cambia sus
endpoints internos, se arregla un archivo — y el JSONL crudo que ya se extrajo
sigue siendo evidencia auditable, porque no depende de volver a conectarse.

DEUDA CONOCIDA
==============
Una respuesta de NotebookLM **no es reproducible**: el corpus del notebook no
vive en este repo y no está versionado. Por eso `ask()` devuelve siempre la
respuesta íntegra y sus citas resueltas a título de fuente, y el tablero las
muestra: lo que el revisor comprueba es la cita, no el número suelto.

Credenciales
------------
    pip install "notebooklm-py[browser]"
    notebooklm login

Guarda el `storage_state.json` en `secrets/notebooklm/` (ya está en .gitignore)
y apunta ahí la variable NOTEBOOKLM_STORAGE, o deja que la librería use su
ubicación por defecto.

Uso directo (para conseguir los ids de los notebooks):
    python3 scripts/phase_7_review/nblm_client.py --listar
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent.parent
CFG = ROOT / "config" / "notebooklm.json"
CFG_EXAMPLE = ROOT / "config" / "notebooklm.example.json"

logger = logging.getLogger("nblm")

FALTA_LIBRERIA = (
    "Falta `notebooklm-py`. Es una dependencia OPCIONAL: sólo la usa el canal de\n"
    "NotebookLM, el resto del pipeline funciona sin ella.\n\n"
    "    pip install \"notebooklm-py[browser]\"\n"
    "    notebooklm login\n\n"
    "Advertencia: la librería NO es oficial de Google. Habla APIs internas con\n"
    "las cookies de tu sesión y puede dejar de funcionar sin aviso."
)


# ── configuración ───────────────────────────────────────────────────────

@dataclass
class NotebookCfg:
    """Un notebook y el territorio que declara cubrir."""
    id: str
    alias: str
    prioridad: int = 1
    params_covered: list[str] = field(default_factory=list)


def load_config(path: Path = CFG) -> list[NotebookCfg]:
    if not path.exists():
        raise SystemExit(
            f"No existe {path.relative_to(ROOT)}.\n"
            f"Cópialo de {CFG_EXAMPLE.relative_to(ROOT)} y pon los ids reales:\n"
            f"    cp {CFG_EXAMPLE.relative_to(ROOT)} {path.relative_to(ROOT)}\n"
            f"    python3 scripts/phase_7_review/nblm_client.py --listar"
        )
    doc = json.loads(path.read_text(encoding="utf-8"))
    cfgs = [NotebookCfg(**{k: v for k, v in nb.items() if not k.startswith("_")})
            for nb in doc.get("notebooks", [])]
    if not cfgs:
        raise SystemExit(f"{path.relative_to(ROOT)} no declara ningún notebook.")
    sin_id = [c.alias for c in cfgs if not c.id or c.id.startswith("PON-AQUI")]
    if sin_id:
        raise SystemExit(
            f"Notebooks sin id real en {path.relative_to(ROOT)}: {', '.join(sin_id)}.\n"
            f"Consíguelos con: python3 scripts/phase_7_review/nblm_client.py --listar"
        )
    return sorted(cfgs, key=lambda c: c.prioridad)


def params_de_interes(cfgs: list[NotebookCfg]) -> list[str]:
    """Unión de lo que los notebooks dicen cubrir, sin repetir y en orden estable."""
    vistos: list[str] = []
    for cfg in cfgs:
        for param in cfg.params_covered:
            if param not in vistos:
                vistos.append(param)
    return vistos


# ── sesión ──────────────────────────────────────────────────────────────

def _import_client():
    try:
        from notebooklm import NotebookLMClient          # type: ignore
    except ImportError as exc:                            # noqa: BLE001
        raise SystemExit(FALTA_LIBRERIA) from exc
    return NotebookLMClient


async def _abrir(NotebookLMClient):
    """`from_storage`, tolerando que la firma cambie: la librería no es estable."""
    storage = os.environ.get("NOTEBOOKLM_STORAGE")
    if not storage:
        return NotebookLMClient.from_storage()
    try:
        return NotebookLMClient.from_storage(storage)
    except TypeError:
        return NotebookLMClient.from_storage(storage_path=storage)


class NblmSession:
    """Sesión con reintentos y caché de títulos de fuente.

    Se usa como gestor de contexto asíncrono:

        async with NblmSession() as ses:
            r = await ses.ask(notebook_id, "…")
    """

    def __init__(self, intentos: int = 3, espera_base: float = 4.0):
        self.intentos = intentos
        self.espera_base = espera_base
        self._client = None
        self._cm = None
        self._titulos: dict[str, dict[str, str]] = {}

    async def __aenter__(self) -> "NblmSession":
        NotebookLMClient = _import_client()
        self._cm = await _abrir(NotebookLMClient)
        self._client = await self._cm.__aenter__()
        return self

    async def __aexit__(self, *exc) -> None:
        if self._cm is not None:
            await self._cm.__aexit__(*exc)

    # ── operaciones ─────────────────────────────────────────────────────

    async def listar(self) -> list[dict]:
        notebooks = await self._client.notebooks.list()
        return [{"id": nb.id, "title": getattr(nb, "title", "")} for nb in notebooks]

    async def _source_titles(self, notebook_id: str) -> dict[str, str]:
        """Mapa source_id → título, cacheado por notebook.

        Sin esto una cita es un id opaco, que para un revisor no es una cita:
        es un identificador que no puede comprobar contra nada.
        """
        if notebook_id in self._titulos:
            return self._titulos[notebook_id]
        mapa: dict[str, str] = {}
        try:
            meta = await self._client.notebooks.get_metadata(notebook_id)
            for src in getattr(meta, "sources", []) or []:
                mapa[str(getattr(src, "id", ""))] = str(getattr(src, "title", "") or "")
        except Exception as exc:                          # noqa: BLE001
            logger.warning("No se pudieron leer las fuentes de %s: %s", notebook_id, exc)
        self._titulos[notebook_id] = mapa
        return mapa

    async def ask(self, notebook_id: str, question: str) -> Optional[dict]:
        """Pregunta y devuelve {"answer", "citations"} o None si falló.

        Reintenta con espera creciente: es una cuenta gratuita contra una API
        interna, y machacarla es la forma segura de que la corten.
        """
        ultimo: Optional[Exception] = None
        for intento in range(1, self.intentos + 1):
            try:
                result = await self._client.chat.ask(notebook_id, question)
                break
            except Exception as exc:                      # noqa: BLE001
                ultimo = exc
                if intento == self.intentos:
                    logger.error("    fallo tras %d intentos: %s", self.intentos, exc)
                    return None
                espera = self.espera_base * (2 ** (intento - 1))
                logger.warning("    intento %d falló (%s) · reintento en %.0fs",
                               intento, exc, espera)
                await asyncio.sleep(espera)
        else:                                             # pragma: no cover
            logger.error("    sin respuesta: %s", ultimo)
            return None

        titulos = await self._source_titles(notebook_id)
        citations = []
        for ref in getattr(result, "references", []) or []:
            source_id = str(getattr(ref, "source_id", "") or "")
            citations.append({
                "n": getattr(ref, "citation_number", None),
                "source_id": source_id,
                "source_title": titulos.get(source_id) or source_id or "fuente sin título",
                "text": (getattr(ref, "text", "") or "")[:600],
            })
        return {
            "answer": getattr(result, "answer", "") or "",
            "citations": citations,
            "conversation_id": getattr(result, "conversation_id", None),
        }


# ── CLI de diagnóstico ──────────────────────────────────────────────────

async def _main_async(args) -> None:
    async with NblmSession() as ses:
        if args.listar:
            notebooks = await ses.listar()
            if not notebooks:
                print("La cuenta no tiene notebooks (o la sesión no es la correcta).")
                return
            print(f"{'id':<40} título")
            print("-" * 80)
            for nb in notebooks:
                print(f"{nb['id']:<40} {nb['title']}")
            print(f"\n{len(notebooks)} notebooks · "
                  f"copia los ids a {CFG.relative_to(ROOT)}")
            return
        if args.preguntar:
            for cfg in load_config():
                print(f"\n=== {cfg.alias} ({cfg.id}) ===")
                res = await ses.ask(cfg.id, args.preguntar)
                if not res:
                    print("  (sin respuesta)")
                    continue
                print(res["answer"])
                for c in res["citations"]:
                    print(f"  [{c['n']}] {c['source_title']}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--listar", action="store_true",
                        help="lista los notebooks de la cuenta con sus ids")
    parser.add_argument("--preguntar", metavar="TEXTO",
                        help="pregunta suelta a los notebooks configurados (prueba de humo)")
    args = parser.parse_args()
    if not (args.listar or args.preguntar):
        parser.print_help()
        return
    asyncio.run(_main_async(args))


if __name__ == "__main__":
    main()
