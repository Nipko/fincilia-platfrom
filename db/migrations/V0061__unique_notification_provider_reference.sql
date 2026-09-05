-- FNC-NTF-002: el feedback de SES debe identificar una sola entrega.
-- SES genera MessageId unicos; Fincilia persiste unicamente su digest.

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

CREATE UNIQUE INDEX uq_notification_delivery_provider_message_ref
  ON fincilia.notification_delivery (provider_message_ref)
  WHERE provider_message_ref IS NOT NULL;

COMMENT ON INDEX fincilia.uq_notification_delivery_provider_message_ref IS
  'Hace inequivoca la correlacion minimizada de feedback del proveedor.';
