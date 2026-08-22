"""Caso de auto-verificación del harness (FNC-QA-003).

Lee un fixture sintético declarado, comprueba que queda dentro del repositorio y
emite un documento JSON determinista. Existe para que el harness ejercite de
extremo a extremo la adjudicación de inputs, el oráculo y la allowlist de
módulos sin depender de ningún validador ajeno.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.golden_harness.registry import resolve_inside, sha256_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Golden harness self check")
    parser.add_argument("--input", type=str, required=True)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args(argv)

    resolved = resolve_inside(args.root.resolve(), args.input)
    if resolved is None or not resolved.is_file():
        print(json.dumps({"ok": False, "reason": "input outside repository or missing"},
                         ensure_ascii=False, indent=2, sort_keys=True))
        return 1

    document = json.loads(resolved.read_text(encoding="utf-8"))
    print(json.dumps(
        {
            "ok": True,
            "fixture_sha256": sha256_file(resolved),
            "record_count": len(document.get("records", [])),
            "data_classification": document.get("data_classification"),
        },
        ensure_ascii=False, indent=2, sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
