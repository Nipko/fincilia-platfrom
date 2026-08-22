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
 def test_local_build_is_declared_and_scoped(self):
  b=M["local_build"];self.assertIs(True,b["local_product_build_allowed"]);self.assertEqual("local_only_synthetic",b["scope"])
 def test_the_pre_s1_flags_stay_false(self):
  self.assertIs(False,M["product_code_allowed"]);self.assertIs(False,M["framework_install_allowed"]);self.assertEqual("not_met",M["s1_ready"])
 def test_local_flag_without_its_limits_bites(self):
  m=copy.deepcopy(M);m["local_build"]["does_not_imply"]=["real_data"];self.bite(m,"WSP-LOCAL-IMPLIES")
 def test_dropping_one_limit_bites(self):
  for removed in list(M["local_build"]["does_not_imply"]):
   with self.subTest(removed=removed):
    m=copy.deepcopy(M);m["local_build"]["does_not_imply"]=[x for x in m["local_build"]["does_not_imply"] if x!=removed];self.bite(m,"WSP-LOCAL-IMPLIES")
 def test_a_truthy_flag_is_not_a_boolean(self):
  m=copy.deepcopy(M);m["local_build"]["local_product_build_allowed"]="yes";self.bite(m,"WSP-LOCAL-FLAG")
 def test_widening_the_scope_bites(self):
  m=copy.deepcopy(M);m["local_build"]["scope"]="any_environment";self.bite(m,"WSP-LOCAL-SCOPE")
 def test_building_a_component_that_does_not_exist_bites(self):
  m=copy.deepcopy(M);m["local_build"]["built_components"]=["payments"];self.bite(m,"WSP-LOCAL-COMPONENT")
 def test_an_unknown_local_key_bites(self):
  m=copy.deepcopy(M);m["local_build"]["s1_ready"]=True;self.bite(m,"WSP-LOCAL-SCHEMA")
 def test_the_api_component_describes_what_the_repository_holds(self):
  api=next(x for x in M["components"] if x["id"]=="api")
  self.assertEqual("python",api["runtime"]);self.assertIn("FastAPI",api["target"])
if __name__=="__main__":unittest.main()
