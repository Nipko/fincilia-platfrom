from __future__ import annotations
import copy,json,unittest
from pathlib import Path
from .model import validate,validate_repository
ROOT=Path(__file__).resolve().parents[2]
MODEL=json.loads((ROOT/"docs/architecture/region-transmission-decision.json").read_text(encoding="utf-8"))
PRIVACY=json.loads((ROOT/"docs/privacy/privacy-map.json").read_text(encoding="utf-8"))
class RegionDecisionTests(unittest.TestCase):
    def codes(self,model=MODEL,privacy=PRIVACY): return {item.code for item in validate(model,privacy)}
    def test_repository_contract_is_valid(self): self.assertEqual([],validate_repository(ROOT))
    def test_agent_acceptance_bites(self):
        model=copy.deepcopy(MODEL); model["human_acceptance"]=True; self.assertIn("A02-HUMAN-PENDING",self.codes(model))
    def test_candidate_selection_bites(self):
        model=copy.deepcopy(MODEL); model["candidate_locations"][0]["selected"]=True; self.assertIn("A02-PREMATURE-SELECTION",self.codes(model))
    def test_legal_suitability_bites(self):
        model=copy.deepcopy(MODEL); model["candidate_locations"][0]["legal_suitability"]="approved"; self.assertIn("A02-LEGAL-UNKNOWN",self.codes(model))
    def test_missing_plane_bites(self):
        model=copy.deepcopy(MODEL); model["data_planes"].remove("telemetry_and_support"); self.assertIn("A02-DATA-PLANES",self.codes(model))
    def test_missing_backup_location_bites(self):
        model=copy.deepcopy(MODEL); model["service_location_contract"]["required_fields"].remove("backup_location"); self.assertIn("A02-SERVICE-FIELD",self.codes(model))
    def test_gate_prematurely_met_bites(self):
        model=copy.deepcopy(MODEL); model["decision_gates"][0]["state"]="met"; self.assertIn("A02-GATE-PREMATURE",self.codes(model))
    def test_gate_sod_bites(self):
        model=copy.deepcopy(MODEL); model["decision_gates"][0]["reviewer"]="Legal"; self.assertIn("A02-GATE-SOD",self.codes(model))
    def test_scoring_winner_bites(self):
        model=copy.deepcopy(MODEL); model["scoring_policy"]["winner"]="LOC-AWS-BR"; self.assertIn("A02-FALSE-PRECISION",self.codes(model))
    def test_default_egress_bites(self):
        model=copy.deepcopy(MODEL); model["default_posture"]["external_egress"]="allow"; self.assertIn("A02-DEFAULT-DENY",self.codes(model))
    def test_privacy_alignment_bites(self):
        privacy=copy.deepcopy(PRIVACY); privacy["region_decision"]="resolved"; self.assertIn("A02-PRIVACY-ALIGNMENT",self.codes(privacy=privacy))
    def test_unknown_source_bites(self):
        model=copy.deepcopy(MODEL); model["candidate_locations"][0]["source_ids"]=["UNKNOWN"]; self.assertIn("A02-SOURCE-REFERENCE",self.codes(model))
    def test_edge_as_region_bites(self):
        model=copy.deepcopy(MODEL); model["location_inference"]["edge_or_local_zone_counts_as_full_region"]=True; self.assertIn("A02-LOCATION-INFERENCE",self.codes(model))
if __name__=="__main__": unittest.main()
