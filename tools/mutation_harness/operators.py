"""Operadores de mutación declarativos (FNC-QA-005).

Cada operador es una transformación pequeña, nombrada y con parámetros exactos.
**No** existe `eval`, ni snippets de Python, ni regex de reemplazo libre, ni
comandos recibidos del registro: un registro que pudiera describir código sería
un ejecutor de código disfrazado de configuración.

Las rutas dentro del documento usan JSON Pointer (RFC 6901).
Solo biblioteca estándar. Determinista.
"""

from __future__ import annotations

import copy
from typing import Any

FLOATING_TOKENS = ("latest", "main", "head", "stable", "current")


class MutationError(Exception):
    """La mutación no puede aplicarse sobre el documento dado."""


def _tokens(pointer: str) -> list[str]:
    if pointer in ("", "/"):
        return []
    if not pointer.startswith("/"):
        raise MutationError(f"pointer must start with '/': {pointer!r}")
    return [token.replace("~1", "/").replace("~0", "~") for token in pointer[1:].split("/")]


def resolve_parent(document: Any, pointer: str) -> tuple[Any, str]:
    """Devuelve el contenedor y la última clave o índice del puntero."""
    tokens = _tokens(pointer)
    if not tokens:
        raise MutationError("the root cannot be mutated")
    node = document
    for token in tokens[:-1]:
        if isinstance(node, list):
            try:
                node = node[int(token)]
            except (ValueError, IndexError) as error:
                raise MutationError(f"invalid list index {token!r} in {pointer!r}") from error
        elif isinstance(node, dict):
            if token not in node:
                raise MutationError(f"missing key {token!r} in {pointer!r}")
            node = node[token]
        else:
            raise MutationError(f"cannot descend into a scalar at {token!r}")
    return node, tokens[-1]


def read_pointer(document: Any, pointer: str) -> Any:
    parent, last = resolve_parent(document, pointer)
    if isinstance(parent, list):
        try:
            return parent[int(last)]
        except (ValueError, IndexError) as error:
            raise MutationError(f"invalid list index {last!r}") from error
    if isinstance(parent, dict):
        if last not in parent:
            raise MutationError(f"missing key {last!r}")
        return parent[last]
    raise MutationError("pointer does not address a container")


# --------------------------------------------------------------------------- #
# Operadores
# --------------------------------------------------------------------------- #

def op_delete_key(document: Any, params: dict[str, Any]) -> Any:
    """Borra exactamente la clave o el elemento apuntado."""
    result = copy.deepcopy(document)
    parent, last = resolve_parent(result, params["pointer"])
    if isinstance(parent, list):
        parent.pop(int(last))
    elif isinstance(parent, dict):
        if last not in parent:
            raise MutationError(f"missing key {last!r}")
        del parent[last]
    else:
        raise MutationError("pointer does not address a container")
    return result


def op_replace_scalar(document: Any, params: dict[str, Any]) -> Any:
    """Sustituye un escalar exacto. Exige el valor actual para no mutar a ciegas."""
    result = copy.deepcopy(document)
    current = read_pointer(result, params["pointer"])
    if current != params["expected_current"]:
        raise MutationError(
            f"precondition failed: expected {params['expected_current']!r}, found {current!r}")
    parent, last = resolve_parent(result, params["pointer"])
    if isinstance(parent, list):
        parent[int(last)] = params["new_value"]
    else:
        parent[last] = params["new_value"]
    return result


def op_flip_boolean(document: Any, params: dict[str, Any]) -> Any:
    """Invierte una bandera de autoridad, seguridad o segregación de funciones."""
    result = copy.deepcopy(document)
    current = read_pointer(result, params["pointer"])
    if not isinstance(current, bool):
        raise MutationError(f"pointer does not address a boolean, found {type(current).__name__}")
    if current != params["expected_current"]:
        raise MutationError(
            f"precondition failed: expected {params['expected_current']!r}, found {current!r}")
    parent, last = resolve_parent(result, params["pointer"])
    if isinstance(parent, list):
        parent[int(last)] = not current
    else:
        parent[last] = not current
    return result


