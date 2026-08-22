"""Validador sintetico de laboratorio para el arnes de mutaciones (FNC-QA-005).

Existe para ejercitar el clasificador del runner sin depender de ningun contrato
real: cada modo reproduce una forma concreta de comportarse mal. Probar el runner
solo contra validadores que funcionan no demostraria que sabe distinguir un
control que muerde de un proceso que se cayo.

Modos:

- `strict`    valida de verdad y emite codigos `SYN-*`.
- `blind`     siempre acepta: sirve para producir un superviviente.
- `wrongcode` falla cuando el documento esta mal, pero siempre por `SYN-OTHER`.
- `dirty`     falla incluso sobre la copia sin mutar.

Ademas, tres marcadores dentro de `controls` alteran la *forma* de la salida sin
tocar el modo. Asi la linea base sigue limpia y solo la copia mutada se porta mal:

- `marker_garbage` imprime algo que no es JSON.
- `marker_noise`   imprime mas bytes de los permitidos.
- `marker_sleep`   se pasa del timeout.

Solo biblioteca estandar. Sin red, sin reloj de pared, sin locale del host.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

CONTRACT = Path("tests/golden/mutations/synthetic_contract.json")
FLOATING = ("latest", "main", "head", "stable", "current")
NOISE_BYTES = 8192
SLEEP_SECONDS = 5


def check(document: dict) -> list[dict]:
    errors: list[dict] = []

    def fail(code: str, location: str, message: str) -> None:
        errors.append({"code": code, "location": location, "message": message})

    if document.get("authority_flag") is not True:
        fail("SYN-FLAG", "authority_flag", "la bandera de autoridad no puede apagarse")
    if document.get("data_ceiling") != "synthetic_only":
        fail("SYN-CEILING", "data_ceiling", "el techo de datos debe seguir siendo sintetico")
    if document.get("human_acceptance") != "pending":
        fail("SYN-ACCEPTANCE", "human_acceptance", "un agente no registra aceptacion humana")

    raw_path = document.get("evidence_path", "")
    if not isinstance(raw_path, str) or not raw_path:
        fail("SYN-PATH", "evidence_path", "la evidencia necesita una ruta")
    elif ".." in Path(raw_path).parts or raw_path.startswith(("/", "\\")) or \
            (len(raw_path) > 1 and raw_path[1] == ":"):
        fail("SYN-PATH", "evidence_path", "ruta no canonica, absoluta o con traversal")
    elif not Path(raw_path).is_file():
        fail("SYN-PATH", "evidence_path", "la evidencia declarada no existe")

    version = document.get("engine_version", "")
    if str(version).strip().lower() in FLOATING:
        fail("SYN-VERSION", "engine_version", "la version es un token flotante")

    controls = [c for c in document.get("controls", []) or []
                if not str(c).startswith("marker_")]
    if not isinstance(document.get("controls"), list) or len(controls) < 3:
        fail("SYN-CONTROLS", "controls", "se esperan al menos tres controles declarados")
    elif len(set(controls)) != len(controls):
        fail("SYN-CONTROLS", "controls", "hay controles duplicados")

    return errors


def markers(document: dict) -> set[str]:
    return {str(c) for c in document.get("controls", []) or [] if str(c).startswith("marker_")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="synthetic fixture validator")
    parser.add_argument("--mode", default="strict")
    args = parser.parse_args(argv)

    if args.mode == "dirty":
        print(json.dumps({"errors": [{"code": "SYN-DIRTY", "location": "-",
                                      "message": "la linea base ya venia sucia"}],
                          "ok": False}, ensure_ascii=False))
        return 1

    document = json.loads(CONTRACT.read_text(encoding="utf-8"))
    present = markers(document)

    if "marker_garbage" in present:
        print("esto no es JSON <<<")
        return 1
    if "marker_sleep" in present:
        time.sleep(SLEEP_SECONDS)
        print(json.dumps({"errors": [], "ok": True}))
        return 0
    if "marker_noise" in present:
        sys.stdout.write("x" * NOISE_BYTES)
        sys.stdout.write("\n")

    if args.mode == "blind":
        print(json.dumps({"errors": [], "ok": True}))
        return 0

    errors = check(document)
    if args.mode == "wrongcode" and errors:
        errors = [{"code": "SYN-OTHER", "location": "-",
                   "message": "falla, pero no por lo que se esperaba"}]

    print(json.dumps({"errors": errors, "ok": not errors}, ensure_ascii=False,
                     indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
