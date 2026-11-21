"""Textos fijos que manda el principal de F7 y el comando «borrar».

Copiados byte a byte del export de n8n (referencia-f7/n8n/agente-principal-unificado.json),
con sus faltas de tildes y sin punto final. El guion es contrato: no tocarlos.
"""

from __future__ import annotations

import re
import unicodedata

# Nodo «Enviar saludo inicial»: va antes de la respuesta en el primer lote de cada sesión.
SALUDO_INICIAL = "Hola, te comunicaste con F7-Automotriz"

# Nodo «Enviar confirmación de reinicio»: la confirmación de «borrar».
ACK_BORRAR = "Ya borre mi memoria, a partir de ahora comienza una conversación nueva"

# Los espacios que reconoce \s en JS (también en modo u).
_JS_ESPACIOS = frozenset(
    "\t\n\x0b\x0c\r \xa0\u1680\u2028\u2029\u202f\u205f\u3000\ufeff"
    + "".join(chr(c) for c in range(0x2000, 0x200B))
)
_JS_ESPACIOS_RE = re.compile(
    "[\t\n\x0b\x0c\r \xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+"
)
_COMANDO = re.compile(r"(?:borrar|borra|borrame)(?: (?:(?:mi|la) memoria|el historial|todo))?")


def _es_borde(c: str) -> bool:
    """[\\s\\p{P}] de JS: espacio o signo de puntuación."""
    return c in _JS_ESPACIOS or unicodedata.category(c).startswith("P")


def es_comando_borrar(texto: object) -> bool:
    """True si el mensaje entero es el comando «borrar» (igual que esComandoBorrar de n8n).

    Normaliza NFKC y NFD, saca las marcas, pasa a minúscula, quita espacios y
    signos de los bordes y junta los espacios repetidos. En n8n además tiene
    que ser texto (un audio nunca es el comando): eso lo controla quien llama.
    """
    if not isinstance(texto, str):
        return False
    t = unicodedata.normalize("NFD", unicodedata.normalize("NFKC", texto))
    t = "".join(c for c in t if not unicodedata.category(c).startswith("M")).lower()
    inicio, fin = 0, len(t)
    while inicio < fin and _es_borde(t[inicio]):
        inicio += 1
    while fin > inicio and _es_borde(t[fin - 1]):
        fin -= 1
    t = _JS_ESPACIOS_RE.sub(" ", t[inicio:fin])
    return _COMANDO.fullmatch(t) is not None
