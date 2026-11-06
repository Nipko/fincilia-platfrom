"""FNC-SMB-003 contra PostgreSQL real: reglas aprobadas, aplicacion y reversion.

ADR-039 §4. Una regla nace de una decision humana, nace `proposed`, solo se
activa con la aprobacion que exige el perfil, solo confirma candidatos que
cumplen todas sus condiciones sobre fuentes verificadas y cada aplicacion queda
`approved_rule` con regla, version y aprobador, reversible sin borrar nada.
Solo datos sinteticos.
"""

from __future__ import annotations

import json
import uuid

import psycopg

from db.seed.local import stable_id
from db.tests import test_reconciliation_candidates as rec
from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN
from db.tests.test_operating_profile import REASON, force_profile
from db.tests.test_p3_vertical import ESPIGA, OWNER, PREPARER, REVIEWER

AUDITOR_ANDINOS = "carla@demo.local"
OWNER_ID = stable_id("subject", "sofia")
PREPARER_ID = stable_id("subject", "ana")
REVIEWER_ID = stable_id("subject", "beto")


def slug(response) -> str:
    return response.json()["type"].rsplit("/", 1)[-1]


def _only_smb_tests(cls: type) -> type:
    for name in dir(cls):
        if name.startswith("test") and not name.startswith("test_smb"):
            setattr(cls, name, None)
    return cls


