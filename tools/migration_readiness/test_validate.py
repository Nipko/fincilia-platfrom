from __future__ import annotations
import copy,json,tempfile,unittest
from pathlib import Path
from .validate import (ROOT,validate_definers,validate_exemptions,validate_migrations,validate_repository)
M=json.loads((ROOT/"docs/database/migration-tooling.json").read_text(encoding="utf-8"))
V1=(ROOT/"db/migrations/V0001__identity_and_tenancy.sql").read_text(encoding="utf-8")
class MigrationTest(unittest.TestCase):
 def bite(self,m,c):self.assertIn(c,{x.code for x in validate_repository(m)[1]})
 def test_valid(self):r,f=validate_repository();self.assertEqual([],f);self.assertIsNone(r["selected_tool"])
 def test_select(self):m=copy.deepcopy(M);m["selected_tool"]="flyway";self.bite(m,"DB-HUMAN")
 def test_adr(self):m=copy.deepcopy(M);m["adr_002_state"]="accepted";self.bite(m,"DB-HUMAN")
 def test_criteria(self):m=copy.deepcopy(M);m["criteria"]=[];self.bite(m,"DB-CRITERIA")
 def test_candidate(self):m=copy.deepcopy(M);m["candidates"]=m["candidates"][:1];self.bite(m,"DB-CANDIDATES")
 def test_evidence(self):m=copy.deepcopy(M);m["candidates"][0]["gaps"]=[];self.bite(m,"DB-EVIDENCE")
 def test_source(self):m=copy.deepcopy(M);m["candidates"][0]["sources"]=["https://example.com"];self.bite(m,"DB-SOURCE")
 def test_spike_claim(self):m=copy.deepcopy(M);m["spike_matrix"][0]["state"]="pass";self.bite(m,"DB-SPIKE")
 def test_policy(self):m=copy.deepcopy(M);m["production_policy"]["startup_auto_migrate"]=True;self.bite(m,"DB-POLICY")
 def test_gate(self):m=copy.deepcopy(M);m["gates"][0]["state"]="met";self.bite(m,"DB-GATE")
 def test_schema(self):m=copy.deepcopy(M);m["x"]=1;self.bite(m,"DB-SCHEMA")

 # ---- alcance local ----------------------------------------------------- #
 def test_local_build_is_declared_and_scoped(self):
  b=M["local_build"];self.assertIs(True,b["local_product_build_allowed"]);self.assertEqual("local_only_synthetic",b["scope"])
 def test_local_build_never_implies_the_human_decision(self):
  self.assertIs(False,M["product_migrations_allowed"]);self.assertEqual("pending",M["human_acceptance"])
 def test_local_flag_without_its_limits_bites(self):
  m=copy.deepcopy(M);m["local_build"]["does_not_imply"]=["adr_002_accepted"];self.bite(m,"DB-LOCAL-IMPLIES")
 def test_dropping_one_limit_bites(self):
  for removed in list(M["local_build"]["does_not_imply"]):
   with self.subTest(removed=removed):
    m=copy.deepcopy(M);m["local_build"]["does_not_imply"]=[x for x in m["local_build"]["does_not_imply"] if x!=removed];self.bite(m,"DB-LOCAL-IMPLIES")
 def test_a_truthy_flag_is_not_a_boolean(self):
  m=copy.deepcopy(M);m["local_build"]["local_product_build_allowed"]="yes";self.bite(m,"DB-LOCAL-FLAG")
 def test_widening_the_scope_bites(self):
  m=copy.deepcopy(M);m["local_build"]["scope"]="any_environment";self.bite(m,"DB-LOCAL-SCOPE")
 def test_moving_the_band_bites(self):
  m=copy.deepcopy(M);m["local_build"]["reserved_band"]="V0001-V9999";self.bite(m,"DB-LOCAL-BAND")
 def test_unknown_local_key_bites(self):
  m=copy.deepcopy(M);m["local_build"]["s1_approved"]=True;self.bite(m,"DB-LOCAL-SCHEMA")

 # ---- migraciones del repositorio --------------------------------------- #
 def scratch(self,name:str,body:str,exemptions=None,definers=None):
  """Un arbol minimo: el validador mira ficheros, no una base levantada."""
  root=Path(tempfile.mkdtemp())
  (root/"db"/"migrations").mkdir(parents=True);(root/"db"/"migrate").mkdir(parents=True)
  (root/"db"/"migrate"/"apply.py").write_text("", encoding="utf-8")
  (root/"db"/"migrations"/name).write_text(body, encoding="utf-8")
  return {x.code for x in validate_migrations(root,exemptions,definers)}
 def test_the_real_migration_directory_is_clean(self):
  self.assertEqual([],validate_migrations(ROOT,M["rls_exemptions"],M["security_definer_functions"]))
 def test_an_unnumbered_file_bites(self):
  self.assertIn("DB-MIGRATION-NAME",self.scratch("fix.sql","SELECT 1;"))
 def test_a_readme_is_allowed(self):
  self.assertEqual(set(),self.scratch("README.md","documentacion"))
 def test_a_number_outside_the_band_bites(self):
  self.assertIn("DB-MIGRATION-BAND",self.scratch("V1000__late.sql","SELECT 1;"))
 def test_destructive_ddl_bites(self):
  for statement in ("DROP TABLE fincilia.company;","ALTER TABLE fincilia.company DROP COLUMN status;","TRUNCATE fincilia.company;","DROP SCHEMA fincilia;"):
   with self.subTest(statement=statement):
    self.assertIn("DB-MIGRATION-DESTRUCTIVE",self.scratch("V0001__x.sql",statement))
 def test_security_definer_bites(self):
  self.assertIn("DB-MIGRATION-DEFINER",self.scratch("V0001__x.sql","CREATE FUNCTION f() RETURNS int LANGUAGE sql SECURITY DEFINER AS 'SELECT 1';"))
 def test_a_role_that_escapes_rls_bites(self):
  for grant in ("ALTER ROLE fincilia_app BYPASSRLS;","CREATE ROLE r SUPERUSER;"):
   with self.subTest(grant=grant):
    self.assertIn("DB-MIGRATION-PRIVILEGE",self.scratch("V0001__x.sql",grant))
 def test_a_company_scoped_table_without_rls_bites(self):
  body="CREATE TABLE fincilia.movement (\n  movement_id uuid PRIMARY KEY,\n  company_id uuid NOT NULL\n);\n"
  codes=self.scratch("V0001__x.sql",body)
  self.assertIn("DB-MIGRATION-RLS",codes);self.assertIn("DB-MIGRATION-FORCE",codes)
 def test_enabling_rls_without_forcing_it_still_bites(self):
  body=("CREATE TABLE fincilia.movement (\n  movement_id uuid PRIMARY KEY,\n  company_id uuid NOT NULL\n);\n"
        "ALTER TABLE fincilia.movement ENABLE ROW LEVEL SECURITY;\n")
  codes=self.scratch("V0001__x.sql",body)
  self.assertNotIn("DB-MIGRATION-RLS",codes);self.assertIn("DB-MIGRATION-FORCE",codes)
 def test_a_table_without_company_id_needs_no_rls(self):
  body="CREATE TABLE fincilia.firm (\n  firm_id uuid PRIMARY KEY,\n  legal_name text NOT NULL\n);\n"
  self.assertEqual(set(),self.scratch("V0001__x.sql",body))
 def test_a_check_parenthesis_does_not_end_the_table(self):
  # Si el cuerpo terminara en el primer `)`, `company_id` quedaria fuera y la
  # tabla pasaria sin RLS.
  body=("CREATE TABLE fincilia.movement (\n  movement_id uuid PRIMARY KEY,\n"
        "  kind text NOT NULL CHECK (kind IN ('debit', 'credit')),\n  company_id uuid NOT NULL\n);\n")
  self.assertIn("DB-MIGRATION-FORCE",self.scratch("V0001__x.sql",body))
 def test_every_company_scoped_table_of_v0001_is_forced(self):
  for table in ("company","engagement","company_grant","authorization_version","audit_event"):
   with self.subTest(table=table):
    self.assertIn(f"ALTER TABLE fincilia.{table} FORCE ROW LEVEL SECURITY;",V1)
 def test_removing_force_from_the_real_migration_bites(self):
  self.assertIn("DB-MIGRATION-FORCE",self.scratch("V0001__x.sql",V1.replace("ALTER TABLE fincilia.audit_event FORCE ROW LEVEL SECURITY;","",1)))

 # ---- excepciones de RLS declaradas ------------------------------------- #
 def test_the_only_exemption_is_the_dispatch_pointer(self):
  self.assertEqual(["fincilia.dispatch_pointer"],[x["table"] for x in M["rls_exemptions"]])
 def test_the_exemption_carries_no_business_data(self):
  item=M["rls_exemptions"][0]
  self.assertEqual("identifiers_and_timestamps_only",item["carries"])
  self.assertTrue(item["owner_role"] and item["gate"])
 def test_an_undeclared_table_without_rls_still_bites(self):
  # La excepcion no es una puerta abierta: solo vale para la tabla declarada.
  body='CREATE TABLE fincilia.otra_tabla (\n  run_id uuid PRIMARY KEY,\n  company_id uuid NOT NULL,\n  kind text NOT NULL,\n  queued_at timestamptz NOT NULL,\n  claimed_at timestamptz,\n  claimed_by text\n);\n'
  codes=self.scratch("V0001__x.sql",body,[json.loads('{"table":"fincilia.dispatch_pointer","reason":"un planificador entre empresas necesita saber que empresa tiene trabajo","carries":"identifiers_and_timestamps_only","columns_allowed":["run_id","company_id","kind","queued_at","claimed_at","claimed_by"],"owner_role":"Security","gate":"DRG-01"}')])
  self.assertIn("DB-MIGRATION-FORCE",codes)
 def test_a_declared_exemption_passes(self):
  codes=self.scratch("V0001__x.sql",'CREATE TABLE fincilia.dispatch_pointer (\n  run_id uuid PRIMARY KEY,\n  company_id uuid NOT NULL,\n  kind text NOT NULL,\n  queued_at timestamptz NOT NULL,\n  claimed_at timestamptz,\n  claimed_by text\n);\n',[json.loads('{"table":"fincilia.dispatch_pointer","reason":"un planificador entre empresas necesita saber que empresa tiene trabajo","carries":"identifiers_and_timestamps_only","columns_allowed":["run_id","company_id","kind","queued_at","claimed_at","claimed_by"],"owner_role":"Security","gate":"DRG-01"}')])
  self.assertEqual(set(),codes)
 def test_adding_an_undeclared_column_to_an_exempt_table_bites(self):
  # Lo que hace util la excepcion: anadir aqui un importe o un nombre de
  # fichero deja de ser invisible y vuelve a exigir una revision.
  body='CREATE TABLE fincilia.dispatch_pointer (\n  run_id uuid PRIMARY KEY,\n  company_id uuid NOT NULL,\n  kind text NOT NULL,\n  queued_at timestamptz NOT NULL,\n  claimed_at timestamptz,\n  claimed_by text,\n  filename text\n);\n'
  codes=self.scratch("V0001__x.sql",body,[json.loads('{"table":"fincilia.dispatch_pointer","reason":"un planificador entre empresas necesita saber que empresa tiene trabajo","carries":"identifiers_and_timestamps_only","columns_allowed":["run_id","company_id","kind","queued_at","claimed_at","claimed_by"],"owner_role":"Security","gate":"DRG-01"}')])
  self.assertIn("DB-RLS-EXEMPTION-COLUMNS",codes)
 def test_an_exemption_for_a_table_that_now_has_rls_is_stale(self):
  body='CREATE TABLE fincilia.dispatch_pointer (\n  run_id uuid PRIMARY KEY,\n  company_id uuid NOT NULL,\n  kind text NOT NULL,\n  queued_at timestamptz NOT NULL,\n  claimed_at timestamptz,\n  claimed_by text\n);\n'+"ALTER TABLE fincilia.dispatch_pointer ENABLE ROW LEVEL SECURITY;"
  codes=self.scratch("V0001__x.sql",body,[json.loads('{"table":"fincilia.dispatch_pointer","reason":"un planificador entre empresas necesita saber que empresa tiene trabajo","carries":"identifiers_and_timestamps_only","columns_allowed":["run_id","company_id","kind","queued_at","claimed_at","claimed_by"],"owner_role":"Security","gate":"DRG-01"}')])
  self.assertIn("DB-RLS-EXEMPTION-STALE",codes)
 def test_an_exemption_for_a_table_nobody_creates_is_stale(self):
  codes=self.scratch("V0001__x.sql","SELECT 1;",[json.loads('{"table":"fincilia.dispatch_pointer","reason":"un planificador entre empresas necesita saber que empresa tiene trabajo","carries":"identifiers_and_timestamps_only","columns_allowed":["run_id","company_id","kind","queued_at","claimed_at","claimed_by"],"owner_role":"Security","gate":"DRG-01"}')])
  self.assertIn("DB-RLS-EXEMPTION-STALE",codes)
 def test_an_exemption_without_a_real_reason_bites(self):
  item=json.loads('{"table":"fincilia.dispatch_pointer","reason":"un planificador entre empresas necesita saber que empresa tiene trabajo","carries":"identifiers_and_timestamps_only","columns_allowed":["run_id","company_id","kind","queued_at","claimed_at","claimed_by"],"owner_role":"Security","gate":"DRG-01"}');item["reason"]="porque si"
  self.assertIn("DB-RLS-EXEMPTION-REASON",{x.code for x in validate_exemptions([item])})
 def test_an_exemption_that_claims_to_carry_data_bites(self):
  item=json.loads('{"table":"fincilia.dispatch_pointer","reason":"un planificador entre empresas necesita saber que empresa tiene trabajo","carries":"identifiers_and_timestamps_only","columns_allowed":["run_id","company_id","kind","queued_at","claimed_at","claimed_by"],"owner_role":"Security","gate":"DRG-01"}');item["carries"]="whatever_is_needed"
  self.assertIn("DB-RLS-EXEMPTION-PAYLOAD",{x.code for x in validate_exemptions([item])})
 def test_an_exemption_without_an_owner_bites(self):
  item=json.loads('{"table":"fincilia.dispatch_pointer","reason":"un planificador entre empresas necesita saber que empresa tiene trabajo","carries":"identifiers_and_timestamps_only","columns_allowed":["run_id","company_id","kind","queued_at","claimed_at","claimed_by"],"owner_role":"Security","gate":"DRG-01"}');item["owner_role"]=""
  self.assertIn("DB-RLS-EXEMPTION-OWNER",{x.code for x in validate_exemptions([item])})
 def test_an_unknown_exemption_key_bites(self):
  item=json.loads('{"table":"fincilia.dispatch_pointer","reason":"un planificador entre empresas necesita saber que empresa tiene trabajo","carries":"identifiers_and_timestamps_only","columns_allowed":["run_id","company_id","kind","queued_at","claimed_at","claimed_by"],"owner_role":"Security","gate":"DRG-01"}');item["forever"]=True
  self.assertIn("DB-RLS-EXEMPTION-SCHEMA",{x.code for x in validate_exemptions([item])})
 def test_a_duplicated_exemption_bites(self):
  item=json.loads('{"table":"fincilia.dispatch_pointer","reason":"un planificador entre empresas necesita saber que empresa tiene trabajo","carries":"identifiers_and_timestamps_only","columns_allowed":["run_id","company_id","kind","queued_at","claimed_at","claimed_by"],"owner_role":"Security","gate":"DRG-01"}')
  self.assertIn("DB-RLS-EXEMPTION-SCHEMA",{x.code for x in validate_exemptions([item,dict(item)])})
 def test_a_comment_explaining_what_was_not_done_does_not_bite(self):
  # El comentario de V0004 explica por que NO se dio BYPASSRLS. Si la regla
  # mirara comentarios, documentar bien penalizaria.
  body="-- Dar BYPASSRLS al worker: descartada." + '\n' + "SELECT 1;"
  self.assertNotIn("DB-MIGRATION-PRIVILEGE",self.scratch("V0001__x.sql",body))
 def test_a_real_bypassrls_grant_still_bites(self):
  self.assertIn("DB-MIGRATION-PRIVILEGE",self.scratch("V0001__x.sql","ALTER ROLE r BYPASSRLS;"))

 # ---- funciones SECURITY DEFINER declaradas ----------------------------- #
 def test_the_declared_definers_are_the_four_dispatch_functions(self):
  names=sorted(x["function"] for x in M["security_definer_functions"])
  self.assertEqual(["fincilia.claim_next_run","fincilia.enqueue_processing_run",
                    "fincilia.finish_run","fincilia.send_to_dead_letter"],names)
 def test_no_definer_is_owned_by_the_schema_owner(self):
  # Si el dueno fuera el migrador, cada EXECUTE seria una escalada hasta el
  # rol que puede cambiar el esquema.
  for item in M["security_definer_functions"]:
   self.assertNotEqual("fincilia_migrator",item["owner_role"])
 def test_the_human_review_is_still_pending(self):
  # `production_policy.security_definer` sigue diciendo
  # `forbidden_without_review`. Declarar no es revisar.
  self.assertEqual("forbidden_without_review",M["production_policy"]["security_definer"])
  for item in M["security_definer_functions"]:
   self.assertEqual("pending",item["human_review_state"])
 def test_marking_the_review_done_bites(self):
  item=json.loads('{"function":"fincilia.f","owner_role":"fincilia_dispatch","granted_to":["fincilia_app"],"reason":"una razon suficientemente larga para que el validador la acepte como explicacion","gate":"DB-G03","human_review_state":"pending"}');item["human_review_state"]="accepted"
  self.assertIn("DB-DEFINER-REVIEW",{x.code for x in validate_definers([item])})
 def test_a_definer_owned_by_the_migrator_bites(self):
  item=json.loads('{"function":"fincilia.f","owner_role":"fincilia_dispatch","granted_to":["fincilia_app"],"reason":"una razon suficientemente larga para que el validador la acepte como explicacion","gate":"DB-G03","human_review_state":"pending"}');item["owner_role"]="fincilia_migrator"
  self.assertIn("DB-DEFINER-OWNER",{x.code for x in validate_definers([item])})
 def test_a_definer_without_a_real_reason_bites(self):
  item=json.loads('{"function":"fincilia.f","owner_role":"fincilia_dispatch","granted_to":["fincilia_app"],"reason":"una razon suficientemente larga para que el validador la acepte como explicacion","gate":"DB-G03","human_review_state":"pending"}');item["reason"]="porque si"
  self.assertIn("DB-DEFINER-REASON",{x.code for x in validate_definers([item])})
 def test_an_undeclared_definer_function_bites(self):
  # La regla no es un permiso general: solo pasa lo declarado.
  self.assertIn("DB-MIGRATION-DEFINER",self.scratch("V0001__x.sql",'CREATE FUNCTION fincilia.f() RETURNS void\nLANGUAGE plpgsql SECURITY DEFINER\nSET search_path = pg_catalog, fincilia\nAS $x$ BEGIN NULL; END; $x$;\nREVOKE ALL PRIVILEGES ON FUNCTION fincilia.f() FROM PUBLIC;\nALTER FUNCTION fincilia.f() OWNER TO fincilia_dispatch;\n',None,[]))
 def test_a_declared_definer_passes(self):
  self.assertEqual(set(),self.scratch("V0001__x.sql",'CREATE FUNCTION fincilia.f() RETURNS void\nLANGUAGE plpgsql SECURITY DEFINER\nSET search_path = pg_catalog, fincilia\nAS $x$ BEGIN NULL; END; $x$;\nREVOKE ALL PRIVILEGES ON FUNCTION fincilia.f() FROM PUBLIC;\nALTER FUNCTION fincilia.f() OWNER TO fincilia_dispatch;\n',None,[json.loads('{"function":"fincilia.f","owner_role":"fincilia_dispatch","granted_to":["fincilia_app"],"reason":"una razon suficientemente larga para que el validador la acepte como explicacion","gate":"DB-G03","human_review_state":"pending"}')]))
 def test_a_definer_without_a_pinned_search_path_bites(self):
  # Sin `search_path` fijo, un objeto colocado antes en la ruta del llamante
  # se ejecuta con los privilegios del dueno de la funcion.
  body='CREATE FUNCTION fincilia.f() RETURNS void\nLANGUAGE plpgsql SECURITY DEFINER\nSET search_path = pg_catalog, fincilia\nAS $x$ BEGIN NULL; END; $x$;\nREVOKE ALL PRIVILEGES ON FUNCTION fincilia.f() FROM PUBLIC;\nALTER FUNCTION fincilia.f() OWNER TO fincilia_dispatch;\n'.replace("SET search_path = pg_catalog, fincilia","")
  self.assertIn("DB-DEFINER-SEARCH-PATH",self.scratch("V0001__x.sql",body,None,[json.loads('{"function":"fincilia.f","owner_role":"fincilia_dispatch","granted_to":["fincilia_app"],"reason":"una razon suficientemente larga para que el validador la acepte como explicacion","gate":"DB-G03","human_review_state":"pending"}')]))
 def test_a_definer_left_open_to_public_bites(self):
  body='CREATE FUNCTION fincilia.f() RETURNS void\nLANGUAGE plpgsql SECURITY DEFINER\nSET search_path = pg_catalog, fincilia\nAS $x$ BEGIN NULL; END; $x$;\nREVOKE ALL PRIVILEGES ON FUNCTION fincilia.f() FROM PUBLIC;\nALTER FUNCTION fincilia.f() OWNER TO fincilia_dispatch;\n'.replace("REVOKE ALL PRIVILEGES ON FUNCTION fincilia.f() FROM PUBLIC;","")
  self.assertIn("DB-DEFINER-PUBLIC",self.scratch("V0001__x.sql",body,None,[json.loads('{"function":"fincilia.f","owner_role":"fincilia_dispatch","granted_to":["fincilia_app"],"reason":"una razon suficientemente larga para que el validador la acepte como explicacion","gate":"DB-G03","human_review_state":"pending"}')]))
 def test_a_definer_whose_owner_is_never_set_bites(self):
  body='CREATE FUNCTION fincilia.f() RETURNS void\nLANGUAGE plpgsql SECURITY DEFINER\nSET search_path = pg_catalog, fincilia\nAS $x$ BEGIN NULL; END; $x$;\nREVOKE ALL PRIVILEGES ON FUNCTION fincilia.f() FROM PUBLIC;\nALTER FUNCTION fincilia.f() OWNER TO fincilia_dispatch;\n'.replace("ALTER FUNCTION fincilia.f() OWNER TO fincilia_dispatch;","")
  self.assertIn("DB-DEFINER-OWNER",self.scratch("V0001__x.sql",body,None,[json.loads('{"function":"fincilia.f","owner_role":"fincilia_dispatch","granted_to":["fincilia_app"],"reason":"una razon suficientemente larga para que el validador la acepte como explicacion","gate":"DB-G03","human_review_state":"pending"}')]))

 # ---- columnas anadidas por ALTER ---------------------------------------- #
 def test_a_column_added_by_alter_is_checked_against_the_exemption(self):
  # V0004 prometia que anadir un dato de negocio a la tabla exenta no podia
  # pasar desapercibido. Mirando solo CREATE TABLE, si podia.
  body=("CREATE TABLE fincilia.dispatch_pointer (" + chr(10) +
        "  run_id uuid PRIMARY KEY," + chr(10) +
        "  company_id uuid NOT NULL" + chr(10) + ");" + chr(10) +
        "ALTER TABLE fincilia.dispatch_pointer" + chr(10) +
        "  ADD COLUMN importe numeric(38,12);" + chr(10))
  exempt=[x for x in M["rls_exemptions"] if x["table"]=="fincilia.dispatch_pointer"]
  self.assertIn("DB-RLS-EXEMPTION-COLUMNS",self.scratch("V0001__x.sql",body,exempt))
 def test_available_at_is_declared_in_the_exemption(self):
  columns=[x for x in M["rls_exemptions"]
           if x["table"]=="fincilia.dispatch_pointer"][0]["columns_allowed"]
  self.assertIn("available_at",columns)
 def test_a_missing_migrator_bites(self):
  root=Path(tempfile.mkdtemp());(root/"db"/"migrations").mkdir(parents=True)
  self.assertIn("DB-LOCAL-MIGRATOR",{x.code for x in validate_migrations(root)})
if __name__=="__main__":unittest.main()
