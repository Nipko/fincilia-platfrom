-- FNC-NTF-001: endurecer la privacidad de la bandeja y el contrato de plantilla.
-- La API siempre trabaja por sujeto; RLS replica esa frontera para que una
-- consulta defectuosa no pueda leer o modificar preferencias de un companero.

DROP POLICY notification_preference_isolation
  ON fincilia.notification_preference;
CREATE POLICY notification_preference_isolation ON fincilia.notification_preference
  USING (
    company_id = nullif(current_setting('fincilia.company_id', true), '')::uuid
    AND subject_id = nullif(current_setting('fincilia.subject_id', true), '')::uuid)
  WITH CHECK (
    company_id = nullif(current_setting('fincilia.company_id', true), '')::uuid
    AND subject_id = nullif(current_setting('fincilia.subject_id', true), '')::uuid);

DROP POLICY notification_intent_isolation
  ON fincilia.notification_intent;
CREATE POLICY notification_intent_isolation ON fincilia.notification_intent
  USING (
    company_id = nullif(current_setting('fincilia.company_id', true), '')::uuid
    AND subject_id = nullif(current_setting('fincilia.subject_id', true), '')::uuid)
  WITH CHECK (
    company_id = nullif(current_setting('fincilia.company_id', true), '')::uuid
    AND subject_id = nullif(current_setting('fincilia.subject_id', true), '')::uuid);

DROP POLICY notification_delivery_isolation
  ON fincilia.notification_delivery;
CREATE POLICY notification_delivery_isolation ON fincilia.notification_delivery
  USING (
    company_id = nullif(current_setting('fincilia.company_id', true), '')::uuid
    AND subject_id = nullif(current_setting('fincilia.subject_id', true), '')::uuid)
  WITH CHECK (
    company_id = nullif(current_setting('fincilia.company_id', true), '')::uuid
    AND subject_id = nullif(current_setting('fincilia.subject_id', true), '')::uuid);

-- Una allowlist es mas fuerte que una denylist: ningun campo nuevo entra en un
-- mensaje sin una migracion revisable. Los tres valores son texto minimizado.
ALTER TABLE fincilia.notification_intent
  DROP CONSTRAINT notification_intent_render_context_check;
ALTER TABLE fincilia.notification_intent
  ADD CONSTRAINT ck_notification_intent_render_context_allowlist CHECK (
    jsonb_typeof(render_context) = 'object'
    AND render_context ?& ARRAY['period_label', 'due_on', 'action_url']
    AND render_context - ARRAY['period_label', 'due_on', 'action_url'] = '{}'::jsonb
    AND jsonb_typeof(render_context -> 'period_label') = 'string'
    AND jsonb_typeof(render_context -> 'due_on') = 'string'
    AND jsonb_typeof(render_context -> 'action_url') = 'string'
    AND length(render_context ->> 'period_label') BETWEEN 3 AND 64
    AND (render_context ->> 'due_on') ~ '^\d{4}-\d{2}-\d{2}$'
    AND (render_context ->> 'action_url') ~ '^/recordatorios\?empresa=[0-9a-f-]{36}$'
    AND pg_column_size(render_context) <= 4096);