@_only_smb_tests
class ReconciliationRuleTests(rec.ReconciliationCandidateTests):
    accounts: set[str] = set()
    sources: set[str] = set()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.__exit__(None, None, None)
        force_profile(ESPIGA, "estricto")

    # ------------------------------------------------------------ helpers #

    def key(self, label: str) -> dict[str, str]:
        return {"Idempotency-Key": f"smb003-{label}-{uuid.uuid4().hex}"}

    def post(self, user: str, path: str, body: dict | None = None,
             key: dict[str, str] | None = None):
        return self.client.post(
            f"/api/v1/companies/{ESPIGA}/reconciliation/{path}",
            headers={**self.auth(user), **(key or self.key("cmd"))}, json=body or {})

    def build(self) -> dict:
        source, account = self.second_channel()
        m = uuid.uuid4().hex[:8]
        left = self.dataset([
            ("13/02/2026", f"Pago NIT FNC-SYN-NIT-0007 lote1 {m}", f"L1-{m}", "-200.000,00"),
            ("14/02/2026", f"Pago NIT FNC-SYN-NIT-0007 lote2 {m}", f"L2-{m}", "-300.000,00"),
            ("15/02/2026", f"Pago NIT FNC-SYN-NIT-0007 lote3 {m}", f"L3-{m}", "-400.000,00"),
            ("16/02/2026", f"Pago NIT FNC-SYN-NIT-0007 lote4 {m}", f"L4-{m}", "-400.000,00"),
            ("17/02/2026", f"Pago NIT FNC-SYN-NIT-0007 lote5 {m}", f"L5-{m}", "-50.000,00"),
        ], marker=f"rule-left-{m}", source=rec.SOURCE, account=rec.ACCOUNT)
        right = self.dataset([
            ("13/02/2026", "Abono NIT FNC-SYN-NIT-0007", f"R1-{m}", "200.000,00"),
            ("14/02/2026", "Abono NIT FNC-SYN-NIT-0007", f"R2-{m}", "300.000,00"),
            ("15/02/2026", "Abono NIT FNC-SYN-NIT-0007", f"R3-{m}", "400.000,00"),
            ("17/02/2026", "Abono NIT FNC-SYN-NIT-0007", f"R5-{m}", "50.000,00"),
            ("18/02/2026", "Abono de otro cliente", f"R5B-{m}", "50.000,00"),
        ], marker=f"rule-right-{m}", source=source, account=account)
        query = {"left_dataset_id": left, "right_dataset_id": right, "max_days": 3}
        explored = self.client.get(
            f"/api/v1/companies/{ESPIGA}/reconciliation/candidates",
            headers=self.auth(PREPARER), params={**query, "limit": 50})
        self.assertEqual(200, explored.status_code, explored.text)
        pairs = {}
        for pair in explored.json()["candidates"]:
            pairs[(pair["left"]["reference"][:2], pair["right"]["reference"].split("-")[0])] = pair
        return {"query": query, "pairs": pairs, "right_account": account,
                "source": source, "marker": m}

    def propose(self, query: dict, pair: dict, user: str = PREPARER) -> str:
        response = self.post(user, "reviews", {
            **query, "left_movement_id": pair["left"]["movement_id"],
            "right_movement_id": pair["right"]["movement_id"]})
        self.assertEqual(200, response.status_code, response.text)
        return response.json()["candidate_id"]

    def confirm(self, candidate_id: str, user: str = REVIEWER):
        return self.post(user, f"reviews/{candidate_id}/decision",
                         {"decision": "confirmed",
                          "reason_code": "documented_counterpart"})

    def review(self, candidate_id: str) -> dict:
        response = self.client.get(
            f"/api/v1/companies/{ESPIGA}/reconciliation/reviews/{candidate_id}",
            headers=self.auth(REVIEWER))
        self.assertEqual(200, response.status_code, response.text)
        return response.json()

    def conditions(self, account: str, **overrides) -> dict:
        body = {"description_contains": "Abono NIT FNC-SYN-NIT-0007",
                "financial_account_id": account, "direction": "inflow",
                "max_amount_difference": "0", "currency": "COP"}
        body.update(overrides)
        return body

    # -------------------------------------------------------------- tests #

    def test_smb003_rule_lifecycle_apply_and_revert_in_strict_profile(self) -> None:
        world = self.build()
        query, pairs = world["query"], world["pairs"]
        self.assertEqual({("L1", "R1"), ("L2", "R2"), ("L3", "R3"), ("L4", "R3"),
                          ("L5", "R5"), ("L5", "R5B")}, set(pairs))

        # 1. Decision humana y propuesta «¿aplicar siempre?».
        human = self.propose(query, pairs[("L1", "R1")])
        confirmed = self.confirm(human)
        self.assertEqual(200, confirmed.status_code, confirmed.text)
        decision_id = confirmed.json()["decision"]["decision_id"]
        proposal = self.post(PREPARER, "rules/proposal", {"decision_id": decision_id})
        self.assertEqual(200, proposal.status_code, proposal.text)
        self.assertEqual("nit fnc syn nit 0007",
                         proposal.json()["conditions"]["description_contains"])
        self.assertEqual("estricto", proposal.json()["operating_profile"])

        # 2. La regla nace `proposed` y el preparador no puede aprobarla.
        created = self.post(PREPARER, "rules", {
            "conditions": self.conditions(world["right_account"]),
            "created_from_decision_id": decision_id})
        self.assertEqual(201, created.status_code, created.text)
        rule = created.json()
        self.assertEqual("proposed", rule["status"])
        self.assertEqual("abono nit fnc syn nit 0007",
                         rule["conditions"]["description_contains"])
        self.assertEqual(decision_id, rule["created_from_decision_id"])
        self.assertEqual(403, self.post(PREPARER, f"rules/{rule['rule_id']}/approval")
                         .status_code)

        # Una regla propuesta no confirma nada.
        idle = self.post(PREPARER, "rules/apply", query)
        self.assertEqual(200, idle.status_code, idle.text)
        self.assertEqual([], idle.json()["applied"])

        # 3. En `estricto` el autor no aprueba su propia regla.
        own = self.post(OWNER, "rules", {
            "conditions": self.conditions(world["right_account"],
                                          description_contains="otra condicion")})
        self.assertEqual(201, own.status_code, own.text)
        self_approval = self.post(OWNER, f"rules/{own.json()['rule_id']}/approval")
        self.assertEqual(409, self_approval.status_code, self_approval.text)
        self.assertEqual("segregation-of-duties", slug(self_approval))

        approved = self.post(REVIEWER, f"rules/{rule['rule_id']}/approval")
        self.assertEqual(200, approved.status_code, approved.text)
        self.assertEqual("active", approved.json()["status"])
        self.assertEqual("independent", approved.json()["approval"]["review_mode"])
        self.assertEqual(REVIEWER_ID, approved.json()["approval"]["approved_by"])

        # 4. Aplicar: solo lo inequivoco y lo no confirmado.
        apply_key = self.key("apply")
        applied = self.post(PREPARER, "rules/apply", query, apply_key)
        self.assertEqual(200, applied.status_code, applied.text)
        result = applied.json()
        self.assertEqual({(item["left_movement_id"], item["right_movement_id"])
                          for item in result["applied"]},
                         {(pairs[("L2", "R2")]["left"]["movement_id"],
                           pairs[("L2", "R2")]["right"]["movement_id"]),
                          (pairs[("L5", "R5")]["left"]["movement_id"],
                           pairs[("L5", "R5")]["right"]["movement_id"])})
        reasons = {item["reason"] for item in result["skipped"]}
        self.assertIn("ambiguous", reasons)
        self.assertIn("already_confirmed", reasons)
        replay = self.post(PREPARER, "rules/apply", query, apply_key)
        self.assertTrue(replay.json()["replayed"])
        self.assertEqual(result["applied"], replay.json()["applied"])

        l5 = next(item for item in result["applied"]
                  if item["left_movement_id"] == pairs[("L5", "R5")]["left"]["movement_id"])
        auto = self.review(l5["candidate_id"])
        self.assertEqual("confirmed", auto["status"])
        self.assertEqual("approved_rule", auto["decision"]["review_mode"])
        self.assertEqual(rule["rule_id"], auto["decision"]["rule_id"])
        self.assertEqual(1, auto["decision"]["rule_version"])
        self.assertEqual(REVIEWER_ID, auto["decision"]["decided_by"])
        self.assertEqual("approved_rule_match", auto["decision"]["reason_code"])

        # 5. Mientras la aplicacion siga vigente, L5 no se confirma con otra pareja.
        other = self.propose(query, pairs[("L5", "R5B")])
        blocked = self.confirm(other)
        self.assertEqual(409, blocked.status_code, blocked.text)
        self.assertEqual("movement-already-confirmed", slug(blocked))

        # 6. Revertir es una fila nueva y libera el movimiento.
        human_revert = self.post(PREPARER, f"decisions/{decision_id}/reversal",
                                 {"reason_code": "rule_too_broad"})
        self.assertEqual(409, human_revert.status_code, human_revert.text)
        reverted = self.post(PREPARER, f"decisions/{l5['decision_id']}/reversal",
                             {"reason_code": "wrong_counterpart"})
        self.assertEqual(200, reverted.status_code, reverted.text)
        self.assertEqual("reverted", reverted.json()["status"])
        self.assertEqual("approved_rule", reverted.json()["decision"]["review_mode"])
        twice = self.post(PREPARER, f"decisions/{l5['decision_id']}/reversal",
                          {"reason_code": "wrong_counterpart"})
        self.assertEqual(409, twice.status_code, twice.text)
        freed = self.confirm(other)
        self.assertEqual(200, freed.status_code, freed.text)
        self.assertEqual("independent", freed.json()["decision"]["review_mode"])

        # 7. Pausar no borra decisiones y deja de aplicar; reanudar y retirar.
        paused = self.post(REVIEWER, f"rules/{rule['rule_id']}/status",
                           {"action": "pause"})
        self.assertEqual("paused", paused.json()["status"])
        quiet = self.post(PREPARER, "rules/apply", query)
        self.assertNotIn(rule["rule_id"], {
            item["rule_id"] for item in
            quiet.json()["applied"] + quiet.json()["skipped"]})
        self.assertEqual("confirmed", self.review(
            next(item["candidate_id"] for item in result["applied"]
                 if item["candidate_id"] != l5["candidate_id"]))["status"])
        resumed = self.post(REVIEWER, f"rules/{rule['rule_id']}/status",
                            {"action": "resume"})
        self.assertEqual("active", resumed.json()["status"])
        retired = self.post(REVIEWER, f"rules/{rule['rule_id']}/status",
                            {"action": "retire"})
        self.assertEqual("retired", retired.json()["status"])
        again = self.post(REVIEWER, f"rules/{rule['rule_id']}/status",
                          {"action": "resume"})
        self.assertEqual(409, again.status_code, again.text)
        listed = self.client.get(
            f"/api/v1/companies/{ESPIGA}/reconciliation/rules",
            headers=self.auth(REVIEWER), params={"status": "retired"})
        self.assertIn(rule["rule_id"], {item["rule_id"] for item in listed.json()})
        self.assertEqual(2, retired.json()["applied_count"])
        self.assertEqual(1, retired.json()["reverted_count"])

        # 8. Otra empresa no ve la regla.
        foreign = self.client.get(
            f"/api/v1/companies/{ESPIGA}/reconciliation/rules/{rule['rule_id']}",
            headers=self.auth(AUDITOR_ANDINOS))
        self.assertEqual(403, foreign.status_code, foreign.text)

    def test_smb004_unmatched_summary_and_reports_honour_reversals(self) -> None:
        world = self.build()
        query, pairs = world["query"], world["pairs"]
        base = f"/api/v1/companies/{ESPIGA}"

        def unmatched(user: str = PREPARER) -> set[str]:
            response = self.client.get(
                f"{base}/reconciliation/unmatched", headers=self.auth(user),
                params={"left_dataset_id": query["left_dataset_id"],
                        "right_dataset_id": query["right_dataset_id"],
                        "limit": 200})
            self.assertEqual(200, response.status_code, response.text)
            body = response.json()
            self.assertEqual("none", body["financial_effect"])
            self.assertEqual(body["total"], len(body["items"]))
            return {item["movement_id"] for item in body["items"]}

        def report() -> dict:
            response = self.client.get(
                f"{base}/reports/operational", headers=self.auth(OWNER),
                params={"days": 30})
            self.assertEqual(200, response.status_code, response.text)
            return response.json()["summary"]["reconciliation"]

        def summary() -> dict:
            response = self.client.get(
                f"{base}/reconciliation/summary", headers=self.auth(PREPARER),
                params={"period_start": "2026-02-01", "period_end": "2026-02-28"})
            self.assertEqual(200, response.status_code, response.text)
            return response.json()

        l5, r5 = (pairs[("L5", "R5")]["left"]["movement_id"],
                  pairs[("L5", "R5")]["right"]["movement_id"])
        everything = unmatched()
        self.assertEqual(10, len(everything))
        self.assertIn(l5, everything)

        rule = self.post(PREPARER, "rules", {
            "conditions": self.conditions(world["right_account"])}).json()
        self.assertEqual(200, self.post(REVIEWER, f"rules/{rule['rule_id']}/approval")
                         .status_code)
        applied = self.post(PREPARER, "rules/apply", query)
        self.assertEqual(200, applied.status_code, applied.text)
        decision = next(item for item in applied.json()["applied"]
                        if item["left_movement_id"] == l5)
        after_apply = unmatched()
        self.assertNotIn(l5, after_apply)
        self.assertNotIn(r5, after_apply)
        before_revert_report = report()
        before_revert_summary = summary()

        reverted = self.post(PREPARER, f"decisions/{decision['decision_id']}/reversal",
                             {"reason_code": "rule_too_broad"})
        self.assertEqual(200, reverted.status_code, reverted.text)

        # La reversion devuelve ambos movimientos a «sin cruzar».
        after_revert = unmatched()
        self.assertIn(l5, after_revert)
        self.assertIn(r5, after_revert)
        # El informe ya no cuenta la aplicacion revertida como confirmada.
        after_revert_report = report()
        self.assertEqual(before_revert_report["confirmed"] - 1,
                         after_revert_report["confirmed"])
        self.assertEqual(before_revert_report["reverted"] + 1,
                         after_revert_report["reverted"])
        after_revert_summary = summary()
        self.assertEqual(before_revert_summary["matched"] - 2,
                         after_revert_summary["matched"])
        for value in after_revert_summary.values():
            self.assertNotIsInstance(value, float)
        self.post(REVIEWER, f"rules/{rule['rule_id']}/status", {"action": "retire"})

        # Fuera de alcance: otra empresa y un par no elegible responden igual.
        foreign = self.client.get(
            f"/api/v1/companies/{stable_id('company', 'andinos')}/reconciliation/"
            "unmatched", headers=self.auth(AUDITOR_ANDINOS),
            params={"left_dataset_id": query["left_dataset_id"],
                    "right_dataset_id": query["right_dataset_id"]})
        self.assertEqual(403, foreign.status_code, foreign.text)
        invalid = self.client.get(
            f"{base}/reconciliation/unmatched", headers=self.auth(PREPARER),
            params={"left_dataset_id": query["left_dataset_id"],
                    "right_dataset_id": query["right_dataset_id"], "limit": 500})
        self.assertEqual(422, invalid.status_code, invalid.text)

    def test_smb003_simple_profile_lets_the_owner_approve_alone(self) -> None:
        world = self.build()
        try:
            switched = self.client.put(
                f"/api/v1/companies/{ESPIGA}/operating-profile",
                headers=self.auth(OWNER),
                json={"operating_profile": "simple", "reason": REASON})
            self.assertEqual(200, switched.status_code, switched.text)
            created = self.post(OWNER, "rules", {
                "conditions": self.conditions(world["right_account"])})
            self.assertEqual(201, created.status_code, created.text)
            approved = self.post(OWNER, f"rules/{created.json()['rule_id']}/approval")
            self.assertEqual(200, approved.status_code, approved.text)
            self.assertEqual("self_reviewed", approved.json()["approval"]["review_mode"])
            applied = self.post(OWNER, "rules/apply", world["query"])
            self.assertEqual(200, applied.status_code, applied.text)
            self.assertTrue(applied.json()["applied"])
            for item in applied.json()["applied"]:
                self.assertEqual(OWNER_ID, item["decided_by"])
            self.post(OWNER, f"rules/{created.json()['rule_id']}/status",
                      {"action": "retire"})
        finally:
            force_profile(ESPIGA, "estricto")

    def test_smb003_database_refuses_forged_rule_decisions(self) -> None:
        world = self.build()
        query, pairs = world["query"], world["pairs"]
        open_candidate = self.propose(query, pairs[("L3", "R3")])
        proposed_rule = self.post(PREPARER, "rules", {
            "conditions": self.conditions(world["right_account"])}).json()
        active_rule = self.post(PREPARER, "rules", {
            "conditions": self.conditions(world["right_account"],
                                          description_contains="abono nit")}).json()
        approved = self.post(REVIEWER, f"rules/{active_rule['rule_id']}/approval")
        self.assertEqual(200, approved.status_code, approved.text)

        def forge(cursor, *, rule_id, version, decided_by, mode="approved_rule",
                  reason="approved_rule_match", candidate=open_candidate):
            cursor.execute(
                "SELECT left_movement_id, right_movement_id FROM fincilia.match_candidate "
                "WHERE candidate_id = %s", (candidate,))
            left, right = (str(value) for value in cursor.fetchone())
            audit_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO fincilia.audit_event (audit_event_id, company_id, "
                "subject_id, action, resource_kind, resource_ref, outcome) VALUES "
                "(%s, %s, %s, 'match.rule.apply', 'match_candidate', 'smb003', "
                "'allowed')", (audit_id, ESPIGA, decided_by))
            cursor.execute(
                "INSERT INTO fincilia.match_decision (company_id, candidate_id, "
                "decision, reason_code, evidence_refs, decided_by, audit_event_id, "
                "review_mode, rule_id, rule_version) VALUES "
                "(%s, %s, 'confirmed', %s, %s::jsonb, %s, %s, %s, %s, %s)",
                (ESPIGA, candidate, reason, json.dumps([
                    {"kind": "movement", "ref": left},
                    {"kind": "movement", "ref": right}]), decided_by, audit_id, mode,
                 rule_id, version))

        cases = (
            ("no rule at all", dict(rule_id=None, version=None, decided_by=REVIEWER_ID),
             psycopg.errors.CheckViolation),
            ("rule not approved", dict(rule_id=proposed_rule["rule_id"], version=1,
                                       decided_by=REVIEWER_ID),
             psycopg.errors.CheckViolation),
            ("wrong version", dict(rule_id=active_rule["rule_id"], version=2,
                                   decided_by=REVIEWER_ID),
             psycopg.errors.CheckViolation),
            ("decider is not the approver", dict(rule_id=active_rule["rule_id"],
                                                 version=1, decided_by=OWNER_ID),
             psycopg.errors.CheckViolation),
            ("independent mode naming a rule", dict(rule_id=active_rule["rule_id"],
                                                    version=1, decided_by=REVIEWER_ID,
                                                    mode="independent"),
             psycopg.errors.CheckViolation),
        )
        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                for label, kwargs, error in cases:
                    with self.subTest(case=label):
                        with self.assertRaises(error):
                            with connection.transaction():
                                forge(cursor, **kwargs)
                # En `estricto` la base rechaza la autoaprobacion aunque se evite la API.
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with connection.transaction():
                        cursor.execute(
                            "INSERT INTO fincilia.audit_event (audit_event_id, "
                            "company_id, subject_id, action, resource_kind, "
                            "resource_ref, outcome) VALUES (%s, %s, %s, "
                            "'match.rule.approve', 'reconciliation_rule', 'x', "
                            "'allowed') RETURNING audit_event_id",
                            (str(uuid.uuid4()), ESPIGA, PREPARER_ID))
                        audit_id = str(cursor.fetchone()[0])
                        cursor.execute(
                            "INSERT INTO fincilia.reconciliation_rule_approval "
                            "(company_id, rule_id, approved_by, audit_event_id) "
                            "VALUES (%s, %s, %s, %s)",
                            (ESPIGA, proposed_rule["rule_id"], PREPARER_ID, audit_id))
            connection.rollback()

        # Historial append-only y aislamiento por empresa con el rol runtime.
        with psycopg.connect(RUNTIME_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                               (stable_id("company", "andinos"),))
                cursor.execute(
                    "SELECT count(*) FROM fincilia.reconciliation_rule WHERE rule_id = %s",
                    (active_rule["rule_id"],))
                self.assertEqual(0, cursor.fetchone()[0])
                cursor.execute("SELECT set_config('fincilia.company_id', %s, true)",
                               (ESPIGA,))
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cursor.execute(
                        "UPDATE fincilia.reconciliation_rule SET version = 2 "
                        "WHERE rule_id = %s", (active_rule["rule_id"],))
            connection.rollback()

    def test_smb003_rules_never_touch_unverified_sources(self) -> None:
        world = self.build()
        m = uuid.uuid4().hex[:8]
        broken = self.dataset([
            ("17/02/2026", f"Pago NIT FNC-SYN-NIT-0007 roto {m}", f"LX-{m}", "-50.000,00"),
            ("18/02/2026", f"Fila rota {m}", f"LY-{m}", "no-es-un-valor"),
        ], marker=f"rule-broken-{m}", source=rec.SOURCE, account=rec.ACCOUNT)
        rule = self.post(PREPARER, "rules", {
            "conditions": self.conditions(world["right_account"])}).json()
        self.assertEqual(200, self.post(REVIEWER, f"rules/{rule['rule_id']}/approval")
                         .status_code)
        refused = self.post(PREPARER, "rules/apply", {
            "left_dataset_id": broken,
            "right_dataset_id": world["query"]["right_dataset_id"], "max_days": 3})
        self.assertEqual(403, refused.status_code, refused.text)

        # Ni forzando un candidato por SQL la base deja aplicar la regla.
        with psycopg.connect(MIGRATOR_DSN) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('fincilia.company_id', %s, false)",
                               (ESPIGA,))
                cursor.execute(
                    "SELECT d.completeness_state, m.movement_id, m.engine_release_id, "
                    "       m.canonical_schema_version "
                    "FROM fincilia.canonical_movement m "
                    "JOIN fincilia.dataset_version d "
                    "  ON d.dataset_version_id = m.dataset_version_id "
                    "WHERE m.dataset_version_id = %s", (broken,))
                completeness, left_movement, release_id, schema = cursor.fetchone()
                self.assertEqual("mismatch", completeness)
                right_movement = world["pairs"][("L5", "R5")]["right"]["movement_id"]
                low, high = sorted((str(left_movement), right_movement))
                audit_id = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO fincilia.audit_event (audit_event_id, company_id, "
                    "subject_id, action, resource_kind, resource_ref, outcome) VALUES "
                    "(%s, %s, %s, 'match.propose', 'match_candidate', 'smb003', "
                    "'allowed')", (audit_id, ESPIGA, PREPARER_ID))
                cursor.execute(
                    "INSERT INTO fincilia.match_candidate (company_id, left_movement_id, "
                    "right_movement_id, rule_version, signals, date_window_days, "
                    "date_distance_days, engine_release_ids, canonical_schema_versions, "
                    "proposed_by, audit_event_id) VALUES (%s, %s, %s, 'smb003-partial', "
                    "%s, 3, 0, %s::uuid[], %s, %s, %s) RETURNING candidate_id",
                    (ESPIGA, low, high,
                     ["exact_amount", "same_currency", "opposite_direction",
                      "different_financial_account", "date_within_explicit_window"],
                     [str(release_id)], [schema], PREPARER_ID, audit_id))
                candidate_id = str(cursor.fetchone()[0])
                decision_audit = str(uuid.uuid4())
                cursor.execute(
                    "INSERT INTO fincilia.audit_event (audit_event_id, company_id, "
                    "subject_id, action, resource_kind, resource_ref, outcome) VALUES "
                    "(%s, %s, %s, 'match.rule.apply', 'match_candidate', 'smb003', "
                    "'allowed')", (decision_audit, ESPIGA, REVIEWER_ID))
                with self.assertRaises(psycopg.errors.CheckViolation) as raised:
                    cursor.execute(
                        "INSERT INTO fincilia.match_decision (company_id, candidate_id, "
                        "decision, reason_code, evidence_refs, decided_by, "
                        "audit_event_id, review_mode, rule_id, rule_version) VALUES "
                        "(%s, %s, 'confirmed', 'approved_rule_match', %s::jsonb, %s, "
                        "%s, 'approved_rule', %s, 1)",
                        (ESPIGA, candidate_id, json.dumps([
                            {"kind": "movement", "ref": low},
                            {"kind": "movement", "ref": high}]), REVIEWER_ID,
                         decision_audit, rule["rule_id"]))
                self.assertEqual("ck_match_decision_rule_eligible",
                                 raised.exception.diag.constraint_name)
            connection.rollback()


if __name__ == "__main__":
    import unittest
    unittest.main()
