from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[2]; MODEL=Path("docs/product/research-protocol.json")
@dataclass(frozen=True)
class Finding:
    code:str; subject:str; detail:str
    def as_dict(self): return self.__dict__
def validate_model(m:dict[str,Any])->list[Finding]:
    f=[]; keys={"schema_version","task","status","data_ceiling","real_sessions_authorized","recording_allowed","artifact_collection_allowed","human_approval","sample","allowed_now","prohibited_now","session_contract","research_questions","metrics","outputs","gates"}
    if set(m)!=keys:return [Finding("RES-SCHEMA","model","unexpected keys")]
    if m["data_ceiling"]!="synthetic_only" or m["real_sessions_authorized"] is not False:f.append(Finding("RES-DATA","model","real research enabled"))
    if m["recording_allowed"] is not False or m["artifact_collection_allowed"] is not False:f.append(Finding("RES-CAPTURE","model","recording/artifacts enabled"))
    if m["human_approval"]!="pending":f.append(Finding("RES-HUMAN","model","agent approval forbidden"))
    if m["sample"]!={"accounting_firms":5,"close_cycles":10,"independent_smes":5,"minimum_two_cycles_same_process":True}:f.append(Finding("RES-SAMPLE","sample","sample weakened"))
    required={"bank_statement","invoice","tax_id","account_number","customer_name","screen_recording","credentials","otp","dian_certificate","erp_export","transaction_amount","production_screenshot"}
    if not required.issubset(set(m["prohibited_now"])):f.append(Finding("RES-PROHIBITED","prohibited_now","sensitive item removed"))
    c=m["session_contract"]
    if c.get("consent_script_required") is not True or c.get("stop_rule")!="participant_starts_sharing_real_financial_data" or c.get("notes")!="structured_categories_only":f.append(Finding("RES-SESSION","session_contract","fail-closed session weakened"))
    if len(m["research_questions"])<10 or len(m["metrics"])<8:f.append(Finding("RES-COVERAGE","model","questions/metrics weakened"))
    ids=[g.get("id") for g in m["gates"]]
    if len(ids)!=len(set(ids)) or any(g.get("state")!="not_met" for g in m["gates"]):f.append(Finding("RES-GATE","gates","gate duplicate or promoted"))
    return f
def validate_repository(override=None):
    m=override or json.loads((ROOT/MODEL).read_text(encoding="utf-8"));f=validate_model(m);return {"firms":m.get("sample",{}).get("accounting_firms"),"cycles":m.get("sample",{}).get("close_cycles"),"gates_not_met":[g["id"] for g in m.get("gates",[]) if g.get("state")=="not_met"]},f
def main():
    r,f=validate_repository();print(json.dumps({"ok":not f,"report":r,"errors":[x.as_dict() for x in f]},indent=2,sort_keys=True));return 0 if not f else 1
if __name__=="__main__":raise SystemExit(main())
