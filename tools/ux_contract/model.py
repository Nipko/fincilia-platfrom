from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path


REQUIRED_PAGES = {"portfolio", "import", "reconcile", "close", "signals", "reports", "mobile"}
REQUIRED_STATES = {"empty", "error", "degraded", "partial", "ambiguous"}
STATE_LABELS = {"empty": "Vacío", "error": "Error", "degraded": "Degradado", "partial": "Parcial", "ambiguous": "Ambiguo"}


@dataclass(frozen=True, order=True)
class Finding:
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


class PrototypeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.pages: set[str] = set()
        self.ids: set[str] = set()
        self.labels_for: set[str] = set()
        self.inputs: set[str] = set()
        self.heading_levels: list[int] = []
        self.tables = 0
        self.captions = 0
        self.images_without_alt = 0
        self.positive_tabindex = 0
        self.div_click_handlers = 0
        self.lang = ""
        self.has_main = False
        self.has_nav = False
        self.has_skip_link = False
        self.has_live_region = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "html": self.lang = values.get("lang") or ""
        if values.get("data-page"): self.pages.add(values["data-page"] or "")
        if values.get("id"): self.ids.add(values["id"] or "")
        if tag == "label" and values.get("for"): self.labels_for.add(values["for"] or "")
        if tag in {"input", "select", "textarea"} and values.get("id"): self.inputs.add(values["id"] or "")
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}: self.heading_levels.append(int(tag[1]))
        if tag == "table": self.tables += 1
        if tag == "caption": self.captions += 1
        if tag == "img" and "alt" not in values: self.images_without_alt += 1
        if values.get("tabindex", "").isdigit() and int(values["tabindex"] or "0") > 0: self.positive_tabindex += 1
        if tag == "div" and any(name.startswith("on") for name in values): self.div_click_handlers += 1
        if tag == "main": self.has_main = True
        if tag == "nav": self.has_nav = True
        if tag == "a" and values.get("href") == "#main-content": self.has_skip_link = True
        if values.get("aria-live"): self.has_live_region = True


def validate(html: str, css: str, js: str, architecture: str) -> list[Finding]:
    findings: list[Finding] = []
    parser = PrototypeParser(); parser.feed(html)
    if parser.lang != "es": findings.append(Finding("UX-LANGUAGE", "prototype language must be Spanish"))
    if parser.pages != REQUIRED_PAGES: findings.append(Finding("UX-PAGES", f"pages differ: {sorted(parser.pages)}"))
    if not (parser.has_main and parser.has_nav and parser.has_skip_link): findings.append(Finding("UX-LANDMARKS", "main, nav and skip link are required"))
    if not parser.has_live_region: findings.append(Finding("UX-LIVE-REGION", "dynamic state requires aria-live"))
    if parser.inputs - parser.labels_for: findings.append(Finding("UX-LABEL", "every form control needs an explicit label"))
    if parser.tables != parser.captions: findings.append(Finding("UX-TABLE-CAPTION", "every table needs a caption"))
    if parser.images_without_alt or parser.positive_tabindex or parser.div_click_handlers: findings.append(Finding("UX-KEYBOARD", "unsafe interaction or image alternative detected"))
    if not re.search(r":focus-visible|\.skip-link:focus", css): findings.append(Finding("UX-FOCUS", "visible focus styling is required"))
    if "prefers-reduced-motion" not in css: findings.append(Finding("UX-MOTION", "reduced-motion policy is required"))
    if "fetch(" in js or "XMLHttpRequest" in js or "eval(" in js: findings.append(Finding("UX-NETWORK", "prototype must be offline and code-safe"))
    for state in REQUIRED_STATES:
        if state not in js or STATE_LABELS[state].lower() not in architecture.lower():
            findings.append(Finding("UX-STATE-COVERAGE", f"missing {state}"))
    for phrase in ["Original", "Extracción fiel", "Dataset limpio", "Esquema canónico", "hoja, fila, columna", "cierre final", "Datos sintéticos"]:
        if phrase.lower() not in (html + architecture).lower(): findings.append(Finding("UX-BOUNDARY", f"missing {phrase}"))
    if re.search(r"fraude (confirmado|detectado)", (html + architecture).lower()): findings.append(Finding("UX-FRAUD-CLAIM", "prototype cannot assert fraud"))
    return sorted(set(findings))


def validate_repository(root: Path) -> list[Finding]:
    base = root / "docs/ux/prototypes"
    return validate(
        (base / "index.html").read_text(encoding="utf-8"),
        (base / "styles.css").read_text(encoding="utf-8"),
        (base / "app.js").read_text(encoding="utf-8"),
        (root / "docs/ux/INFORMATION_ARCHITECTURE.md").read_text(encoding="utf-8"),
    )
