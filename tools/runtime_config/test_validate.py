from __future__ import annotations
import copy,json,unittest
from .validate import ROOT,validate_repository
M=json.loads((ROOT/"docs/platform/runtime-config.json").read_text(encoding="utf-8"))
class ConfigTest(unittest.TestCase):
 def bite(self,m,c):self.assertIn(c,{x.code for x in validate_repository(m)[1]})
 def test_valid(self):r,f=validate_repository();self.assertEqual([],f);self.assertFalse(r["production_enabled"])
 def test_production(self):m=copy.deepcopy(M);m["production_enabled"]=True;self.bite(m,"CFG-GATE")
 def test_ai(self):m=copy.deepcopy(M);m["external_ai_enabled"]=True;self.bite(m,"CFG-GATE")
 def test_env(self):m=copy.deepcopy(M);m["environments"][3]["enabled"]=True;self.bite(m,"CFG-ENV")
 def test_name(self):m=copy.deepcopy(M);m["variables"][0]["name"]="DATABASE";self.bite(m,"CFG-NAME")
 def test_secret(self):m=copy.deepcopy(M);m["variables"][1]["safe_example"]="password";self.bite(m,"CFG-SECRET")
 def test_forbidden(self):m=copy.deepcopy(M);m["forbidden_in_config"]=[];self.bite(m,"CFG-FORBIDDEN")
 def test_order(self):m=copy.deepcopy(M);m["load_order"].reverse();self.bite(m,"CFG-ORDER")
 def test_gate(self):m=copy.deepcopy(M);m["gates"][0]["state"]="met";self.bite(m,"CFG-ACTIVATION")
 def test_schema(self):m=copy.deepcopy(M);m["x"]=1;self.bite(m,"CFG-SCHEMA")
if __name__=="__main__":unittest.main()
