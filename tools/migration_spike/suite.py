"""Los doce invariantes del spike de migraciones (FNC-DB-002).

Tres de ellos son estaticos y no necesitan base de datos: el plan canonico, el
rechazo de una migracion desconocida y el alcance de la limpieza. Se ejecutan
siempre, tambien cuando no hay runtime de contenedores, porque no dependen de el.

Los nueve restantes exigen PostgreSQL real. Si no hay runtime **no se simulan**:
quedan `not_executed` y el handoff queda `PARTIAL`. Un resultado inventado seria
peor que ninguno.

Regla de veredicto: un caso que espera fallo no se da por bueno con un exit
distinto de cero cualquiera. Tiene que fallar por el marcador declarado. Un
timeout, una excepcion o una salida truncada nunca cuentan como aprobado.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from tools.migration_spike.manifest import plan, plan_digest, validate_manifest
from tools.migration_spike.runner import CaseResult, Execution, SpikeLab, SpikeRunnerError

COMPANY_A = "company-alpha-synthetic"
COMPANY_B = "company-beta-synthetic"

STATIC_CASE_IDS = ("DBS-CHECKSUM-ORDER", "DBS-UNKNOWN-MIGRATION", "DBS-CLEANUP-SCOPE")

CASE_CATALOGUE: tuple[dict[str, str], ...] = (
    {"case_id": "DBS-BLANK", "invariant": "blank_database_to_head",
     "expectation": "una base vacia llega al estado esperado y registra tres migraciones",
     "kind": "runtime", "matrix_ref": "DBS-01"},
    {"case_id": "DBS-REPLAY", "invariant": "replay_head_is_noop",
     "expectation": "una segunda ejecucion no aplica nada y no duplica historial",
     "kind": "runtime", "matrix_ref": "DBS-02"},
    {"case_id": "DBS-TAMPER", "invariant": "modified_applied_file_fails_checksum",
     "expectation": "editar una migracion ya aplicada aborta por checksum antes de ejecutar",
     "kind": "runtime", "matrix_ref": "DBS-04"},
    {"case_id": "DBS-PARTIAL-FAILURE", "invariant": "failed_migration_leaves_nothing",
     "expectation": "un error a mitad no deja objetos parciales ni fila de historial",
     "kind": "runtime", "matrix_ref": "DBS-07"},
    {"case_id": "DBS-PRIVILEGES", "invariant": "separated_roles_without_privilege",
     "expectation": "migrator y runtime no son superuser, bypassrls, createdb ni createrole "
                    "y el runtime no es propietario",
     "kind": "runtime", "matrix_ref": "DBS-06"},
    {"case_id": "DBS-RUNTIME-DENIAL", "invariant": "runtime_cannot_migrate",
     "expectation": "el runtime no crea, altera ni borra objetos y no escribe historial",
     "kind": "runtime", "matrix_ref": "DBS-06"},
    {"case_id": "DBS-RLS", "invariant": "company_isolation_fails_closed",
     "expectation": "A no lee ni escribe B, y sin contexto de compania no se ve ni se escribe nada",
     "kind": "runtime", "matrix_ref": "DBS-06"},
    {"case_id": "DBS-FORCE-RLS", "invariant": "force_row_level_security_preserved",
     "expectation": "la tabla sensible conserva RLS habilitada y forzada, con politica",
     "kind": "runtime", "matrix_ref": "DBS-06"},
    {"case_id": "DBS-CONCURRENCY", "invariant": "two_migrators_do_not_race",
     "expectation": "dos migradores concurrentes producen una sola aplicacion por version",
     "kind": "runtime", "matrix_ref": "DBS-05"},
    {"case_id": "DBS-CHECKSUM-ORDER", "invariant": "plan_is_independent_of_directory_order",
     "expectation": "barajar el manifiesto no cambia el plan canonico ni su digest",
     "kind": "static", "matrix_ref": "DBS-04"},
    {"case_id": "DBS-UNKNOWN-MIGRATION", "invariant": "duplicate_or_gapped_version_refused",
     "expectation": "una version duplicada, un hueco o un fichero no manifestado se rechazan",
     "kind": "static", "matrix_ref": "DBS-01"},
    {"case_id": "DBS-CLEANUP-SCOPE", "invariant": "cleanup_never_targets_another_project",
     "expectation": "todo argv apunta al proyecto del spike y a su propio fichero de Compose",
     "kind": "static", "matrix_ref": "DBS-05"},
)


def _catalogue(case_id: str) -> dict[str, str]:
    return next(item for item in CASE_CATALOGUE if item["case_id"] == case_id)


def _result(case_id: str, outcome: str, detail: str,
            executions: list[Execution] | None = None) -> CaseResult:
    entry = _catalogue(case_id)
    return CaseResult(case_id, entry["invariant"], entry["expectation"], outcome, detail,
                      executions or [])


def _expect_success(case_id: str, executions: list[Execution], marker: str) -> CaseResult:
    for execution in executions:
        if execution.status != "completed":
            return _result(case_id, "error",
                           f"{execution.status}: the outcome is unknown", executions)
        if execution.truncated:
            return _result(case_id, "error", "output truncated; cannot be evaluated",
                           executions)
        if execution.exit_code != 0:
            return _result(case_id, "fail",
                           f"exit {execution.exit_code}: "
                           f"{(execution.stderr or execution.stdout).strip()[-300:]}",
                           executions)
    combined = "\n".join(item.stdout + item.stderr for item in executions)
    if marker and marker not in combined:
        return _result(case_id, "fail",
                       f"the run succeeded but never emitted {marker!r}", executions)
    return _result(case_id, "pass", f"observed {marker}" if marker else "completed",
                   executions)


def _expect_failure(case_id: str, execution: Execution, marker: str) -> CaseResult:
    if execution.status != "completed":
        return _result(case_id, "error", f"{execution.status}: the outcome is unknown",
                       [execution])
    if execution.truncated:
        return _result(case_id, "error", "output truncated; cannot be evaluated", [execution])
    if execution.exit_code == 0:
        return _result(case_id, "fail",
                       "the database accepted an operation that must be denied", [execution])
    combined = execution.stdout + execution.stderr
    if marker not in combined:
        return _result(case_id, "fail",
                       f"it failed, but not for the declared reason: expected {marker!r}, "
                       f"got {combined.strip()[-300:]}", [execution])
    return _result(case_id, "pass", f"denied with {marker}", [execution])


# --------------------------------------------------------------------------- #
# Casos estaticos
# --------------------------------------------------------------------------- #

def case_checksum_order(manifest: dict[str, Any]) -> CaseResult:
    shuffled = copy.deepcopy(manifest)
    shuffled["migrations"] = list(reversed(shuffled.get("migrations", [])))
    original, reordered = plan(manifest), plan(shuffled)
    if original != reordered or plan_digest(original) != plan_digest(reordered):
        return _result("DBS-CHECKSUM-ORDER", "fail",
                       "reversing the manifest changed the canonical plan")
    if [step["version"] for step in original] != sorted(
            step["version"] for step in original):
        return _result("DBS-CHECKSUM-ORDER", "fail", "the plan is not ordered by version")
    return _result("DBS-CHECKSUM-ORDER", "pass",
                   f"plan digest stable at {plan_digest(original)[:16]}")


def case_unknown_migration(manifest: dict[str, Any], spike_root: Path) -> CaseResult:
    checks: list[tuple[str, dict[str, Any], str]] = []

    duplicate = copy.deepcopy(manifest)
    if duplicate.get("migrations"):
        duplicate["migrations"].append(copy.deepcopy(duplicate["migrations"][0]))
    checks.append(("duplicate version", duplicate, "MSP-VERSION-DUPLICATE"))

    gapped = copy.deepcopy(manifest)
    if len(gapped.get("migrations", [])) > 1:
        gapped["migrations"].pop(1)
    checks.append(("version gap", gapped, "MSP-VERSION-GAP"))

    unmanifested = copy.deepcopy(manifest)
    unmanifested["migrations"] = unmanifested.get("migrations", [])[:-1]
    checks.append(("unmanifested file", unmanifested, "MSP-FILE-NOT-MANIFESTED"))

    outside = copy.deepcopy(manifest)
    if outside.get("migrations"):
        outside["migrations"][0] = {**outside["migrations"][0],
                                    "path": "../outside/V0001__escape.sql"}
    checks.append(("path escaping the spike", outside, "MSP-PATH-UNSAFE"))

    tampered = copy.deepcopy(manifest)
    if tampered.get("migrations"):
        tampered["migrations"][0] = {**tampered["migrations"][0], "sha256": "0" * 64}
    checks.append(("checksum drift", tampered, "MSP-CHECKSUM"))

    missed: list[str] = []
    for label, candidate, expected in checks:
        codes = {finding.code for finding in validate_manifest(candidate, spike_root)}
        if expected not in codes:
            missed.append(f"{label} was not refused with {expected}")
    if missed:
        return _result("DBS-UNKNOWN-MIGRATION", "fail", "; ".join(missed))
    return _result("DBS-UNKNOWN-MIGRATION", "pass",
                   f"{len(checks)} malformed plans refused with their own code")


def case_cleanup_scope(lab: SpikeLab | None, spike_root: Path,
                       adapter: dict[str, Any] | None) -> CaseResult:
    """El alcance de la limpieza se comprueba sobre el argv, no sobre el efecto."""
    if lab is None:
        probe_adapter_value = adapter or dict(
            id="static", prefix=("docker",), probe=(), translate_paths=False)
        try:
            lab = SpikeLab(probe_adapter_value, spike_root)
        except SpikeRunnerError as error:
            return _result("DBS-CLEANUP-SCOPE", "error", str(error))

    problems: list[str] = []
    for arguments in (("down", "--volumes", "--remove-orphans"), ("up", "-d", "--wait"),
                      ("config", "--quiet")):
        argv = lab.compose_argv(*arguments)
        if "-p" not in argv or argv[argv.index("-p") + 1] != "fincilia-db-spike":
            problems.append(f"{arguments[0]} does not pin the spike project")
        compose_index = argv.index("-f") + 1
        if not argv[compose_index].endswith("spikes/FNC-DB-002/compose.yaml"):
            problems.append(f"{arguments[0]} does not use the spike compose file")
        if any(token in ("*", "--all") for token in argv):
            problems.append(f"{arguments[0]} uses a wildcard")

    try:
        SpikeLab(lab.adapter, spike_root, project="fincilia-local")
        problems.append("the runner accepted a foreign compose project")
    except SpikeRunnerError:
        pass

    try:
        lab.container_script("../../etc/passwd")
        problems.append("the runner accepted a script path outside sql/")
    except SpikeRunnerError:
        pass

    if problems:
        return _result("DBS-CLEANUP-SCOPE", "fail", "; ".join(problems))
    return _result("DBS-CLEANUP-SCOPE", "pass",
                   "every argv pins project fincilia-db-spike and the spike compose file")


def static_cases(manifest: dict[str, Any], spike_root: Path,
                 lab: SpikeLab | None = None,
                 adapter: dict[str, Any] | None = None) -> list[CaseResult]:
    return [
        case_checksum_order(manifest),
        case_unknown_migration(manifest, spike_root),
        case_cleanup_scope(lab, spike_root, adapter),
    ]


# --------------------------------------------------------------------------- #
# Casos con PostgreSQL real
# --------------------------------------------------------------------------- #

def runtime_cases(lab: SpikeLab, manifest: dict[str, Any]) -> list[CaseResult]:
    steps = plan(manifest)
    results: list[CaseResult] = []

    # ---- Ciclo 1: base en blanco ------------------------------------- #
    lifecycle = lab.up(fresh=True)
    if any(item.status != "completed" or item.exit_code != 0 for item in lifecycle):
        detail = "; ".join(f"{item.status}/{item.exit_code}" for item in lifecycle)
        return [_result(entry["case_id"], "error",
                        f"the laboratory did not start ({detail})", lifecycle)
                for entry in CASE_CATALOGUE if entry["kind"] == "runtime"]

    applied = [lab.apply_step(step) for step in steps]
    head = lab.run_case("sql/cases/probe_head_state.sql", "fnc_spike_migrator")
    results.append(_expect_success("DBS-BLANK", applied + [head], "FNC_SPIKE_OK head_state"))

    # ---- Replay: idempotencia ---------------------------------------- #
    replayed = [lab.apply_step(step) for step in steps]
    count = lab.run_case("sql/cases/probe_history_count.sql", "fnc_spike_migrator")
    replay_result = _expect_success("DBS-REPLAY", replayed + [count],
                                    "FNC_SPIKE_OK history_count")
    if replay_result.outcome == "pass":
        combined = "\n".join(item.stdout + item.stderr for item in replayed)
        if "FNC_SPIKE_APPLYING" in combined:
            replay_result = _result("DBS-REPLAY", "fail",
                                    "the replay re-applied a migration instead of skipping it",
                                    replayed)
        elif combined.count("FNC_SPIKE_ALREADY_APPLIED") < len(steps):
            replay_result = _result("DBS-REPLAY", "fail",
                                    "not every step reported that it was already applied",
                                    replayed)
    results.append(replay_result)

    # ---- Tamper: fichero aplicado y editado --------------------------- #
    tampered_entry = next((item for item in manifest.get("tampered", []) or []
                           if item.get("path", "").endswith(".sql")), None)
    if tampered_entry is None:
        results.append(_result("DBS-TAMPER", "error", "no tampered fixture is manifested"))
    else:
        first = steps[0]
        tamper = lab.apply_step(first, override_path=tampered_entry["path"],
                                override_checksum=tampered_entry["sha256"])
        results.append(_expect_failure("DBS-TAMPER", tamper, "FNC_SPIKE_CHECKSUM_MISMATCH"))

    # ---- Fallo parcial ------------------------------------------------ #
    failing_entry = next((item for item in manifest.get("failing", []) or []
                          if item.get("path", "").endswith(".sql")), None)
    if failing_entry is None:
        results.append(_result("DBS-PARTIAL-FAILURE", "error",
                               "no failing fixture is manifested"))
    else:
        failing_step = {"version": "V0009", "name": "partial_failure",
                        "path": failing_entry["path"], "sha256": failing_entry["sha256"]}
        broken = lab.apply_step(failing_step)
        verdict = _expect_failure("DBS-PARTIAL-FAILURE", broken,
                                  "FNC_SPIKE_DELIBERATE_FAILURE")
        if verdict.outcome == "pass":
            residue = lab.run_case("sql/cases/probe_no_partial_artifact.sql",
                                   "fnc_spike_migrator")
            verdict = _expect_success("DBS-PARTIAL-FAILURE", [residue],
                                      "FNC_SPIKE_OK no_partial_artifact")
            verdict.executions.insert(0, broken)
        results.append(verdict)

    # ---- Privilegios --------------------------------------------------- #
    privileges = lab.run_case("sql/cases/probe_privileges.sql", "fnc_spike_bootstrap")
    results.append(_expect_success("DBS-PRIVILEGES", [privileges], "FNC_SPIKE_OK privileges"))

    # ---- FORCE RLS ----------------------------------------------------- #
    force = lab.run_case("sql/cases/probe_force_rls.sql", "fnc_spike_bootstrap")
    results.append(_expect_success("DBS-FORCE-RLS", [force], "FNC_SPIKE_OK force_rls"))

    # ---- Denegacion al runtime ----------------------------------------- #
    denials = (
        ("sql/cases/deny_runtime_create.sql", "permission denied for schema spike"),
        ("sql/cases/deny_runtime_alter.sql", "must be owner of table company_ledger"),
        ("sql/cases/deny_runtime_drop.sql", "must be owner of table company_ledger"),
        ("sql/cases/deny_runtime_history_write.sql", "permission denied for table schema_history"),
        ("sql/cases/deny_runtime_history_update.sql", "permission denied for table schema_history"),
    )
    denial_results = [_expect_failure("DBS-RUNTIME-DENIAL",
                                      lab.run_case(script, "fnc_spike_runtime"), marker)
                      for script, marker in denials]
    readable = lab.run_case("sql/cases/probe_runtime_read_history.sql", "fnc_spike_runtime")
    read_result = _expect_success("DBS-RUNTIME-DENIAL", [readable],
                                  "FNC_SPIKE_OK runtime_reads_history")
    failed = [item for item in denial_results + [read_result] if item.outcome != "pass"]
    if failed:
        results.append(_result("DBS-RUNTIME-DENIAL", failed[0].outcome,
                               "; ".join(item.detail for item in failed),
                               [execution for item in failed for execution in item.executions]))
    else:
        results.append(_result("DBS-RUNTIME-DENIAL", "pass",
                               f"{len(denials)} write paths denied, read path preserved",
                               [item.executions[0] for item in denial_results]))

    # ---- Aislamiento por compania -------------------------------------- #
    rls_steps: list[CaseResult] = []
    for company in (COMPANY_A, COMPANY_B):
        seeded = lab.run_case("sql/cases/probe_rls_seed.sql", "fnc_spike_runtime",
                              {"company": company})
        rls_steps.append(_expect_success("DBS-RLS", [seeded], "FNC_SPIKE_OK seed"))
    for company in (COMPANY_A, COMPANY_B):
        read = lab.run_case("sql/cases/probe_rls_read.sql", "fnc_spike_runtime",
                            {"company": company})
        rls_steps.append(_expect_success("DBS-RLS", [read], "FNC_SPIKE_OK rls_read"))
    cross = lab.run_case("sql/cases/deny_rls_cross_company.sql", "fnc_spike_runtime",
                         {"company": COMPANY_A, "other": COMPANY_B})
    rls_steps.append(_expect_failure("DBS-RLS", cross, "row-level security policy"))
    no_context = lab.run_case("sql/cases/deny_rls_missing_context.sql", "fnc_spike_runtime")
    rls_steps.append(_expect_failure("DBS-RLS", no_context, "row-level security policy"))

    broken_rls = [item for item in rls_steps if item.outcome != "pass"]
    if broken_rls:
        results.append(_result("DBS-RLS", broken_rls[0].outcome,
                               "; ".join(item.detail for item in broken_rls),
                               [execution for item in broken_rls
                                for execution in item.executions]))
    else:
        results.append(_result("DBS-RLS", "pass",
                               "two companies isolated, cross-company write denied and "
                               "missing context fails closed",
                               [item.executions[0] for item in rls_steps]))

    # ---- Ciclo 2: concurrencia sobre una base limpia -------------------- #
    restart = lab.up(fresh=True)
    if any(item.status != "completed" or item.exit_code != 0 for item in restart):
        results.append(_result("DBS-CONCURRENCY", "error",
                               "the laboratory could not be recreated for the race",
                               restart))
        return results

    # Dos migradores compiten por la MISMA version antes de pasar a la siguiente.
    # Lanzar las tres versiones a la vez no seria una carrera: seria desordenar el
    # plan, y V0002 fallaria legitimamente porque V0001 aun no ha commiteado.
    race: list[Execution] = []
    for step in steps:
        contenders = [lab.apply_step_async(step), lab.apply_step_async(step)]
        for process in contenders:
            out, err = process.communicate(timeout=180)
            race.append(Execution(tuple(process.args), process.returncode,
                                  out.decode("utf-8", "replace"),
                                  err.decode("utf-8", "replace"), False, "completed"))
    history = lab.run_case("sql/cases/probe_history_count.sql", "fnc_spike_migrator")
    if any(item.exit_code != 0 for item in race):
        broken = next(item for item in race if item.exit_code != 0)
        results.append(_result("DBS-CONCURRENCY", "fail",
                               f"a racing migrator failed: "
                               f"{(broken.stderr or broken.stdout).strip()[-300:]}", race))
    else:
        verdict = _expect_success("DBS-CONCURRENCY", [history],
                                  "FNC_SPIKE_OK history_count")
        combined = "\n".join(item.stdout + item.stderr for item in race)
        applications = combined.count("FNC_SPIKE_APPLIED")
        contended = combined.count("FNC_SPIKE_ALREADY_APPLIED")
        if verdict.outcome == "pass" and applications != len(steps):
            verdict = _result("DBS-CONCURRENCY", "fail",
                              f"{applications} applications for {len(steps)} versions; "
                              "the lock did not serialise the migrators", race)
        elif verdict.outcome == "pass" and contended != len(steps):
            # Si el segundo migrador nunca encontro la version ya aplicada, no hubo
            # contienda y el caso no habria probado nada.
            verdict = _result("DBS-CONCURRENCY", "fail",
                              f"only {contended} of {len(steps)} contenders found the work "
                              "already done; there was no real race to serialise", race)
        elif verdict.outcome == "pass":
            verdict = _result("DBS-CONCURRENCY", "pass",
                              f"{len(steps)} versions, {applications} applications and "
                              f"{contended} contenders that found the work already done",
                              race)
        results.append(verdict)

    return results
