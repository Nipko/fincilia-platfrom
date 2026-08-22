from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[2];MODEL=Path("docs/database/migration-tooling.json");HOSTS={"github.com","salsita.github.io"}
@dataclass(frozen=True)
class Finding:
 code:str;subject:str;detail:str
 def as_dict(self):return self.__dict__
def validate_model(m:dict[str,Any]):
 f=[];keys={"schema_version","task","status","data_ceiling","adr_002_state","selected_tool","preferred_for_spike","human_acceptance","product_migrations_allowed","criteria","candidates","spike_matrix","production_policy","gates"}
 if set(m)!=keys:return [Finding("DB-SCHEMA","model","unexpected keys")]
 if m["data_ceiling"]!="synthetic_only" or m["adr_002_state"]!="proposed" or m["selected_tool"] is not None or m["human_acceptance"]!="pending" or m["product_migrations_allowed"] is not False:f.append(Finding("DB-HUMAN","model","decision prematurely accepted"))
 required={"plain_sql","versioned_order","content_checksum","transaction_by_default","concurrency_lock","strict_out_of_order","dry_run_or_plan","separate_migrator_role","postgresql_17","blank_replay_upgrade_tests","immutable_applied_migrations","forward_only_production","expand_contract"}
 if set(m["criteria"])!=required:f.append(Finding("DB-CRITERIA","criteria","criteria drift"))
 ids=[x.get("id") for x in m["candidates"]]
 if ids!=["flyway","dbmate","node_pg_migrate"] or m["preferred_for_spike"]!="flyway":f.append(Finding("DB-CANDIDATES","candidates",str(ids)))
 for c in m["candidates"]:
  if not c.get("strengths") or not c.get("gaps") or not c.get("sources"):f.append(Finding("DB-EVIDENCE",str(c.get("id")),"incomplete"))
  for source in c.get("sources",[]):
   u=urlparse(source)
   if u.scheme!="https" or u.hostname not in HOSTS:f.append(Finding("DB-SOURCE",str(c.get("id")),source))
 tests=m["spike_matrix"]
 if len(tests)!=8 or len({x.get("id") for x in tests})!=8 or any(x.get("state")!="not_run" for x in tests):f.append(Finding("DB-SPIKE","spike_matrix","tests missing or falsely passed"))
 p=m["production_policy"]
 if p!={"down_migrations":"forbidden_as_normal_rollback","rollback":"forward_fix_or_application_rollback_with_compatible_schema","applied_file_edit":"forbidden","migration_actor":"dedicated_non_runtime_role","startup_auto_migrate":False,"security_definer":"forbidden_without_review"}:f.append(Finding("DB-POLICY","production_policy","unsafe policy"))
 if any(g.get("state")!="not_met" for g in m["gates"]):f.append(Finding("DB-GATE","gates","premature gate"))
 return f
def validate_repository(o=None):
 m=o or json.loads((ROOT/MODEL).read_text(encoding="utf-8"));f=validate_model(m);return {"preferred_for_spike":m.get("preferred_for_spike"),"selected_tool":m.get("selected_tool"),"spike_tests_not_run":sum(x.get("state")=="not_run" for x in m.get("spike_matrix",[]))},f
def main():
 r,f=validate_repository();print(json.dumps({"ok":not f,"report":r,"errors":[x.as_dict() for x in f]},indent=2,sort_keys=True));return 0 if not f else 1
if __name__=="__main__":raise SystemExit(main())
