from __future__ import annotations
import json
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = Path("docs/business/budget-f0-f2.json")

@dataclass(frozen=True)
class Finding:
    code: str; subject: str; detail: str
    def as_dict(self) -> dict[str, str]: return self.__dict__

def calculate(scenario: dict[str, Any], contingency: int, trm: Decimal, months: int) -> dict[str, int]:
    labor = scenario["person_months"] * scenario["loaded_cost_per_person_month_cop"]
    non_labor = sum(scenario["non_labor_cop"].values())
    capital = (Decimal(labor + non_labor) * (Decimal(100 + contingency) / 100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return {"labor_cop": labor, "non_labor_cop": non_labor, "capital_cop": int(capital), "capital_usd": int((capital / trm).quantize(Decimal("1"), rounding=ROUND_HALF_UP)), "monthly_burn_cop": int((capital / months).quantize(Decimal("1"), rounding=ROUND_HALF_UP))}

def validate_model(model: dict[str, Any]) -> list[Finding]:
    f: list[Finding] = []
    expected = {"schema_version","task","status","currency","trm","planning_horizon_months","contingency_percent","uncontracted_revenue_counted","founder_approved","scenarios","phase_release","sensitivity","required_human_inputs"}
    if set(model) != expected: return [Finding("FIN-SCHEMA","model","unexpected keys")]
    if model["currency"] != "COP" or model["contingency_percent"] != 30: f.append(Finding("FIN-GUARDRAIL","model","currency/contingency changed"))
    if model["uncontracted_revenue_counted"] is not False: f.append(Finding("FIN-REVENUE","model","uncontracted revenue counted"))
    if model["founder_approved"] is not False: f.append(Finding("FIN-HUMAN","model","agent cannot approve budget"))
    if set(model["trm"]) != {"cop_per_usd","date","source"} or model["trm"]["cop_per_usd"] <= 0 or not model["trm"]["source"].startswith("https://www.superfinanciera.gov.co/"): f.append(Finding("FIN-TRM","trm","TRM evidence invalid"))
    ids = [x.get("id") for x in model["scenarios"]]
    if ids != ["lean","base","high"]: f.append(Finding("FIN-SCENARIOS","scenarios",str(ids)))
    previous = 0
    for s in model["scenarios"]:
        if set(s) != {"id","person_months","loaded_cost_per_person_month_cop","non_labor_cop"} or len(s["non_labor_cop"]) < 6: f.append(Finding("FIN-SCENARIO-SCHEMA",str(s.get("id")),"incomplete")); continue
        result = calculate(s, model["contingency_percent"], Decimal(str(model["trm"]["cop_per_usd"])), model["planning_horizon_months"])
        if result["capital_cop"] <= previous: f.append(Finding("FIN-ORDER",s["id"],"capital not increasing"))
        previous = result["capital_cop"]
    if any(x.get("state") != "not_released" for x in model["phase_release"]): f.append(Finding("FIN-RELEASE","phase_release","phase prematurely released"))
    if len(model["required_human_inputs"]) < 10: f.append(Finding("FIN-INPUTS","required_human_inputs","inputs weakened"))
    if model["sensitivity"] != {"fx_percent":[-25,-10,0,10,25],"person_month_percent":[-10,0,10],"non_labor_percent":[-20,0,20]}: f.append(Finding("FIN-SENSITIVITY","sensitivity","scenarios weakened"))
    return f

def validate_repository(model_override: dict[str, Any] | None=None):
    model=model_override or json.loads((ROOT/MODEL_PATH).read_text(encoding="utf-8")); findings=validate_model(model)
    trm=Decimal(str(model["trm"]["cop_per_usd"])); report={s["id"]:calculate(s,model["contingency_percent"],trm,model["planning_horizon_months"]) for s in model["scenarios"]}
    return report, findings

def main() -> int:
    report, findings=validate_repository(); print(json.dumps({"ok":not findings,"report":report,"errors":[x.as_dict() for x in findings]},indent=2,sort_keys=True)); return 0 if not findings else 1
if __name__=="__main__": raise SystemExit(main())
