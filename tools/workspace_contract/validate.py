from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[2];MODEL=Path("docs/platform/workspace-scaffold.json")
@dataclass(frozen=True)
class Finding:
 code:str;subject:str;detail:str
 def as_dict(self):return self.__dict__
def validate_model(m:dict[str,Any],root:Path=ROOT):
 f=[]; keys={"schema_version","task","status","data_ceiling","product_code_allowed","framework_install_allowed","s1_ready","components","invariants","activation_gates"}
 if set(m)!=keys:return [Finding("WSP-SCHEMA","model","unexpected keys")]
 if m["data_ceiling"]!="synthetic_only" or m["product_code_allowed"] is not False or m["framework_install_allowed"] is not False or m["s1_ready"]!="not_met":f.append(Finding("WSP-GATE","model","pre-S1 boundary weakened"))
 ids=[x.get("id") for x in m["components"]]; expected=["web","api","mobile","document_worker","contracts","config","database"]
 if ids!=expected:f.append(Finding("WSP-COMPONENTS","components",str(ids)))
 for c in m["components"]:
  p=Path(c.get("path","")); target=(root/p)
  if p.is_absolute() or ".." in p.parts or not target.is_dir() or not (target/"README.md").is_file():f.append(Finding("WSP-PATH",str(c.get("id")),str(p)))
 if next((x for x in m["components"] if x.get("id")=="document_worker"),{}).get("authority")!="manifest_only":f.append(Finding("WSP-WORKER","document_worker","authority changed"))
 required={"company_is_financial_boundary","worker_cannot_publish_financial_state","web_and_mobile_never_authorize","no_real_data","no_framework_dependency_before_S1","no_shared_database_writes_across_module_owners"}
 if set(m["invariants"])!=required:f.append(Finding("WSP-INVARIANTS","invariants","drift"))
 if any(g.get("state")!="not_met" for g in m["activation_gates"]):f.append(Finding("WSP-ACTIVATION","activation_gates","premature activation"))
 return f
def validate_repository(o=None):
 m=o or json.loads((ROOT/MODEL).read_text(encoding="utf-8"));f=validate_model(m);return {"components":len(m.get("components",[])),"s1_ready":m.get("s1_ready")},f
def main():
 r,f=validate_repository();print(json.dumps({"ok":not f,"report":r,"errors":[x.as_dict() for x in f]},indent=2,sort_keys=True));return 0 if not f else 1
if __name__=="__main__":raise SystemExit(main())
