from __future__ import annotations
import copy,json,unittest
from .validate import ROOT,validate_repository
M=json.loads((ROOT/"docs/database/migration-tooling.json").read_text(encoding="utf-8"))
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
if __name__=="__main__":unittest.main()
