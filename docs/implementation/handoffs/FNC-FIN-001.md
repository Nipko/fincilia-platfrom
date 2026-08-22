---
task: FNC-FIN-001
status: REVIEW_PENDING
base_sha: 78155c7
integration_sha: see_git_commit_containing_this_handoff
implementer: Integration Steward
human_acceptance: pending
---
# Handoff FNC-FIN-001

Modelo ejecutable con escenarios Lean/Base/High, TRM oficial fechada, 30% de contingencia,
sensibilidades y liberación por gate. Rango indicativo: COP 2.613–5.772 millones hasta F2.
No es presupuesto aprobado: costos por rol, cotizaciones, caja y capital siguen pendientes.

Comandos: `python -m tools.budget_model.validate` y
`python -m unittest tools.budget_model.test_validate -v`.
