"""Partir la respuesta del modelo en globos de WhatsApp, como F7 en n8n.

Port de splitResponse del nodo «devuelve outputs» (igual a
referencia-f7/logica/unificado/logica.mjs:33-89). Corta en cada punto que no
esté protegido (URLs, mails, números con punto, «Av.»), limpia Markdown y
saca las comillas dobles y «¿». Los pedazos quedan sin punto final.

Las regex imitan a las de JS: \\b y \\w ASCII, \\s con los espacios de JS,
«.» sin cruzar saltos de línea y ^/$ de línea con los saltos de JS.
"""

from __future__ import annotations

import re

_WS = "\t\n\x0b\x0c\r \xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
_WS_CHARS = frozenset(
    "\t\n\x0b\x0c\r \xa0\u1680\u2028\u2029\u202f\u205f\u3000\ufeff"
    + "".join(chr(c) for c in range(0x2000, 0x200B))
)
# ^ y $ de JS con la bandera m: también cortan en \r, \u2028 y \u2029.
_INI = r"(?:\A|(?<=[\n\r\u2028\u2029]))"
_FIN = r"(?=[\n\r\u2028\u2029]|\Z)"
_A = re.ASCII

_ESCAPADOS = re.compile(r"\\r\\n|\\n|\\r")
_CRLF = re.compile(r"\r\n?")
_LINEA_EN_BLANCO = re.compile(r"\n(?:[\t ]*\n)+")
_LINKS = re.compile(r"!?\[([^\]\n]*)\]\(")
_DESTINO = re.compile(
    r"^(?:<((?:https?://|www\.|mailto:)[^<>" + _WS + r"]+)>|((?:https?://|www\.|mailto:)[^"
    + _WS + r"]+?))(?:[" + _WS + r"]+(?:\"[^\"]*\"|'[^']*'))?\Z",
    re.I | _A,
)
_URL_O_MAIL = re.compile(
    r"(?:https?://|www\.)[^" + _WS + r"<>\"`]+|[\w.+-]+@[\w.-]+\.[a-z]{2,}", re.I | _A
)
_GUIONES_INICIO = re.compile(r"^_{1,3}")
_CIERRE_SIGNOS = re.compile(r"[.!?,;:]+\Z")
_MARCA_ANTES = re.compile(r"(\*{1,3}|_{1,3})\Z")
_NUMEROS = re.compile(r"[0-9]+(?:\.[0-9]+)+")
_AVENIDA = re.compile(r"\b(?:av|avda)\.(?=[" + _WS + r"])", re.I | _A)
# Agregado el 17/11: «etc.» no corta el mensaje (antes «…, etc.)» dejaba un «)» suelto).
_ETCETERA = re.compile(r"\betc\.", re.I | _A)
# Prueba del 21/11 (R05): una letra sola con punto pegada a la palabra siguiente es una abreviatura
# de la planilla («T.ENTERO», «T.DIVIDIDOS»), no el fin de una oración.
_ABREVIATURA = re.compile(r"\b[a-z]\.(?=[a-z])", re.I | _A)

_BLOQUE_CODIGO = re.compile(
    _INI + r"[\t ]*(?:`{3,}|~{3,})(?:[a-z0-9_+-]+)?[\t ]*(?:\n|" + _FIN + r")", re.I | _A
)
_SEPARADOR = re.compile(_INI + r"[\t ]*(?:={2,}|-{2,}|\*{3,}|_{3,})[\t ]*" + _FIN)
_TITULO = re.compile(
    _INI + r"[\t ]*#{1,6}[\t ]+([^\n\r\u2028\u2029]+?)(?:[\t ]+#+)?[\t ]*" + _FIN
)
_VINETA = re.compile(_INI + r"[\t ]*(?:[-+*•◦▪‣]|[0-9]{1,9}[.)])[\t ]+(?:\[[ xX]\][\t ]+)?")
_TOKEN_ENTRE_ANGULOS = re.compile("<([\ue000][0-9]+[\ue001])>")
_ASTERISCO_O_ACENTO = re.compile(r"\*|`")
# [^\p{L}\p{N}_] de JS = [^\w] de Python en modo Unicode (\w = isalnum o «_»).
_ENFASIS = re.compile(r"(^|[^\w])_{1,3}([^\n]+?)_{1,3}(?=\Z|[^\w])")
_TACHADO = re.compile(r"~~([^\n]+?)~~")
_ESPACIOS = re.compile("[" + _WS + "]+")
_TOKEN = re.compile("\ue000([0-9]+)\ue001")


