# Borde HTTPS verificable de UAT

`FNC-UAT-003` observa el borde público de `fincilia.com` sin autenticarse y sin
descargar cuerpos. Su única operación es `HEAD` sobre el origen HTTP y diez
rutas HTTPS públicas.

La sonda comprueba redirección exacta, cadena/nombre TLS, versión TLS moderna,
HSTS de un año con subdominios, CSP sin `unsafe-eval` y sin framing, `nosniff`,
`DENY`, política de permisos cerrada, referrer policy y `no-store`.

## Ejecución

```bash
python3 -m tools.uat_edge_probe probe --revision "$(git rev-parse HEAD)"
python3 -m tools.uat_edge_probe validate
```

El primer comando imprime JSON y nunca lo escribe automáticamente. El
Integration Steward revisa la salida y versiona solo la evidencia mínima. No se
envían cookies, tokens, query strings, formularios ni contenido financiero.

La comprobación es evidencia de UAT, no un pentest ni una aprobación de
producción. Security, Platform/SRE y QA continúan como revisores independientes.
