# DRG-01 — piloto privado con datos reales

Este paquete convierte la intención “probar con mis propios datos” en una lista
cerrada de obligaciones. No autoriza una carga: el reporte permanece bloqueado
mientras falte una sola evidencia o revisión requerida.

## Alcance más pequeño útil

El primer piloto real empieza con una empresa del Founder y usuarios nominales.
Admite únicamente extractos, auxiliares y facturas propios en CSV, XLSX o PDF.
No admite tarjetas, nómina, documentos de identidad, salud, secretos, conectores,
correo, SFTP, webhooks, IA externa ni cierre automático.

Esta reducción limita el daño posible, pero no convierte los datos en sintéticos:
siguen sujetos a privacidad, seguridad, transmisión internacional, retención y
borrado.

## Secuencia obligatoria

1. Cerrar DRG-00: tratamiento, L-01, A-02, ambiente aislado, inventario,
   borrado, ensayo y revisión independiente.
2. Desplegar el entorno de piloto separado del host beta: HTTPS/WAF como única
   entrada, stores privados, KMS, Secrets Manager, CloudTrail y SSM sin SSH.
3. Activar IdP administrado, usuarios nominales, MFA y revocación; PostgreSQL
   continúa siendo la autoridad de empresa y rol.
4. Demostrar cuarentena, inspección, canales no usados deshabilitados, RLS y
   negaciones cross-tenant.
5. Ejercitar backup/restore con tombstones, derechos, incidente y rollback.
6. Obtener concepto PCI, DPA/subencargados, pentest e independientes nominales.
7. Solo entonces el gate puede derivar `real_data_authorized=true`.

## Verificación

```text
python -m tools.drg01_readiness.validate
python -m unittest tools.drg01_readiness.test_validate
```

El resultado válido hoy es `ok: true`, `DRG-01: not_met` y una lista explícita
de blockers. `ok` significa que el modelo no se contradice; no que el piloto
esté autorizado.
