from __future__ import annotations
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[2];MODEL=Path("docs/database/migration-tooling.json");HOSTS={"github.com","salsita.github.io"}
MIGRATIONS=Path("db/migrations");MIGRATOR=Path("db/migrate/apply.py")
# `local_build` es un alcance aparte: habilita construir en local, y nada mas. Lo
# que NO implica se declara explicitamente para que nadie lo reutilice como si
# fuera la decision humana que todavia no existe.
LOCAL_KEYS={"local_product_build_allowed","scope","compose_project","migrator","reserved_band","does_not_imply"}
NEVER_IMPLIED={"adr_002_accepted","tool_selected","s1_approved","product_migrations_allowed","deployment_to_shared_environment"}
FILENAME=re.compile(r"^V(?P<number>\d{4})__[a-z0-9_]+\.sql$")
# El cuerpo llega hasta el `);` en columna cero: un parentesis interior de un
# CHECK no cierra la tabla.
CREATE_TABLE=re.compile(r"(?ms)^CREATE TABLE (?P<name>fincilia\.[a-z_]+) \((?P<body>.*?)^\);")
DESTRUCTIVE=re.compile(r"(?i)\b(DROP\s+(TABLE|COLUMN|SCHEMA)|TRUNCATE)\b")
@dataclass(frozen=True)
class Finding:
 code:str;subject:str;detail:str
 def as_dict(self):return self.__dict__
EXEMPTION_KEYS={"table","reason","carries","columns_allowed","owner_role","gate"}
COLUMN=re.compile(r"(?m)^  (?P<name>[a-z][a-z0-9_]*)\s")
NEWLINE=chr(10)
def validate_exemptions(items):
 f=[]
 if not isinstance(items,list):return [Finding("DB-RLS-EXEMPTION-SCHEMA","rls_exemptions","not a list")]
 for item in items:
  if not isinstance(item,dict) or set(item)!=EXEMPTION_KEYS:f.append(Finding("DB-RLS-EXEMPTION-SCHEMA",str((item or {}).get("table")),"unexpected keys"));continue
  # Una excepcion sin motivo escrito y sin dueno es una excepcion que nadie
  # revisa: se exige que ambas cosas existan y digan algo.
  if len(str(item["reason"]))<40:f.append(Finding("DB-RLS-EXEMPTION-REASON",str(item["table"]),"the reason must say why, not just that"))
  if item["carries"]!="identifiers_and_timestamps_only":f.append(Finding("DB-RLS-EXEMPTION-PAYLOAD",str(item["table"]),str(item["carries"])))
  if not item["owner_role"] or not item["gate"]:f.append(Finding("DB-RLS-EXEMPTION-OWNER",str(item["table"]),"an exemption needs an owner and a gate"))
 tables=[x.get("table") for x in items if isinstance(x,dict)]
 if len(tables)!=len(set(tables)):f.append(Finding("DB-RLS-EXEMPTION-SCHEMA","rls_exemptions","duplicate table"))
 return f
def exempt_columns(exemptions,qualified):
 for item in exemptions:
  if isinstance(item,dict) and item.get("table")==qualified:return set(item.get("columns_allowed") or [])
 return None
def validate_model(m:dict[str,Any]):
 f=[];keys={"schema_version","task","status","data_ceiling","adr_002_state","selected_tool","preferred_for_spike","human_acceptance","product_migrations_allowed","criteria","candidates","spike_matrix","production_policy","gates","local_build","rls_exemptions"}
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
 f.extend(validate_local_build(m["local_build"]))
 f.extend(validate_exemptions(m["rls_exemptions"]))
 return f
def validate_local_build(b:Any):
 f=[]
 if not isinstance(b,dict) or set(b)!=LOCAL_KEYS:return [Finding("DB-LOCAL-SCHEMA","local_build","unexpected keys")]
 if b["scope"]!="local_only_synthetic":f.append(Finding("DB-LOCAL-SCOPE","local_build",str(b["scope"])))
 if b["migrator"]!=MIGRATOR.as_posix():f.append(Finding("DB-LOCAL-MIGRATOR","local_build",str(b["migrator"])))
 if b["reserved_band"]!="V0001-V0999":f.append(Finding("DB-LOCAL-BAND","local_build",str(b["reserved_band"])))
 if not isinstance(b["local_product_build_allowed"],bool):f.append(Finding("DB-LOCAL-FLAG","local_build","the flag must be a boolean, not a truthy value"))
 # Habilitar la construccion local exige enumerar, en el mismo sitio, cada
 # decision que sigue pendiente. Un permiso sin sus limites acaba citado como si
 # los incluyera.
 if b["local_product_build_allowed"] is True and not NEVER_IMPLIED.issubset(set(b["does_not_imply"])):f.append(Finding("DB-LOCAL-IMPLIES","local_build","enabling the local build must spell out what it still does not authorise"))
 return f
