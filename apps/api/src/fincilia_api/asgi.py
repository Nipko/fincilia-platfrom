"""Punto de entrada ASGI real.

Vive aparte de `main.py` para que importar la fabrica en una prueba no obligue a
resolver la configuracion del proceso.
"""

from fincilia_api.main import create_app

app = create_app()