def op_insert_element(document: Any, params: dict[str, Any]) -> Any:
    """Inserta un elemento en una lista, en una posición exacta."""
    result = copy.deepcopy(document)
    target = read_pointer(result, params["pointer"])
    if not isinstance(target, list):
        raise MutationError("pointer does not address a list")
    index = params.get("index", len(target))
    if not isinstance(index, int) or index < 0 or index > len(target):
        raise MutationError(f"invalid insertion index {index!r}")
    target.insert(index, params["value"])
    return result


def op_reorder_list(document: Any, params: dict[str, Any]) -> Any:
    """Invierte el orden de una lista sin cambiar su contenido.

    Control metamórfico: la semántica no cambia, así que el validador **debe**
    seguir pasando. Si falla, es sensible al orden y eso es un defecto suyo.
    """
    result = copy.deepcopy(document)
    target = read_pointer(result, params["pointer"])
    if not isinstance(target, list):
        raise MutationError("pointer does not address a list")
    if len(target) < 2:
        raise MutationError("reordering a list of fewer than two elements proves nothing")
    target.reverse()
    return result


def op_path_traversal_internal(document: Any, params: dict[str, Any]) -> Any:
    """Reescribe una ruta relativa válida en forma no canónica con `..`.

    La ruta sigue resolviendo dentro del repositorio: el punto es que dos
    grafías del mismo fichero hacen ambigua la contabilidad de digests.
    """
    result = copy.deepcopy(document)
    current = read_pointer(result, params["pointer"])
    if not isinstance(current, str) or not current:
        raise MutationError("pointer does not address a non-empty path string")
    if current != params["expected_current"]:
        raise MutationError(
            f"precondition failed: expected {params['expected_current']!r}, found {current!r}")
    head, _, tail = current.partition("/")
    if not tail:
        raise MutationError("path has no directory segment to traverse through")
    mutated = f"{head}/../{head}/{tail}"
    parent, last = resolve_parent(result, params["pointer"])
    if isinstance(parent, list):
        parent[int(last)] = mutated
    else:
        parent[last] = mutated
    return result


def op_float_version_token(document: Any, params: dict[str, Any]) -> Any:
    """Degrada una versión exacta a un token flotante."""
    result = copy.deepcopy(document)
    current = read_pointer(result, params["pointer"])
    if not isinstance(current, str):
        raise MutationError("pointer does not address a version string")
    if current != params["expected_current"]:
        raise MutationError(
            f"precondition failed: expected {params['expected_current']!r}, found {current!r}")
    token = params.get("token", "latest")
    if token not in FLOATING_TOKENS:
        raise MutationError(f"{token!r} is not a recognised floating token")
    parent, last = resolve_parent(result, params["pointer"])
    if isinstance(parent, list):
        parent[int(last)] = token
    else:
        parent[last] = token
    return result


OPERATORS = {
    "delete_key": op_delete_key,
    "replace_scalar": op_replace_scalar,
    "flip_boolean": op_flip_boolean,
    "insert_element": op_insert_element,
    "reorder_list": op_reorder_list,
    "path_traversal_internal": op_path_traversal_internal,
    "float_version_token": op_float_version_token,
}

OPERATOR_REQUIRED_PARAMS = {
    "delete_key": ("pointer",),
    "replace_scalar": ("pointer", "expected_current", "new_value"),
    "flip_boolean": ("pointer", "expected_current"),
    "insert_element": ("pointer", "value"),
    "reorder_list": ("pointer",),
    "path_traversal_internal": ("pointer", "expected_current"),
    "float_version_token": ("pointer", "expected_current"),
}


def apply_operator(document: Any, operator: str, params: dict[str, Any]) -> Any:
    if operator not in OPERATORS:
        raise MutationError(f"operator {operator!r} is not allowlisted")
    missing = [p for p in OPERATOR_REQUIRED_PARAMS[operator] if p not in params]
    if missing:
        raise MutationError(f"operator {operator!r} needs parameters {missing}")
    return OPERATORS[operator](document, params)
