"""FNC-BIL-002 contra PostgreSQL real, siempre con referencias sinteticas.

Stripe se reemplaza en la frontera HTTP, pero este archivo no reemplaza la
base: ejercita el rol LOGIN de la aplicacion, RLS, funciones SECURITY DEFINER,
idempotencia concurrente y el ledger append-only que materializa el webhook.
"""

from __future__ import annotations

import concurrent.futures
import datetime as dt
import time
import unittest
import uuid
from contextlib import contextmanager

import psycopg

from db.seed.local import DEFAULT_SECRET, seed, stable_id
from db.tests.test_api_authorization import MIGRATOR_DSN, RUNTIME_DSN
from fincilia_api import billing


FIRM = stable_id("firm", "andes")
SOFIA = stable_id("subject", "sofia")
BETO = stable_id("subject", "beto")
PLAN_VERSION = "b2000000-0000-4000-8000-000000000002"
PRICE = "price_FNCBIL002SYNTHETIC"
CUSTOMER = "cus_FNCBIL002SYNTHETIC"
SUBSCRIPTION = "sub_FNCBIL002SYNTHETIC"
EVENT_PREFIX = "evt_FNCBIL002"


def event_id() -> str:
    return EVENT_PREFIX + uuid.uuid4().hex


@contextmanager
def runtime_for(subject_id: str | None = None):
    with psycopg.connect(RUNTIME_DSN) as connection:
        with connection.transaction():
            if subject_id is not None:
                connection.execute(
                    "SELECT set_config('fincilia.subject_id', %s, true)",
                    (subject_id,),
                )
            yield connection


class StripeBillingDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not MIGRATOR_DSN or not RUNTIME_DSN:
            raise unittest.SkipTest("migrator and runtime DSNs are required")
        seed(MIGRATOR_DSN, secret=DEFAULT_SECRET)
        cls._clean(remove_catalog=True)
        with psycopg.connect(MIGRATOR_DSN) as connection:
            connection.execute(
                "INSERT INTO fincilia.billing_plan_version ("
                "plan_version_id, plan_code, version, display_name, audience_code, "
                "catalog_state, multi_company_portfolio, team_review_workflows, "
                "advanced_quality_controls, foundational_security, basic_data_export, "
                "max_companies, max_active_members, max_monthly_documents, "
                "max_storage_bytes, currency_code, unit_amount_minor, trial_days) "
                "VALUES (%s, 'business', 99, 'Negocio sintetico', 'growing_team', "
                "'commercial', true, true, true, true, true, 10, 10, 1000, "
                "104857600, 'USD', 4900, 14)",
                (PLAN_VERSION,),
            )
            connection.execute(
                "INSERT INTO fincilia.billing_provider_price ("
                "plan_version_id, external_price_id, configured_by) "
                "VALUES (%s, %s, 'fnc-bil-002-test')",
                (PLAN_VERSION, PRICE),
            )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._clean(remove_catalog=True)

    def setUp(self) -> None:
        self._clean(remove_catalog=False)

    @classmethod
    def _clean(cls, *, remove_catalog: bool) -> None:
        with psycopg.connect(MIGRATOR_DSN) as connection:
            connection.execute(
                "DELETE FROM fincilia.billing_webhook_inbox "
                "WHERE provider_event_id LIKE %s", (EVENT_PREFIX + "%",))
            connection.execute(
                "DELETE FROM fincilia.subscription_event WHERE firm_id = %s", (FIRM,))
            connection.execute(
                "DELETE FROM fincilia.firm_subscription WHERE firm_id = %s", (FIRM,))
            connection.execute(
                "DELETE FROM fincilia.billing_checkout_attempt WHERE firm_id = %s", (FIRM,))
            connection.execute(
                "DELETE FROM fincilia.billing_provider_binding WHERE firm_id = %s", (FIRM,))
            connection.execute(
                "DELETE FROM fincilia.billing_account WHERE firm_id = %s", (FIRM,))
            if remove_catalog:
                connection.execute(
                    "DELETE FROM fincilia.billing_provider_price "
                    "WHERE plan_version_id = %s", (PLAN_VERSION,))
                connection.execute(
                    "DELETE FROM fincilia.billing_plan_version "
                    "WHERE plan_version_id = %s", (PLAN_VERSION,))

    def _ready_checkout(self) -> billing.CheckoutReservation:
        key = str(uuid.uuid4())
        with runtime_for(SOFIA) as connection:
            reservation = billing.reserve_checkout(
                connection, firm_id=FIRM, subject_id=SOFIA,
                plan_code="business", idempotency_key=key)
            replay = billing.reserve_checkout(
                connection, firm_id=FIRM, subject_id=SOFIA,
                plan_code="business", idempotency_key=key)
            self.assertEqual(reservation, replay)
            self.assertEqual(PRICE, reservation.price_id)
            self.assertEqual("reserved", reservation.state)
            self.assertEqual(
                "ready",
                billing.complete_checkout(
                    connection, attempt_id=reservation.attempt_id,
                    subject_id=SOFIA, session_id="cs_test_FNCBIL002SYNTHETIC",
                    expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1),
                ),
            )
            self.assertEqual(
                "replayed",
                billing.complete_checkout(
                    connection, attempt_id=reservation.attempt_id,
                    subject_id=SOFIA, session_id="cs_test_FNCBIL002SYNTHETIC",
                    expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1),
                ),
            )
        return reservation

    def _apply(self, *, provider_event_id: str, status: str = "active",
               subscription_id: str = SUBSCRIPTION,
               payload: bytes = b'{"synthetic":true}') -> str:
        with runtime_for() as connection:
            return billing.apply_verified_subscription(
                connection, event_id=provider_event_id,
                event_type="customer.subscription.updated",
                created=int(time.time()), payload=payload,
                customer_id=CUSTOMER, subscription_id=subscription_id,
                firm_id=FIRM, plan_code="business", price_id=PRICE,
                provider_status=status, trial_end=None,
            )

    def test_checkout_webhook_portal_and_cancellation_are_append_only(self) -> None:
        reservation = self._ready_checkout()
        first_event = event_id()
        self.assertEqual("materialized", self._apply(provider_event_id=first_event))
        self.assertEqual("duplicate", self._apply(provider_event_id=first_event))
        self.assertEqual("unchanged", self._apply(provider_event_id=event_id()))
        self.assertEqual(
            "materialized", self._apply(provider_event_id=event_id(), status="past_due"))
        self.assertEqual(
            "materialized", self._apply(provider_event_id=event_id(), status="canceled"))

        with runtime_for(SOFIA) as connection:
            self.assertEqual(
                CUSTOMER,
                billing.portal_customer(connection, firm_id=FIRM, subject_id=SOFIA),
            )
            overview = billing.read_overview(
                connection, firm_id=FIRM, subject_id=SOFIA,
                payments_enabled=True)
        self.assertEqual("ready", overview["payments_state"])
        self.assertEqual("canceled", overview["subscription"]["status"])
        self.assertEqual(3, overview["subscription"]["sequence"])
        self.assertEqual("payment_provider", overview["subscription"]["source_code"])

        with psycopg.connect(MIGRATOR_DSN) as connection:
            row = connection.execute(
                "SELECT state, external_session_id, session_digest "
                "FROM fincilia.billing_checkout_attempt "
                "WHERE checkout_attempt_id = %s", (reservation.attempt_id,)).fetchone()
            self.assertEqual("consumed", row[0])
            self.assertEqual("cs_test_FNCBIL002SYNTHETIC", row[1])
            self.assertRegex(row[2], r"^[0-9a-f]{64}$")
            binding = connection.execute(
                "SELECT external_customer_id, external_subscription_id, "
                "last_provider_event_digest FROM fincilia.billing_provider_binding "
                "WHERE firm_id = %s", (FIRM,)).fetchone()
            self.assertEqual((CUSTOMER, SUBSCRIPTION), binding[:2])
            self.assertRegex(binding[2], r"^[0-9a-f]{64}$")

    def test_two_concurrent_deliveries_materialize_exactly_once(self) -> None:
        self._ready_checkout()
        shared_event = event_id()

        def deliver(_index: int) -> str:
            return self._apply(provider_event_id=shared_event)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(deliver, range(2)))
        self.assertEqual(["duplicate", "materialized"], sorted(outcomes))
        with psycopg.connect(MIGRATOR_DSN) as connection:
            current = connection.execute(
                "SELECT count(*) FROM fincilia.firm_subscription "
                "WHERE firm_id = %s AND ended_at IS NULL", (FIRM,)).fetchone()[0]
            inbox = connection.execute(
                "SELECT count(*) FROM fincilia.billing_webhook_inbox "
                "WHERE provider_event_id = %s", (shared_event,)).fetchone()[0]
        self.assertEqual((1, 1), (current, inbox))

    def test_two_distinct_concurrent_snapshots_are_serialized_per_firm(self) -> None:
        self._ready_checkout()
        events = (event_id(), event_id())

        def deliver(provider_event_id: str) -> str:
            return self._apply(provider_event_id=provider_event_id)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(deliver, events))
        self.assertEqual(["materialized", "unchanged"], sorted(outcomes))
        with psycopg.connect(MIGRATOR_DSN) as connection:
            current = connection.execute(
                "SELECT count(*) FROM fincilia.firm_subscription "
                "WHERE firm_id = %s AND ended_at IS NULL", (FIRM,)).fetchone()[0]
            inbox = connection.execute(
                "SELECT count(*) FROM fincilia.billing_webhook_inbox "
                "WHERE provider_event_id = ANY(%s)", (list(events),)).fetchone()[0]
        self.assertEqual((1, 2), (current, inbox))

    def test_stale_delete_cannot_cancel_a_newer_provider_subscription(self) -> None:
        self._ready_checkout()
        old_subscription = "sub_FNCBIL002OLD00001"
        new_subscription = "sub_FNCBIL002NEW00001"
        self.assertEqual(
            "materialized",
            self._apply(provider_event_id=event_id(),
                        subscription_id=old_subscription),
        )
        self.assertEqual(
            "unchanged",
            self._apply(provider_event_id=event_id(),
                        subscription_id=new_subscription),
        )
        with runtime_for() as connection:
            stale = billing.apply_verified_subscription(
                connection, event_id=event_id(),
                event_type="customer.subscription.deleted",
                created=int(time.time()), payload=b'{"synthetic":"stale-delete"}',
                customer_id=CUSTOMER, subscription_id=old_subscription,
                firm_id=FIRM, plan_code="business", price_id=PRICE,
                provider_status="canceled", trial_end=None,
            )
        self.assertEqual("stale", stale)
        with psycopg.connect(MIGRATOR_DSN) as connection:
            current = connection.execute(
                "SELECT status, sequence FROM fincilia.firm_subscription "
                "WHERE firm_id = %s AND ended_at IS NULL", (FIRM,)).fetchone()
            bound = connection.execute(
                "SELECT external_subscription_id FROM "
                "fincilia.billing_provider_binding WHERE firm_id = %s",
                (FIRM,),
            ).fetchone()[0]
        self.assertEqual(("active", 1), current)
        self.assertEqual(new_subscription, bound)

    def test_same_event_identifier_with_different_payload_is_rejected(self) -> None:
        self._ready_checkout()
        provider_event_id = event_id()
        self.assertEqual(
            "materialized",
            self._apply(provider_event_id=provider_event_id,
                        payload=b'{"synthetic":"first"}'),
        )
        with self.assertRaisesRegex(billing.BillingError,
                                    "billing-webhook-conflict"):
            self._apply(provider_event_id=provider_event_id,
                        payload=b'{"synthetic":"different"}')

    def test_member_spoofing_and_missing_checkout_proof_fail_closed(self) -> None:
        with runtime_for(BETO) as connection:
            with self.assertRaisesRegex(billing.BillingError, "billing-forbidden"):
                billing.reserve_checkout(
                    connection, firm_id=FIRM, subject_id=BETO,
                    plan_code="business", idempotency_key=str(uuid.uuid4()))
        with runtime_for(BETO) as connection:
            with self.assertRaisesRegex(billing.BillingError, "billing-forbidden"):
                billing.reserve_checkout(
                    connection, firm_id=FIRM, subject_id=SOFIA,
                    plan_code="business", idempotency_key=str(uuid.uuid4()))
        with runtime_for() as connection:
            with self.assertRaisesRegex(
                    billing.BillingError, "billing-operation-rejected"):
                billing.apply_verified_subscription(
                    connection, event_id=event_id(),
                    event_type="customer.subscription.created",
                    created=int(time.time()), payload=b'{"synthetic":true}',
                    customer_id=CUSTOMER, subscription_id=SUBSCRIPTION,
                    firm_id=FIRM, plan_code="business", price_id=PRICE,
                    provider_status="active", trial_end=None)

    def test_runtime_cannot_read_or_write_exact_provider_references(self) -> None:
        for table in (
                "billing_provider_price", "billing_provider_binding",
                "billing_checkout_attempt"):
            with self.subTest(table=table), psycopg.connect(RUNTIME_DSN) as connection:
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    connection.execute(f"SELECT * FROM fincilia.{table} LIMIT 1")

        with psycopg.connect(MIGRATOR_DSN) as connection:
            routines = connection.execute(
                "SELECT routine_name FROM information_schema.routine_privileges "
                "WHERE grantee = 'fincilia_app' AND routine_schema = 'fincilia' "
                "AND routine_name LIKE '%stripe%' ORDER BY routine_name"
            ).fetchall()
        self.assertEqual([
            ("apply_stripe_subscription_snapshot",),
            ("complete_stripe_checkout",),
            ("record_stripe_webhook",),
            ("reserve_stripe_checkout",),
            ("stripe_plan_ready",),
            ("stripe_portal_customer",),
        ], routines)

    def test_ignored_event_is_minimal_and_idempotent(self) -> None:
        provider_event_id = event_id()
        with runtime_for() as connection:
            first = billing.record_ignored_webhook(
                connection, event_id=provider_event_id,
                event_type="charge.refunded", created=int(time.time()),
                payload=b'{"synthetic":true}')
            replay = billing.record_ignored_webhook(
                connection, event_id=provider_event_id,
                event_type="charge.refunded", created=int(time.time()),
                payload=b'{"synthetic":true}')
        self.assertEqual(("ignored", "duplicate"), (first, replay))
        with psycopg.connect(MIGRATOR_DSN) as connection:
            row = connection.execute(
                "SELECT processing_state, outcome_code, provider_event_digest, "
                "payload_digest FROM fincilia.billing_webhook_inbox "
                "WHERE provider_event_id = %s", (provider_event_id,)).fetchone()
        self.assertEqual(("ignored", "event_type_not_subscribed"), row[:2])
        self.assertRegex(row[2], r"^[0-9a-f]{64}$")
        self.assertRegex(row[3], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
