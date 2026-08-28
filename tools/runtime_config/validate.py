from __future__ import annotations
import json,re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[2];MODEL=Path("docs/platform/runtime-config.json")
@dataclass(frozen=True)
class Finding:
 code:str;subject:str;detail:str
 def as_dict(self):return self.__dict__
def validate_model(m:dict[str,Any],root:Path=ROOT):
 f=[]; keys={"schema_version","task","status","active_environment","production_enabled","external_ai_enabled","real_data_enabled","environments","variables","forbidden_in_config","load_order","gates"}
 if set(m)!=keys:return [Finding("CFG-SCHEMA","model","unexpected keys")]
 if m["active_environment"]!="local" or m["production_enabled"] is not False or m["external_ai_enabled"] is not False or m["real_data_enabled"] is not False:f.append(Finding("CFG-GATE","model","unsafe capability enabled"))
 envs={x.get("id"):x for x in m["environments"]}
 if set(envs)!={"local","ci","pilot","staging","production"} or any(envs.get(x,{}).get("enabled") is not False for x in ("pilot","staging","production")):f.append(Finding("CFG-ENV","environments","environment drift"))
 names=[x.get("name") for x in m["variables"]]
 if len(names)!=len(set(names)) or any(not re.fullmatch(r"FINCILIA_[A-Z0-9_]+",str(x)) for x in names):f.append(Finding("CFG-NAME","variables","invalid/duplicate variable"))
 for v in m["variables"]:
  if set(v)!={"name","class","required","safe_example","owner"} or not v["owner"]:f.append(Finding("CFG-VARIABLE",str(v.get("name")),"invalid variable"));continue
  if v["class"]=="secret_reference" and v["safe_example"]!="set_in_untracked_local_env":f.append(Finding("CFG-SECRET",v["name"],"secret value/example forbidden"))
 if len(m["forbidden_in_config"])<9:f.append(Finding("CFG-FORBIDDEN","forbidden_in_config","denylist weakened"))
 if m["load_order"]!=["compiled_safe_defaults","environment_file_untracked_local_only","secret_provider_reference","runtime_policy_validation"]:f.append(Finding("CFG-ORDER","load_order","load order changed"))
 if any(g.get("state")!="not_met" for g in m["gates"]):f.append(Finding("CFG-ACTIVATION","gates","gate prematurely met"))
 example=(root/".env.example").read_text(encoding="utf-8")
 declared={line.split("=",1)[0] for line in example.splitlines() if line and not line.startswith("#")}
 if declared!=set(names):f.append(Finding("CFG-EXAMPLE",".env.example",f"declared={sorted(declared)}"))
 return f
def validate_repository(o=None):
 m=o or json.loads((ROOT/MODEL).read_text(encoding="utf-8"));f=validate_model(m);return {"variables":len(m.get("variables",[])),"production_enabled":m.get("production_enabled")},f
def main():
 r,f=validate_repository();print(json.dumps({"ok":not f,"report":r,"errors":[x.as_dict() for x in f]},indent=2,sort_keys=True));return 0 if not f else 1
if __name__=="__main__":raise SystemExit(main())
