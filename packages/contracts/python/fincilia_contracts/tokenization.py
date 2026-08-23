"""Tokenizacion de identificadores de cuenta.

Una cuenta bancaria se reconoce por su numero, y ese numero es justo lo que no
puede vivir en la base. `canonical-model` tipa `financial_account.identifier_token`
como `tokenized_identifier`: lo que se guarda es una huella con clave, no el dato.

Tres propiedades sostienen esto, y las tres son comprobables:

* **el token es determinista dentro de una version de clave.** La misma cuenta
  produce el mismo token, que es lo que permite detectar un alta duplicada sin
  guardar el numero;
* **el token no se puede invertir sin la clave**, y la clave no es la de firma de
  tokens de sesion. Un secreto que sirve para dos cosas tiene el radio de
  explosion de las dos, y rotar uno obligaria a rotar el otro;
* **rotar la clave no cambia la identidad economica de la cuenta.** El token
  cambia, la fila no: por eso la version de clave se guarda junto al token y no
  dentro de el.

Aqui no se registra nada. El identificador en claro entra, sale un token, y no
toca ningun log ni ninguna excepcion: los mensajes de error de este modulo hablan
de longitudes y de formatos, jamas de valores.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from typing import Final

# Un identificador de cuenta razonable: digitos, letras y separadores. El limite
# alto no es generoso por gusto, es que un IBAN largo cabe en 34 y un identificador
# de pasarela puede ser mas largo.
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._/-]{3,63}$")

# Familias en las que los cuatro ultimos digitos ayudan a reconocer la cuenta sin
# identificarla. Para un ERP o un libro contable no significan nada, y ensenarlos
# seria mostrar un trozo de identificador sin ninguna ganancia.
LAST4_FAMILIES: Final[frozenset[str]] = frozenset({
    "bank_account", "payment_gateway", "merchant_acquirer", "digital_wallet",
})

MIN_KEY_LENGTH: Final[int] = 32
TOKEN_LENGTH: Final[int] = 64


class TokenizationError(ValueError):
    """El identificador o la clave no sirven. El mensaje nunca lleva el valor."""


@dataclass(frozen=True)
class AccountIdentifier:
    """Lo que se guarda de un identificador: su token y su cola visible."""

    token: str
    last4: str | None
    key_version: int

    def as_dict(self) -> dict[str, object]:
        return {"identifier_token": self.token, "identifier_last4": self.last4,
                "identifier_key_version": self.key_version}


def normalise(identifier: str) -> str:
    """Forma comparable de un identificador.

    Sin espacios, sin separadores y en mayusculas: `1234-5678` y `1234 5678` son
    la misma cuenta, y si produjeran tokens distintos el alta duplicada pasaria
    desapercibida, que es exactamente lo que la deteccion existe para evitar.
    """
    if not isinstance(identifier, str):
        raise TokenizationError("the identifier must be text")
    squeezed = re.sub(r"[\s._/-]", "", identifier).upper()
    if not squeezed:
        raise TokenizationError("the identifier is empty once separators are removed")
    return squeezed


def digits_of(identifier: str) -> str:
    return re.sub(r"[^0-9]", "", identifier)


def tokenize(identifier: str, *, key: str, key_version: int = 1,
             account_family: str = "bank_account",
             company_id: str = "") -> AccountIdentifier:
    """Convierte un identificador en lo unico que se persiste de el.

    `company_id` entra en el material del HMAC a proposito: el mismo numero en
    dos empresas produce dos tokens distintos, asi que comparar tokens entre
    empresas no revela que comparten una cuenta. Sin eso, la tokenizacion
    filtraria una relacion que nadie ha autorizado a conocer.
    """
    if not key or len(key) < MIN_KEY_LENGTH:
        raise TokenizationError(
            f"the tokenization key needs at least {MIN_KEY_LENGTH} characters")
    if not 1 <= int(key_version) <= 999:
        raise TokenizationError("the key version is out of range")

    canonical = normalise(identifier)
    if not IDENTIFIER.match(identifier.strip()):
        raise TokenizationError(
            "the identifier has characters or a length this system does not accept")

    material = "\x1f".join((str(key_version), company_id, account_family, canonical))
    token = hmac.new(key.encode("utf-8"), material.encode("utf-8"),
                     hashlib.sha256).hexdigest()

    digits = digits_of(canonical)
    last4 = digits[-4:] if account_family in LAST4_FAMILIES and len(digits) >= 4 else None
    return AccountIdentifier(token=token, last4=last4, key_version=int(key_version))


def matches(candidate: str, stored_token: str, *, key: str, key_version: int,
            account_family: str, company_id: str) -> bool:
    """Compara en tiempo constante.

    Comparar tokens con `==` filtra por cuanto tardan en diferir. Aqui no hay un
    secreto que adivinar caracter a caracter, pero la comparacion insegura es un
    habito que se copia al sitio donde si lo hay.
    """
    try:
        computed = tokenize(candidate, key=key, key_version=key_version,
                            account_family=account_family, company_id=company_id)
    except TokenizationError:
        return False
    return hmac.compare_digest(computed.token, stored_token)


def redact(identifier: str) -> str:
    """Como se nombra un identificador en un mensaje para una persona.

    Nunca el valor. Ni siquiera un prefijo: un prefijo de un numero de cuenta
    identifica al banco, y con la cola visible ya hay bastante para reconocerla.
    """
    digits = digits_of(normalise(identifier)) if identifier else ""
    return f"...{digits[-4:]}" if len(digits) >= 4 else "(sin cola visible)"
