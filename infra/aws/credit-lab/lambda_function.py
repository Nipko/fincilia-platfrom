"""Respuesta pública sintética y efímera para la actividad AWS Lambda."""


def lambda_handler(event, context):
    del event, context
    body = """<!doctype html>
<html lang="es">
<head><meta charset="utf-8"><title>Fincilia AWS Credit Lab</title></head>
<body>
  <main>
    <h1>Fincilia AWS Credit Lab</h1>
    <p>Laboratorio efímero, sin usuarios ni datos financieros.</p>
  </main>
</body>
</html>"""
    return {
        "statusCode": 200,
        "headers": {
            "content-type": "text/html; charset=utf-8",
            "cache-control": "no-store",
            "x-content-type-options": "nosniff",
            "content-security-policy": "default-src 'none'; style-src 'unsafe-inline'",
        },
        "body": body,
    }
