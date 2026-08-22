from __future__ import annotations
import copy,json,unittest
from .validate import ROOT,validate_repository
M=json.loads((ROOT/"docs/platform/workspace-scaffold.json").read_text(encoding="utf-8"))
class WorkspaceTest(unittest.TestCase):
 def bite(self,m,c):self.assertIn(c,{x.code for x in validate_repository(m)[1]})
 def test_valid(self):r,f=validate_repository();self.assertEqual([],f);self.assertEqual(7,r["components"])
 def test_product(self):m=copy.deepcopy(M);m["product_code_allowed"]=True;self.bite(m,"WSP-GATE")
 def test_framework(self):m=copy.deepcopy(M);m["framework_install_allowed"]=True;self.bite(m,"WSP-GATE")
 def test_component(self):m=copy.deepcopy(M);m["components"]=m["components"][:-1];self.bite(m,"WSP-COMPONENTS")
 def test_path(self):m=copy.deepcopy(M);m["components"][0]["path"]="../x";self.bite(m,"WSP-PATH")
 def test_worker(self):m=copy.deepcopy(M);m["components"][3]["authority"]="financial";self.bite(m,"WSP-WORKER")
 def test_invariant(self):m=copy.deepcopy(M);m["invariants"]=[];self.bite(m,"WSP-INVARIANTS")
 def test_activation(self):m=copy.deepcopy(M);m["activation_gates"][0]["state"]="met";self.bite(m,"WSP-ACTIVATION")
 def test_schema(self):m=copy.deepcopy(M);m["x"]=1;self.bite(m,"WSP-SCHEMA")
if __name__=="__main__":unittest.main()
