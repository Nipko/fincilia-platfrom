# ADR-037 — entrega externa de notificaciones

- Estado: **Proposed; adaptadores reales desactivados**
- Fecha: 2026-08-31
- Tarea: FNC-NTF-001
- Owners: Product + Platform + Privacy, accountable FOUNDER-01
- Gates: DRG-00, DRG-01

## Decisión propuesta

- Notifications posee preferencias, mensajes lógicos y entregas; no modifica
  ciclos, expectativas ni estado financiero.
- Un hecho comprometido crea intención + outbox en la misma transacción. El
  dispatcher entrega al menos una vez y el adaptador usa clave idempotente.
- Correo, push y webhook son canales separados. La primera superficie productiva
  será correo; los demás permanecen no configurados.
- Plantillas reciben solo campos allowlisted. No se envían importes, cuentas,
  identificadores fiscales, celdas ni evidencia adjunta.
- Consentimiento, quiet hours, locale, unsubscribe y finalidad se resuelven antes
  de encolar. Timeout desconocido se reconcilia antes de reintentar.
- La UI diferencia `queued`, `sent`, `delivered`, `failed` y `suppressed`; nunca
  llama “entregado” a un recordatorio interno.

## Configuración pendiente para el final

Proveedor SMTP/API, dominio remitente, DKIM/SPF/DMARC, direcciones From/Reply-To,
política de quiet hours y textos legales de baja.