def _js_trim(s: str) -> str:
    inicio, fin = 0, len(s)
    while inicio < fin and s[inicio] in _WS_CHARS:
        inicio += 1
    while fin > inicio and s[fin - 1] in _WS_CHARS:
        fin -= 1
    return s[inicio:fin]


def _a_texto(valor: object) -> str:
    """String(value ?? '') de JS, para lo que puede llegar acá."""
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "true" if valor else "false"
    return str(valor)


def partir_respuesta_f7(texto: object) -> list[str]:
    """Parte la respuesta del modelo en los globos que le llegan al cliente.

    Recibe el texto final (ya controlado). Devuelve la lista de globos, sin
    punto final; lista vacía si no queda nada (en n8n: no se manda nada).
    """
    text = _CRLF.sub("\n", _ESCAPADOS.sub("\n", _a_texto(texto)))
    # Una línea en blanco separa globos: queda una marca que al final es un punto.
    text = _LINEA_EN_BLANCO.sub("\n\ue002\n", text)
    tokens: list[str] = []

    def protect(s: str) -> str:
        key = f"\ue000{len(tokens)}\ue001"
        tokens.append(s)
        return key

    # Enlaces [texto](url): se lee el cierre balanceado del paréntesis.
    cursor, plain, pos = 0, "", 0
    while True:
        match = _LINKS.search(text, pos)
        if not match:
            break
        last_index = match.end()
        pos = last_index
        end, depth = last_index, 1
        while end < len(text) and depth:
            if text[end] == "(":
                depth += 1
            if text[end] == ")":
                depth -= 1
            end += 1
        if depth:
            continue
        target = _js_trim(text[last_index:end - 1])
        destination = _DESTINO.search(target)
        if not destination:
            continue
        plain += text[cursor:match.start()] + match.group(1) + " " + protect(
            destination.group(1) or destination.group(2)
        )
        cursor = end
        pos = end
    text = plain + text[cursor:]

    def url_o_mail(m: re.Match) -> str:
        s, offset, whole = m.group(0), m.start(), m.string
        leading = ""
        email_marker = ""
        if "@" in s:
            gm = _GUIONES_INICIO.search(s)
            email_marker = gm.group(0) if gm else ""
        if email_marker and whole[offset + len(s):].startswith(email_marker):
            leading = email_marker
            s = s[len(email_marker):]
        tm = _CIERRE_SIGNOS.search(s)
        trailing = tm.group(0) if tm else ""
        if trailing:
            s = s[: -len(trailing)]
        mm = _MARCA_ANTES.search(whole[:offset])
        marker = mm.group(0) if mm else ""
        if marker and s.endswith(marker):
            s = s[: -len(marker)]
            trailing = marker + trailing
        return leading + protect(s) + trailing

    text = _URL_O_MAIL.sub(url_o_mail, text)
    text = _NUMEROS.sub(lambda m: protect(m.group(0)), text)
    text = _AVENIDA.sub(lambda m: protect(m.group(0)), text)
    text = _ETCETERA.sub(lambda m: protect(m.group(0)), text)
    text = _ABREVIATURA.sub(lambda m: protect(m.group(0)), text)

    text = _BLOQUE_CODIGO.sub("\n", text)
    text = _SEPARADOR.sub("", text)
    text = _TITULO.sub(r"\1", text)
    text = _VINETA.sub("", text)
    text = _TOKEN_ENTRE_ANGULOS.sub(r"\1", text)
    text = _ASTERISCO_O_ACENTO.sub("", text)
    text = _ENFASIS.sub(r"\1\2", text)
    text = _TACHADO.sub(r"\1", text)
    text = text.replace('\\"', "").replace('"', "").replace("¿", "").replace("\ue002", ".")
    text = _js_trim(_ESPACIOS.sub(" ", text))
    if not text:
        return []

    def restaurar(m: re.Match) -> str:
        i = int(m.group(1))
        return tokens[i] if i < len(tokens) else "undefined"

    partes = (_js_trim(_TOKEN.sub(restaurar, s)) for s in text.split("."))
    return [p for p in partes if p]
