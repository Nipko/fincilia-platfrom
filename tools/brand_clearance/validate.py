from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[2];MODEL=Path("docs/business/brand-clearance.json")
@dataclass(frozen=True)
class Finding:
 code:str;subject:str;detail:str
 def as_dict(self):return self.__dict__
def validate_model(m:dict[str,Any])->list[Finding]:
 f=[]; keys={"schema_version","task","status","evidence_checked_at","legal_clearance","agent_may_file_or_reserve","preferred_name","preferred_state","descriptor_es","descriptor_en","tagline_es","tagline_en","candidates","search_plan","channels","brand_architecture","gates"}
 if set(m)!=keys:return [Finding("BRD-SCHEMA","model","unexpected keys")]
 if m["legal_clearance"]!="pending_counsel" or m["agent_may_file_or_reserve"] is not False:f.append(Finding("BRD-LEGAL","model","agent cannot clear/file"))
 if m["preferred_name"]!="Fincilia" or m["preferred_state"]!="provisional_pending_legal_clearance":f.append(Finding("BRD-PREFERRED","model","preference or state changed"))
 names=[x.get("name") for x in m["candidates"]]
 if names!=["Fincilia","Cotejo","Empatar"]:f.append(Finding("BRD-CANDIDATES","candidates",str(names)))
 if any(not x.get("strengths") or not x.get("risks") or "pending" not in x.get("legal_risk","") and "preliminary" not in x.get("legal_risk","") for x in m["candidates"]):f.append(Finding("BRD-RISK","candidates","risk omitted"))
 sp=m["search_plan"]
 if sp.get("jurisdictions")!=["CO","WIPO_MADRID"] or set(sp.get("nice_classes_candidate",[]))!={9,35,36,42}:f.append(Finding("BRD-SEARCH","search_plan","scope weakened"))
 for r in sp.get("registries",[]):
  u=urlparse(r.get("url",""))
  if u.scheme!="https" or r.get("state") not in {"pending_manual_legal_search","optional_pending_expansion"}:f.append(Finding("BRD-REGISTRY",str(r.get("id")),"invalid registry/state"))
 domain=next((x for x in m["channels"] if x.get("channel")=="domains"),{})
 if domain.get("result")!="no_availability_claim":f.append(Finding("BRD-DOMAIN","domains","availability overstated"))
 if len(m["brand_architecture"])<6 or any(not x.startswith("Fincilia ") for x in m["brand_architecture"]):f.append(Finding("BRD-ARCHITECTURE","brand_architecture","family drift"))
 ids=[g.get("id") for g in m["gates"]]
 if len(ids)!=len(set(ids)) or any(g.get("state")!="not_met" for g in m["gates"]):f.append(Finding("BRD-GATE","gates","gate promoted/duplicated"))
 return f
def validate_repository(o=None):
 m=o or json.loads((ROOT/MODEL).read_text(encoding="utf-8"));f=validate_model(m);return {"preferred":m.get("preferred_name"),"legal_clearance":m.get("legal_clearance"),"gates_not_met":[g["id"] for g in m.get("gates",[]) if g.get("state")=="not_met"]},f
def main():
 r,f=validate_repository();print(json.dumps({"ok":not f,"report":r,"errors":[x.as_dict() for x in f]},indent=2,sort_keys=True));return 0 if not f else 1
if __name__=="__main__":raise SystemExit(main())
