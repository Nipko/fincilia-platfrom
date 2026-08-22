from __future__ import annotations
import copy,json,tempfile,unittest
from pathlib import Path
from .validate import ROOT,validate_migrations,validate_repository
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
 def scratch(self,name:str,body:str):
  """Un arbol minimo: el validador mira ficheros, no una base levantada."""
  root=Path(tempfile.mkdtemp())
  (root/"db"/"migrations").mkdir(parents=True);(root/"db"/"migrate").mkdir(parents=True)
  (root/"db"/"migrate"/"apply.py").write_text("", encoding="utf-8")
  (root/"db"/"migrations"/name).write_text(body, encoding="utf-8")
  return {x.code for x in validate_migrations(root)}
 def test_the_real_migration_directory_is_clean(self):
  self.assertEqual([],validate_migrations(ROOT))
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
 def test_a_missing_migrator_bites(self):
  root=Path(tempfile.mkdtemp());(root/"db"/"migrations").mkdir(parents=True)
  self.assertIn("DB-LOCAL-MIGRATOR",{x.code for x in validate_migrations(root)})
if __name__=="__main__":unittest.main()
