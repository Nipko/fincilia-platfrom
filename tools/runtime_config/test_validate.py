from __future__ import annotations
import copy,json,unittest
from .validate import ROOT,validate_repository
M=json.loads((ROOT/"docs/platform/runtime-config.json").read_text(encoding="utf-8"))
class ConfigTest(unittest.TestCase):
 def bite(self,m,c):self.assertIn(c,{x.code for x in validate_repository(m)[1]})
 def test_valid(self):r,f=validate_repository();self.assertEqual([],f);self.assertFalse(r["production_enabled"])
 def test_production(self):m=copy.deepcopy(M);m["production_enabled"]=True;self.bite(m,"CFG-GATE")
 def test_ai(self):m=copy.deepcopy(M);m["external_ai_enabled"]=True;self.bite(m,"CFG-GATE")
 def test_env(self):m=copy.deepcopy(M);next(x for x in m["environments"] if x["id"]=="pilot")["enabled"]=True;self.bite(m,"CFG-ENV")
 def test_name(self):m=copy.deepcopy(M);m["variables"][0]["name"]="DATABASE";self.bite(m,"CFG-NAME")
 def secret_index(self,m):return next(i for i,v in enumerate(m["variables"]) if v["class"]=="secret_reference")
 def test_secret(self):m=copy.deepcopy(M);m["variables"][self.secret_index(m)]["safe_example"]="password";self.bite(m,"CFG-SECRET")
 def test_every_secret_uses_the_untracked_placeholder(self):
  self.assertTrue(any(v["class"]=="secret_reference" for v in M["variables"]))
  for v in M["variables"]:
   if v["class"]=="secret_reference":self.assertEqual(v["safe_example"],"set_in_untracked_local_env")
 def test_forbidden(self):m=copy.deepcopy(M);m["forbidden_in_config"]=[];self.bite(m,"CFG-FORBIDDEN")
 def test_order(self):m=copy.deepcopy(M);m["load_order"].reverse();self.bite(m,"CFG-ORDER")
 def test_gate(self):m=copy.deepcopy(M);m["gates"][0]["state"]="met";self.bite(m,"CFG-ACTIVATION")
 def test_schema(self):m=copy.deepcopy(M);m["x"]=1;self.bite(m,"CFG-SCHEMA")
if __name__=="__main__":unittest.main()
