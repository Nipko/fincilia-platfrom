from __future__ import annotations
import copy,json,unittest
from .validate import ROOT,validate_repository
MODEL=json.loads((ROOT/"docs/business/budget-f0-f2.json").read_text(encoding="utf-8"))
class BudgetModelTest(unittest.TestCase):
    def bites(self,m,c): self.assertIn(c,{x.code for x in validate_repository(m)[1]})
    def test_valid(self):
        r,f=validate_repository(); self.assertEqual([],f); self.assertEqual(3796000000,r["base"]["capital_cop"])
    def test_contingency(self): m=copy.deepcopy(MODEL);m["contingency_percent"]=10;self.bites(m,"FIN-GUARDRAIL")
    def test_revenue(self): m=copy.deepcopy(MODEL);m["uncontracted_revenue_counted"]=True;self.bites(m,"FIN-REVENUE")
    def test_agent_approval(self): m=copy.deepcopy(MODEL);m["founder_approved"]=True;self.bites(m,"FIN-HUMAN")
    def test_trm_source(self): m=copy.deepcopy(MODEL);m["trm"]["source"]="https://example.com";self.bites(m,"FIN-TRM")
    def test_scenario_removed(self): m=copy.deepcopy(MODEL);m["scenarios"]=m["scenarios"][:2];self.bites(m,"FIN-SCENARIOS")
    def test_scenario_order(self): m=copy.deepcopy(MODEL);m["scenarios"][1]["loaded_cost_per_person_month_cop"]=1;self.bites(m,"FIN-ORDER")
    def test_release(self): m=copy.deepcopy(MODEL);m["phase_release"][0]["state"]="released";self.bites(m,"FIN-RELEASE")
    def test_inputs(self): m=copy.deepcopy(MODEL);m["required_human_inputs"]=["cash"];self.bites(m,"FIN-INPUTS")
    def test_sensitivity(self): m=copy.deepcopy(MODEL);m["sensitivity"]["fx_percent"]=[0];self.bites(m,"FIN-SENSITIVITY")
    def test_unknown_key(self): m=copy.deepcopy(MODEL);m["x"]=1;self.bites(m,"FIN-SCHEMA")
if __name__=="__main__":unittest.main()
