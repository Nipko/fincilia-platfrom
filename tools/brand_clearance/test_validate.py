from __future__ import annotations
import copy,json,unittest
from .validate import ROOT,validate_repository
M=json.loads((ROOT/"docs/business/brand-clearance.json").read_text(encoding="utf-8"))
class BrandTest(unittest.TestCase):
 def bite(self,m,c):self.assertIn(c,{x.code for x in validate_repository(m)[1]})
 def test_valid(self):r,f=validate_repository();self.assertEqual([],f);self.assertEqual("Fincilia",r["preferred"])
 def test_clearance(self):m=copy.deepcopy(M);m["legal_clearance"]="clear";self.bite(m,"BRD-LEGAL")
 def test_agent_file(self):m=copy.deepcopy(M);m["agent_may_file_or_reserve"]=True;self.bite(m,"BRD-LEGAL")
 def test_preference(self):m=copy.deepcopy(M);m["preferred_name"]="Cotejo";self.bite(m,"BRD-PREFERRED")
 def test_candidate(self):m=copy.deepcopy(M);m["candidates"]=m["candidates"][:1];self.bite(m,"BRD-CANDIDATES")
 def test_risk(self):m=copy.deepcopy(M);m["candidates"][0]["risks"]=[];self.bite(m,"BRD-RISK")
 def test_jurisdiction(self):m=copy.deepcopy(M);m["search_plan"]["jurisdictions"]=["CO"];self.bite(m,"BRD-SEARCH")
 def test_registry(self):m=copy.deepcopy(M);m["search_plan"]["registries"][0]["state"]="clear";self.bite(m,"BRD-REGISTRY")
 def test_domain(self):m=copy.deepcopy(M);next(x for x in m["channels"] if x["channel"]=="domains")["result"]="available";self.bite(m,"BRD-DOMAIN")
 def test_family(self):m=copy.deepcopy(M);m["brand_architecture"]=["Other"];self.bite(m,"BRD-ARCHITECTURE")
 def test_gate(self):m=copy.deepcopy(M);m["gates"][0]["state"]="met";self.bite(m,"BRD-GATE")
 def test_schema(self):m=copy.deepcopy(M);m["x"]=1;self.bite(m,"BRD-SCHEMA")
if __name__=="__main__":unittest.main()
