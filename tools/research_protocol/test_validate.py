from __future__ import annotations
import copy,json,unittest
from .validate import ROOT,validate_repository
M=json.loads((ROOT/"docs/product/research-protocol.json").read_text(encoding="utf-8"))
class ResearchProtocolTest(unittest.TestCase):
 def bite(self,m,c):self.assertIn(c,{x.code for x in validate_repository(m)[1]})
 def test_valid(self):r,f=validate_repository();self.assertEqual([],f);self.assertEqual(10,r["cycles"])
 def test_real(self):m=copy.deepcopy(M);m["real_sessions_authorized"]=True;self.bite(m,"RES-DATA")
 def test_record(self):m=copy.deepcopy(M);m["recording_allowed"]=True;self.bite(m,"RES-CAPTURE")
 def test_artifact(self):m=copy.deepcopy(M);m["artifact_collection_allowed"]=True;self.bite(m,"RES-CAPTURE")
 def test_approval(self):m=copy.deepcopy(M);m["human_approval"]="accepted";self.bite(m,"RES-HUMAN")
 def test_sample(self):m=copy.deepcopy(M);m["sample"]["close_cycles"]=2;self.bite(m,"RES-SAMPLE")
 def test_prohibited(self):m=copy.deepcopy(M);m["prohibited_now"].remove("credentials");self.bite(m,"RES-PROHIBITED")
 def test_stop(self):m=copy.deepcopy(M);m["session_contract"]["stop_rule"]="continue";self.bite(m,"RES-SESSION")
 def test_questions(self):m=copy.deepcopy(M);m["research_questions"]=[];self.bite(m,"RES-COVERAGE")
 def test_gate(self):m=copy.deepcopy(M);m["gates"][0]["state"]="met";self.bite(m,"RES-GATE")
 def test_schema(self):m=copy.deepcopy(M);m["x"]=1;self.bite(m,"RES-SCHEMA")
if __name__=="__main__":unittest.main()
