from __future__ import annotations
import unittest
from pathlib import Path
from .model import validate, validate_repository

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs/ux/prototypes"
HTML = (BASE / "index.html").read_text(encoding="utf-8")
CSS = (BASE / "styles.css").read_text(encoding="utf-8")
JS = (BASE / "app.js").read_text(encoding="utf-8")
IA = (ROOT / "docs/ux/INFORMATION_ARCHITECTURE.md").read_text(encoding="utf-8")

class UxContractTests(unittest.TestCase):
    def codes(self, html=HTML, css=CSS, js=JS, ia=IA) -> set[str]:
        return {item.code for item in validate(html, css, js, ia)}
    def test_repository_contract_is_valid(self): self.assertEqual([], validate_repository(ROOT))
    def test_missing_page_bites(self): self.assertIn("UX-PAGES", self.codes(html=HTML.replace('data-page="mobile"','data-page="removed"')))
    def test_missing_label_bites(self): self.assertIn("UX-LABEL", self.codes(html=HTML.replace('for="ui-state"','for="removed"')))
    def test_missing_caption_bites(self): self.assertIn("UX-TABLE-CAPTION", self.codes(html=HTML.replace("<caption>","<p>",1).replace("</caption>","</p>",1)))
    def test_positive_tabindex_bites(self): self.assertIn("UX-KEYBOARD", self.codes(html=HTML.replace('tabindex="-1"','tabindex="2"')))
    def test_network_call_bites(self): self.assertIn("UX-NETWORK", self.codes(js=JS + "\nfetch('/external');"))
    def test_missing_state_bites(self): self.assertIn("UX-STATE-COVERAGE", self.codes(js=JS.replace("ambiguous", "uncertain")))
    def test_fraud_claim_bites(self): self.assertIn("UX-FRAUD-CLAIM", self.codes(ia=IA + "\nFraude detectado"))

if __name__ == "__main__": unittest.main()