def validate_migrations(root:Path,exemptions=None):
 exemptions=exemptions or []
 f=[];directory=root/MIGRATIONS
 if not (root/MIGRATOR).is_file():
  f.append(Finding("DB-LOCAL-MIGRATOR","repository","the declared migrator does not exist"))
 if not directory.is_dir():return f
 for path in sorted(directory.glob("*")):
  name=path.name
  # Solo el README y migraciones. Un fichero suelto en este directorio es
  # o basura o una migracion que nadie numero.
  if name=="README.md":continue
  match=FILENAME.match(name)
  if not match:
   f.append(Finding("DB-MIGRATION-NAME",name,"expected V####__name.sql"));continue
  number=int(match.group("number"))
  if not 1<=number<=999:f.append(Finding("DB-MIGRATION-BAND",name,"outside the reserved V0001-V0999 band"))
  text=path.read_text(encoding="utf-8")
  # Las reglas textuales miran lo que se ejecuta, no lo que se explica. Un
  # comentario que dice por que NO se hizo algo no puede disparar la regla
  # contra ese algo.
  code=NEWLINE.join(line for line in text.splitlines()
                    if not line.lstrip().startswith("--"))
  if DESTRUCTIVE.search(code):f.append(Finding("DB-MIGRATION-DESTRUCTIVE",name,"destructive DDL needs expand/contract and review, not a migration"))
  if "SECURITY DEFINER" in code:f.append(Finding("DB-MIGRATION-DEFINER",name,"SECURITY DEFINER is forbidden without review"))
  if "BYPASSRLS" in code or "SUPERUSER" in code:f.append(Finding("DB-MIGRATION-PRIVILEGE",name,"a migration must not grant a role that escapes RLS"))
  declared={str(x.get("table")) for x in exemptions if isinstance(x,dict)}
  for table in CREATE_TABLE.finditer(text):
   qualified=table.group("name")
   if "company_id" not in table.group("body"):continue
   if qualified in declared:
    # Excepcion declarada. Se comprueba que las columnas siguen siendo las que
    # se aprobaron: anadir aqui un importe o un nombre de fichero deja de ser
    # invisible y vuelve a exigir una revision.
    allowed=exempt_columns(exemptions,qualified) or set()
    found={c.group("name") for c in COLUMN.finditer(table.group("body"))}
    extra=sorted(found-allowed)
    if extra:f.append(Finding("DB-RLS-EXEMPTION-COLUMNS",qualified,f"undeclared columns {extra}"))
    if f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY;" in text:f.append(Finding("DB-RLS-EXEMPTION-STALE",qualified,"the table has RLS; the exemption is stale and should be removed"))
    continue
   # Una tabla con `company_id` sin RLS forzada es una fuga silenciosa: la
   # consulta correcta devuelve filas de otra empresa y nadie ve un error.
   if f"ALTER TABLE {qualified} ENABLE ROW LEVEL SECURITY;" not in text:f.append(Finding("DB-MIGRATION-RLS",qualified,"company-scoped table without ENABLE ROW LEVEL SECURITY"))
   if f"ALTER TABLE {qualified} FORCE ROW LEVEL SECURITY;" not in text:f.append(Finding("DB-MIGRATION-FORCE",qualified,"without FORCE the owner is exempt and the isolation is only apparent"))
 created={m.group("name") for path in sorted(directory.glob("*.sql")) for m in CREATE_TABLE.finditer(path.read_text(encoding="utf-8"))}
 for item in exemptions:
  if isinstance(item,dict) and item.get("table") not in created:f.append(Finding("DB-RLS-EXEMPTION-STALE",str(item.get("table")),"declared exemption for a table no migration creates"))
 return f
def validate_repository(o=None,root:Path|None=None):
 base=root or ROOT;m=o or json.loads((base/MODEL).read_text(encoding="utf-8"));f=validate_model(m)+validate_migrations(base,m.get("rls_exemptions"))
 return {"preferred_for_spike":m.get("preferred_for_spike"),"selected_tool":m.get("selected_tool"),"spike_tests_not_run":sum(x.get("state")=="not_run" for x in m.get("spike_matrix",[])),"local_product_build_allowed":(m.get("local_build") or {}).get("local_product_build_allowed"),"migrations":sorted(p.name for p in (base/MIGRATIONS).glob("*.sql")),"rls_exemptions":[str(x.get("table")) for x in (m.get("rls_exemptions") or []) if isinstance(x,dict)]},f
def main():
 r,f=validate_repository();print(json.dumps({"ok":not f,"report":r,"errors":[x.as_dict() for x in f]},indent=2,sort_keys=True));return 0 if not f else 1
if __name__=="__main__":raise SystemExit(main())
