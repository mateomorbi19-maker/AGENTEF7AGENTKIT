"""Modalidad (envío o taller en CABA) y estado del turno, como «Preparar Estado» en n8n.

Port de resolverModalidad y del armado del estado del nodo «Preparar Estado»
de referencia-f7/n8n/agente-principal-unificado.json (P9 de MAPA_MIGRACION).
Las regex imitan a las de JS: \\b ASCII, \\s con los espacios de JS, «.» sin
cruzar saltos de línea y $ solo al final del texto.
"""

from __future__ import annotations

import json
import re
import unicodedata

_WS = "\t\n\x0b\x0c\r \xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
_WS_CHARS = frozenset(
    "\t\n\x0b\x0c\r \xa0\u1680\u2028\u2029\u202f\u205f\u3000\ufeff"
    + "".join(chr(c) for c in range(0x2000, 0x200B))
)
_S = "[" + _WS + "]"
_DOT = r"[^\n\r\u2028\u2029]"
_A = re.ASCII


def _c(patron: str) -> re.Pattern:
    """Compila con \\s de JS (escrito como «\\s» en el patrón) y \\b ASCII."""
    return re.compile(patron.replace(r"\s", _S), _A)


_DIACRITICOS = re.compile("[\u0300-\u036f]")
_AFIRMACION = re.compile(
    r"^si[" + _WS + r",]+((?:(?:por|con) )?envio(?: a [a-z ]+)?|(?:en )?caba|(?:en el )?taller|con colocacion)[.!]*\Z",
    _A,
)
_VERBO_EN_ELECCION = _c(
    r"\b(?:me|te|se|sale|cuesta|gratis|es|tienen|puedo|necesito|quiero|debo|hay|seria|fuera|hacen)\b"
)
_CORRECCION = _c(r"\b(?:mejor|al final|en cambio|prefiero ahora|cambio a)\b")
_ORACIONES = _c(r"(?<!\.)\.(?!\.)|[!?\n]+")
_MENCIONA = _c(r"\b(?:envio|caba|taller|colocacion)\b")
_CITA = _c(
    r"\b(?:dije|dicho|dijimos|dijiste|decia|decian|habia pedido|otro pedido|me referia|antes queria|antes preferia)\b|[\"“”«»]"
)
_DUDA = _c(r"\b(?:no estoy seguro|no estoy segura|ya no|no me decido)\b")
_SI_CONDICIONAL = _c(r"\bsi\s+[^,]")
_SEGMENTAR = _c(
    r"\b((?:no|nunca|tampoco)\b[^,;.!?\n]{0,60}\b(?:envio|caba|taller|colocacion))\s+(?:y\s+)?(?=(?:prefiero|elijo|opto por)\b)"
)
_FRAGMENTOS = _c(r"[\n,;.!]+|\bpero\b")
_ESPACIOS = _c(r"\s+")
_ENVIO = _c(
    r"\b(?:envio|envios|envi(?:ar|en|arme)|domicilio|mandan|envian|mandamelo|mandamela|enviamelo|envienmelo|envienmela"
    # Agregado el 17/11 (pedido de Mateo): más formas de pedir el envío.
    r"|manden|mandar|mandarlo|mandarla|mandalo|mandala|mandalos|mandalas|envialo|enviala|envialos|envialas"
    r"|mandenlo|mandenla|envienlo|envienla|correo|encomienda|andreani)\b|\ba mi casa\b"
)
_CABA = _c(r"\b(?:caba|taller|colocacion)\b")
_DUDOSO = _c(r"\b(?:no se|no decidi|todavia no|quizas|tal vez|depende|si es|si puedo|si pueden|si sale|si conviene)\b")
_SI = _c(r"\bsi\b")
_O_Y = _c(r"\b(?:o|y)\b")
_AMBAS = _c(r"\b(?:ambas|ambos|cualquiera)\b")
_UBICACION = _c(r"\b(?:por trabajo|de vacaciones|para trabajar)\b")
_PREGUNTA = _c(r"[?¿]")
_CONSULTA = _c(r"\b(?:hacen|hacias|cuanto|cuesta|tarda|donde|que costo|se puede|pueden enviar|saber)\b")
_NEGACION = _c(r"\b(?:no|nunca|tampoco)\b")
_MULETILLA = _c(r"^(?:bueno|dale|ok|perfecto|entonces|mejor|al final)\s+")

# Elecciones de envío: las primeras se prueban sobre «simple», el resto sobre «f».
_ENVIO_SIMPLE = [
    _c(r"^para enviar\Z"),
    _c(r"^me (?:lo|la|los|las) (?:mandan|envian) a [a-z0-9 ]+\Z"),
    _c(r"^(?:la )?(?:opcion )?(?:de |por |con )?envio(?: a " + _DOT + r"+)?\Z"),
]
_ENVIO_F = [
    # «quisiera»: agregado el 20/11 acá y en las de taller; la pregunta del guion dice «Quisieras…».
    _c(r"\b(?:prefiero|quiero|quisiera|elijo|elegi|opto por|me quedo con|seria|necesito)\s+(?:la\s+)?(?:opcion\s+)?(?:por\s+)?envio\b"),
    _c(r"\b(?:(?:quiero|quisiera|prefiero|necesito)\s+)?que\s+me\s+(?:(?:lo|la|las|los)\s+)?(?:envien|manden)\b"),
    _c(r"\b(?:mandamelo|mandamela|envienmelo|enviamelo|envienmela)\b"),
]
_ENVIO_DOMICILIO = _c(r"^(?:a domicilio|en mi domicilio)\Z")

_CABA_COLOCACION = _c(r"^(?:con )?colocacion en (?:el )?(?:taller|caba)\Z")
_CABA_COLOQUEN = _c(r"\b(?:quiero|quisiera|prefiero|necesito)\s+que\s+(?:me\s+)?(?:lo|la|los|las)\s+coloquen\s+en\s+(?:el\s+)?(?:taller|caba)\b")
_CABA_SOLO = _c(r"^(?:(?:ahi|alla)\s+)?(?:(?:en|al|con)\s+)?(?:(?:el|su)\s+)?(?:caba|taller|colocacion)\Z")
_CABA_PREFIERO = _c(r"\b(?:prefiero|quiero|quisiera|elijo|elegi|opto por|me quedo con|seria|necesito)\s+(?:la\s+)?(?:opcion\s+)?(?:en\s+)?(?:(?:el|su)\s+)?(?:caba|taller|colocacion)\b")
_CABA_VOY = _c(r"\b(?:voy|ire|vamos|iremos|paso|pasare|lo llevo|llevo el auto)\s+(?:a|al|por)\s+(?:el\s+)?(?:taller|caba)\b")
_CABA_COLOCARLO = _c(r"^colocar(?:lo|la|los|las)?(?: (?:ahi|alla))? en (?:(?:el|su|tu|nuestro) )?(?:taller|caba)\Z")
# Corrección del 20/11: «Colocar y soy de Flores CABA» (respuesta real, relevamiento M11).
_CABA_COLOCAR_Y_ZONA = _c(r"^colocar(?:lo|la|los|las)?\s+y\s+(?:soy|somos|estoy|vivo)\s+(?:de|en)\b")
_CABA_PREFIERO_COLOCAR = _c(r"\b(?:prefiero|quiero|quisiera|necesito)\s+colocar(?:lo|la|los|las)?\s+en\s+(?:(?:el|su|tu)\s+)?(?:taller|caba)\b")

# Agregado el 17/11 (pedido de Mateo). El resolver de n8n no reconocía respuestas
# naturales como «Coloco en CABA», «lo coloco en el taller», «me lo mandan» o «lo
# quiero con envio», y el agente volvía a preguntar envío o taller. Las mismas
# exclusiones de antes siguen valiendo: preguntas, condicionales, dudas, citas,
# negaciones y las dos opciones juntas no son una elección.
def _capital(m: re.Match) -> str:
    # Corrección del 20/11 (campaña de pruebas): «Córdoba capital» es la ciudad del cliente, no el taller.
    return m.group(0) if m.group(1) else "caba"


_TIPEOS = [
    (_c(r"\bcab\b"), "caba"),                      # «Coloco en Cab»
    (_c(r"\b(?:(cordoba|mendoza|salta|juan|luis|neuquen|rioja|fe|corrientes|tucuman|catamarca|jujuy|formosa"
        r"|santiago|estero|chaco|misiones)\s+)?capital(?:\s+federal)?\b"), _capital),  # «en Capital»
    (_c(r"\b(?:taler|tayer)\b"), "taller"),
    # Prueba del 21/11: «con embio a tucuman», dos veces, y el agente seguía preguntando.
    (_c(r"\b(?:embio|enbio|emvio)\b"), "envio"),
    (_c(r"\b(?:embios|enbios|emvios)\b"), "envios"),
]
_CABA_VERBO = _c(
    r"^(?:(?:yo|lo|la|los|las|me|nos|se)\s+)*(?:coloco|colocamos|colocaria|colocariamos|colocan|instalo|instalamos"
    r"|retiro|retiramos|hago|hacemos|llevo|llevamos|paso|pasamos|voy|vamos)\s+"
    # Corrección del 20/11: «lo coloco ahí en el taller», «voy directamente al taller».
    r"(?:(?:ahi|alla|directamente|yo)\s+)*(?:a\s+)?(?:en|al|por)\s+"
    r"(?:(?:el|su|tu|nuestro)\s+)?(?:caba|taller)\b"
)
_ENVIO_CON = _c(
    r"^(?:(?:lo|la|los|las)\s+)?(?:(?:quiero|quisiera|prefiero|necesito|seria|va|van|vendria)\s+)?(?:con|por)\s+envio\b"
)
_ENVIO_MANDAN = _c(r"^(?:(?:si|dale|ok)\s+)?me\s+(?:lo|la|los|las)\s+(?:mandan|manden|envian|envien|mandas|envias)\b")
_ENVIO_IMPERATIVO = _c(
    r"\b(?:mandalo|mandala|mandalos|mandalas|envialo|enviala|envialos|envialas|mandenlo|mandenla|envienlo|envienla)\b"
)
_ENVIO_MEDIO = _c(r"^(?:por\s+)?(?:correo|encomienda|andreani)\b|^a\s+mi\s+casa\b")

# Corrección del 20/11 (campaña de pruebas con conversaciones reales y relevamiento de Messenger).
# El agente repetía «envío o taller» aunque el cliente ya lo había dicho, y una pregunta posterior
# borraba lo ya confirmado.
# - «ya te dije», «como te dije»: reafirman la elección que acompañan; no son una cita de otra
#   cosa. Con un «pero» después («te dije envío pero voy yo») quedan como cita, igual que antes.
# - «decime si…», «quería saber si…»: son preguntas, no condicionales. Ni eligen ni borran.
# - Un pedido o una consulta de precio que nombra una sola opción la elige («cuánto sale con
#   envío», «quiero las fundas con envío a Córdoba», «precio colocadas en el taller»). No elige
#   preguntar si hacen envíos, cuánto sale o tarda el envío, cuánto sale la colocación, comparar
#   las dos opciones ni qué incluye un precio ya dado («ese precio es con envío?»): regla del guion.
_REAFIRMA = _c(
    r"\b(?P<negada>(?:no|nunca|tampoco)\s+)?(?:(?:ya|como)\s+)*(?:te\s+)?(?:lo\s+)?dije\b"
    r"(?:\s+(?:que|q|arriba|antes|recien)\b)?"
)
_PERO = _c(r"\bpero\b")
_PREGUNTA_INDIRECTA = _c(
    r"\b(?:decime|decirme|digame|diganme|saber|sabes?|saben|consulto|consultar|consultarte"
    r"|pregunto|preguntar|preguntarte)\s+si\b"
)
_TRAS_PREGUNTA = _c(r"\?+")
_PIDE = _c(
    r"\b(?:precios?|salen?|saldrian?|cuestan?|costarian?|valor|costo|total|presupuesto|cotiza\w*"
    r"|quiero|quisiera|necesito|busco|interesan?|pasame)\b"
    # «cuánto tarda con envío?» pregunta por el tiempo, no por el precio.
    r"|\bcuanto\b(?!\s+(?:tiempo\b|(?:se\s+)?(?:tard|demor|lleg|falta|esper)))"
)
_PEDIDO_ENVIO = _c(
    r"\b(?:con|por)\s+envio\b|\b(?:la|el)\s+(?:opcion\s+)?de\s+envio\b|\bopcion\s+(?:(?:de|con|por)\s+)?envio\b"
)
_PEDIDO_CABA = _c(
    r"\bcolocad[oa]s?\s+(?:(?:ahi|alla)\s+)?en\s+(?:(?:el|su|tu)\s+)?(?:taller|caba)\b"
    r"|\bcon\s+(?:la\s+)?colocacion\b|\bcolocacion\s+incluida\b"
    r"|\b(?:coloco|colocamos|instalo|instalamos|llevo|paso|voy)\s+(?:(?:ahi|alla|directamente|yo)\s+)*"
    r"(?:a\s+)?(?:en|al|por)\s+(?:(?:el|su|tu|nuestro)\s+)?(?:caba|taller)\b"
)
# «cuánto sale en el taller?» pide ese precio; «cuánto sale la colocación en el taller?» pregunta por el servicio.
_PEDIDO_EN_TALLER = _c(r"\ben\s+(?:(?:el|su|tu)\s+)?taller\b")
_COLOCACION_COMO_SERVICIO = _c(r"\bcoloca(?:cion|r\w*)\b")
_DESTINO_CABA = _c(r"\b(?:a|para|hasta)\s+(?:la\s+)?caba\b")  # «con envío a Capital» sigue siendo envío
_ALTERNATIVA = _c(r"\bo\b")
_PRECIO_YA_DADO = _c(
    r"(?<!cuanto\s)\b(?:es|son|era|eran|esta|estan|incluye|incluyen|viene|vienen)\s+(?:ya\s+)?"
    r"(?:(?:con|por)\s+envio|colocad[oa]s?|con\s+(?:la\s+)?colocacion)\b"
    r"|\b(?:ese|este|esos|estos)\s+(?:precios?|valor|presupuesto|importe|total)\b"
)


# Prueba de «romper el flujo» del 21/11. El cliente decía la modalidad a su manera y el agente
# volvía a preguntar, o no registraba que había cambiado de una opción a la otra:
# - al final de un pedido: «fundas para Sandero con envío a Posadas», «todo por envío entonces»;
# - como pedido directo: «Me las mandás a Paraná?», «mandamelas a Tandil», «y con envío?»,
#   «es para colocar en el taller», «lo quiero colocado», «y colocadas en el taller?»;
# - como precio de un escenario: «cuánto sale si lo coloco en el taller», «y si voy al taller?».
# Un condicional de otra cosa («si me conviene voy al taller») sigue sin elegir.
_COLA = r"(?:\s+(?:entonces|nomas|por favor|porfa|gracias|dale))*"
_LUGAR = r"(?!mi\s+(?:mail|email|correo|whatsapp|wsp|celular|telefono|numero)\b)[a-z0-9 ]+?"
_ENVIO_AL_FINAL = _c(r"\b(?:con|por)\s+envio(?:\s+(?:a|hasta|para)\s+" + _LUGAR + r")?" + _COLA + r"\Z")
# «fundas sandero envio a posadas». «El envío a Córdoba» o «precio del envío a…» hablan del envío, no lo eligen.
_ENVIO_DESTINO_AL_FINAL = _c(
    r"(?<!el\s)(?<!del\s)(?<!de\s)(?<!un\s)(?<!su\s)(?<!mi\s)(?<!tu\s)\benvio\s+a\s+" + _LUGAR + _COLA + r"\Z"
)
_VB_ENVIO = r"(?:mandas|mandan|manden|envias|envian|envien)"
_A_LUGAR = r"\s+(?:a|hasta|para)\s+" + _LUGAR
_DIRECTO_ENVIO = [
    _c(r"^(?:y\s+)?(?:si\s+)?(?:mejor\s+)?me\s+(?:lo|la|los|las)\s+" + _VB_ENVIO + _A_LUGAR + r"\s*\??\Z"),
    _c(r"\b(?:mandamel[oa]s?|enviamel[oa]s?|envienmel[oa]s?|mandenmel[oa]s?)" + _A_LUGAR + _COLA + r"\s*\??\Z"),
    _c(r"^y\s+(?:(?:si\s+)?es\s+)?(?:con|por)\s+envio(?:" + _A_LUGAR + r")?\s*\??\Z"),
]
_SI_ENVIO = _c(
    r"\bsi\s+(?:mejor\s+)?(?:me\s+)?(?:(?:lo|la|los|las)\s+)?" + _VB_ENVIO + r"\b"
    r"|\bsi\s+(?:es|fuera|va|van)\s+(?:con|por)\s+envio\b"
)
_EN_TALLER = r"(?:(?:ahi|alla|yo)\s+)*(?:en|al)\s+(?:(?:el|su|tu)\s+)?(?:taller|caba)"
_SI_CABA = _c(
    r"\bsi\s+(?:mejor\s+)?(?:yo\s+)?(?:(?:lo|la|los|las)\s+)?(?:coloco|colocan|llevo|instalo|instalan)\s+" + _EN_TALLER + r"\b"
    r"|\bsi\s+(?:mejor\s+)?voy\s+(?:al\s+taller|a\s+caba)\b"
)
_DIRECTO_CABA = [
    _c(r"^y\s+si\s+(?:mejor\s+)?(?:voy\s+(?:al\s+taller|a\s+caba)|(?:(?:lo|la|los|las)\s+)?(?:coloco|llevo|instalo)\s+"
       + _EN_TALLER + r")\s*\??\Z"),
    _c(r"^y\s+(?:colocad[oa]s?(?:\s+(?:ahi|alla))?(?:\s+en\s+(?:el\s+)?(?:taller|caba))?|con\s+(?:la\s+)?colocacion"
       r"|en\s+(?:el\s+)?taller)\s*\??\Z"),
    _c(r"\bpara\s+colocar(?:lo|la|los|las)?\s+(?:(?:ahi|alla)\b|(?:(?:ahi|alla)\s+)?en\s+(?:(?:el|su|tu)\s+)?(?:taller|caba)\b)"),
    _c(r"\b(?:lo|la|los|las)\s+(?:quiero|quisiera|necesito|prefiero)\s+colocad[oa]s?\b"),
]
_COLOCADO = _c(r"\bcolocad[oa]s?\b")
_DUDA_DIRECTA = _c(r"\b(?:no se|no decidi|todavia no|quizas|tal vez|depende|capaz)\b")
# El «si» de un escenario («cuánto sale si lo coloco en el taller») no es una condición.
_SI_ESCENARIO = re.compile(_SI_CABA.pattern + "|" + _SI_ENVIO.pattern, _A)


# Re-prueba del 21/11 (R55): la frase empieza por lo que se coloca o se manda («las fundas del Gol
# las coloco en el taller», «las fundas me las mandan a Rosario»). El pronombre pegado al verbo
# marca que habla de lo que va a hacer el cliente.
_CABA_OBJETO_VERBO = _c(
    r"\b(?:lo|la|los|las)\s+(?:coloco|colocamos|instalo|instalamos|llevo|llevamos|retiro|retiramos)\s+"
    r"(?:(?:ahi|alla|yo|directamente)\s+)*(?:en|al|por)\s+(?:(?:el|su|tu|nuestro)\s+)?(?:caba|taller)" + _COLA + r"\Z"
)
_ENVIO_OBJETO_VERBO = _c(
    r"\bme\s+(?:lo|la|los|las)\s+(?:mandan|envian|mandas|envias)\s+(?:a|hasta|para)\s+" + _LUGAR + _COLA + r"\Z"
)


# Si en la misma frase pide que le manden otra cosa («las fundas mandamelas… y la alfombra la retiro
# en el taller»), son las dos opciones: no elige.
_PIDE_ENVIO_CON_PRONOMBRE = _c(
    r"\b(?:mandamel[oa]s?|enviamel[oa]s?|envienmel[oa]s?|mandenmel[oa]s?)\b"
    r"|\bme\s+(?:lo|la|los|las)\s+" + _VB_ENVIO + r"\b"
)


def _pedido_directo(f: str) -> str | None:
    """La opción que pide un fragmento con una de las formas de arriba, si nombra una sola."""
    if (_NEGACION.search(f) or _DUDA_DIRECTA.search(f) or _ALTERNATIVA.search(f) or _AMBAS.search(f)
            or _PRECIO_YA_DADO.search(f)):
        return None
    pide = bool(_PIDE.search(f))
    envio = any(p.search(f) for p in _DIRECTO_ENVIO) or (pide and bool(_SI_ENVIO.search(f)))
    caba = any(p.search(f) for p in _DIRECTO_CABA) or (
        pide and (bool(_SI_CABA.search(f)) or bool(_COLOCADO.search(f)))
    )
    if envio == caba:
        return None
    if envio and (_CABA.search(_DESTINO_CABA.sub(" ", f)) or _COLOCADO.search(f)):
        return None
    if caba and _ENVIO.search(f):
        return None
    return "envio" if envio else "caba"


def _envio_al_final(f: str) -> bool:
    """El fragmento termina nombrando el envío: «fundas para Sandero con envío a Posadas»."""
    if _PRECIO_YA_DADO.search(f) or _ALTERNATIVA.search(f):
        return False
    return bool(_ENVIO_AL_FINAL.search(f) or _ENVIO_DESTINO_AL_FINAL.search(f))


def _sin_reafirmacion(m: re.Match) -> str:
    # «no te dije envío» no reafirma nada, y un «pero» después («te dije envío pero voy yo») corrige:
    # en los dos casos se deja como está y sigue contando como cita.
    resto = _ORACIONES.split(m.string[m.end():], maxsplit=1)[0]
    return m.group(0) if m.group("negada") or _PERO.search(resto) else " "


def _cortar_tras_pregunta(m: re.Match) -> str:
    return m.group(0) + "\n"


def _opcion_pedida(f: str) -> str | None:
    """La opción que nombra un pedido o una consulta de precio, si nombra una sola y no la niega."""
    if not _PIDE.search(f) or _PRECIO_YA_DADO.search(f) or _NEGACION.search(f) or _ALTERNATIVA.search(f):
        return None
    envio = bool(_PEDIDO_ENVIO.search(f))
    caba = bool(_PEDIDO_CABA.search(f)) or (
        bool(_PEDIDO_EN_TALLER.search(f)) and not _COLOCACION_COMO_SERVICIO.search(f)
    )
    if envio == caba:
        return None
    # Si además nombra la otra opción, compara: no elige. «Con envío a Capital» es solo el destino.
    if envio and _CABA.search(_DESTINO_CABA.sub(" ", f)):
        return None
    if caba and _ENVIO.search(f):
        return None
    return "envio" if envio else "caba"


def _js_trim(s: str) -> str:
    inicio, fin = 0, len(s)
    while inicio < fin and s[inicio] in _WS_CHARS:
        inicio += 1
    while fin > inicio and s[fin - 1] in _WS_CHARS:
        fin -= 1
    return s[inicio:fin]


def _largo_js(s: str) -> int:
    """.length de JS: cuenta unidades UTF-16 (un emoji vale 2)."""
    return len(s.encode("utf-16-le", "surrogatepass")) // 2


def _afirmacion(m: re.Match) -> str:
    # «sí envío» es una elección; «si es fácil» queda como condicional.
    completo, eleccion = m.group(0), m.group(1)
    return completo if _VERBO_EN_ELECCION.search(eleccion) else eleccion


def resolver_modalidad(historial_humano: object, texto_actual: object) -> str | None:
    """resolverModalidad de n8n, con los agregados del 17/11 y las correcciones del 20/11.

    Recibe:
      historial_humano: los mensajes del cliente de la sesión, del más viejo al
        más nuevo (en n8n, los últimos 30 de la memoria, que ya incluyen el lote
        de este turno; se usan los últimos 30).
      texto_actual: el texto del lote de este turno (se evalúa otra vez al final).
    Devuelve "caba", "envio" o None (sin confirmar, ambiguo o datos inválidos).
    """
    if (
        not isinstance(historial_humano, list)
        or any(not isinstance(t, str) for t in historial_humano)
        or not isinstance(texto_actual, str)
    ):
        return None
    elegida: str | None = None
    for original in [*historial_humano[-30:], texto_actual]:
        if _largo_js(original) > 20000:
            return None
        normalizado = _js_trim(
            _DIACRITICOS.sub("", unicodedata.normalize("NFD", original)).lower()
        )
        for patron, reemplazo in _TIPEOS:
            normalizado = patron.sub(reemplazo, normalizado)
        # Corrección del 20/11: «ya te dije» se quita para leer la elección que reafirma.
        reafirma = any(
            _MENCIONA.search(o) and any(not m.group("negada") for m in _REAFIRMA.finditer(o))
            for o in _ORACIONES.split(normalizado)
        )
        normalizado = _js_trim(_REAFIRMA.sub(_sin_reafirmacion, normalizado))
        texto = _AFIRMACION.sub(_afirmacion, normalizado, count=1)
        correccion = bool(_CORRECCION.search(texto))
        opciones: list[str] = []
        negadas: set[str] = set()
        # Condicionales, dudas y citas valen dentro de la oración que menciona la modalidad.
        ambigua = any(
            _MENCIONA.search(o)
            and (
                _CITA.search(o)
                or _DUDA.search(o)
                # Corrección del 20/11: el «si» de «decime si…» no es una condición.
                # Prueba del 21/11: tampoco lo es el de «cuánto sale si lo coloco en el taller».
                or _SI_CONDICIONAL.search(_SI_ESCENARIO.sub(" ", _PREGUNTA_INDIRECTA.sub(" ", o)))
            )
            for o in _ORACIONES.split(texto)
        )
        # Separar solo una corrección después de una modalidad ya negada.
        segmentado = _SEGMENTAR.sub(r"\1, ", texto)
        # Corrección del 20/11: lo que el cliente afirma después de una pregunta se lee aparte
        # («cuánto sale? lo coloco en el taller»).
        segmentado = _TRAS_PREGUNTA.sub(_cortar_tras_pregunta, segmentado)
        for fragmento in _FRAGMENTOS.split(segmentado):
            f = _ESPACIOS.sub(" ", _js_trim(fragmento))
            # Corrección del 20/11: lo que sigue a «decime si» o «saber si» es una pregunta.
            indirecta = _PREGUNTA_INDIRECTA.search(f)
            if indirecta:
                f = _js_trim(f[: indirecta.start()])
            if not f:
                continue
            # Prueba del 21/11: pedidos directos y precios de un escenario (ver _pedido_directo).
            directo = _pedido_directo(f)
            if directo:
                opciones.append(directo)
                continue
            envio = bool(_ENVIO.search(f))
            caba = bool(_CABA.search(f))
            if not envio and not caba:
                continue
            if _DUDOSO.search(f) or _SI.search(f):
                ambigua = True
                continue
            if (envio and caba and _O_Y.search(f)) or _AMBAS.search(f):
                ambigua = True
                continue
            # Preguntas, ubicación del domicilio y precios no son una elección.
            if _UBICACION.search(f):
                continue
            # Corrección del 20/11: un pedido o una consulta de precio que nombra una sola opción la elige.
            pedida = _opcion_pedida(f)
            if pedida:
                opciones.append(pedida)
                continue
            if _PREGUNTA.search(f) or _CONSULTA.search(f):
                continue
            niega_envio = envio and bool(_NEGACION.search(f))
            niega_caba = caba and bool(_NEGACION.search(f))
            if niega_envio:
                negadas.add("envio")
            if niega_caba:
                negadas.add("caba")
            simple = _MULETILLA.sub("", f, count=1)
            eleccion_envio = (
                any(p.search(simple) for p in _ENVIO_SIMPLE)
                or any(p.search(f) for p in _ENVIO_F)
                or bool(_ENVIO_DOMICILIO.search(simple))
                or bool(_ENVIO_CON.search(simple))
                or bool(_ENVIO_MANDAN.search(simple))
                or bool(_ENVIO_IMPERATIVO.search(f))
                or bool(_ENVIO_MEDIO.search(simple))
                or _envio_al_final(simple)
                or (bool(_ENVIO_OBJETO_VERBO.search(f)) and not caba)
            )
            eleccion_caba = (
                bool(_CABA_COLOCACION.search(simple))
                or bool(_CABA_COLOQUEN.search(f))
                or bool(_CABA_SOLO.search(simple))
                or bool(_CABA_PREFIERO.search(f))
                or bool(_CABA_VOY.search(f))
                or bool(_CABA_COLOCARLO.search(simple))
                or bool(_CABA_PREFIERO_COLOCAR.search(f))
                or bool(_CABA_VERBO.search(simple))
                or bool(_CABA_COLOCAR_Y_ZONA.search(simple))
                or (bool(_CABA_OBJETO_VERBO.search(f)) and not _PIDE_ENVIO_CON_PRONOMBRE.search(f))
            )
            if eleccion_envio and not niega_envio:
                opciones.append("envio")
            if eleccion_caba and not niega_caba:
                opciones.append("caba")
        # Corrección del 20/11: reafirmar sin una elección reconocible sigue siendo ambiguo, como antes.
        if reafirma and not opciones:
            ambigua = True
        distintas = set(opciones)
        if ambigua or (len(distintas) > 1 and not correccion):
            elegida = None
        elif opciones:
            elegida = opciones[-1]
        elif elegida in negadas:
            elegida = None
    return elegida


def modalidad_confirmada(historial_humano: object, texto_actual: object) -> str:
    """Lo que va al prompt y a buscar_precio: "caba", "envio" o "sin_confirmar"."""
    return resolver_modalidad(historial_humano, texto_actual) or "sin_confirmar"


def _numero_js(valor: object) -> float:
    """Number(x) de JS para lo que devuelve un COUNT (número o texto)."""
    if isinstance(valor, bool):
        return 1.0 if valor else 0.0
    if valor is None:
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        t = _js_trim(valor)
        if not t:
            return 0.0
        try:
            return float(t)
        except ValueError:
            return float("nan")
    return float("nan")


def preparar_estado(
    datos: dict,
    cantidad_previa: object,
    multimedia_registrada: object,
    historial_humano: object,
) -> dict:
    """El item que «Preparar Estado» le pasa a «Clasificar y Ensamblar».

    Recibe:
      datos: lo de datos_finales1, al menos {"key": <sesión>, "texto": <lote>}.
      cantidad_previa: el COUNT de mensajes del cliente guardados en la sesión
        antes de este lote («Contar mensajes previos»). 0 = primer lote: el
        flujo ya mandó SALUDO_INICIAL.
      multimedia_registrada: lo de «Leer Estado» (lista de filas con asset_id,
        version, aceptado y hay_envio_incierto, o ese JSON como texto).
      historial_humano: lo de «Leer Estado» (lista de textos del cliente, los
        últimos 30 de la sesión ya con el lote, o ese JSON como texto).
    Devuelve datos más estado_texto, multimedia_registrada (lista),
    saludo_inicial_gestionado_por_flujo, saludo_inicial_enviado,
    modalidad_confirmada y context_guard, en ese orden.
    """
    multimedia = multimedia_registrada
    if isinstance(multimedia, str):
        try:
            multimedia = json.loads(multimedia)
        except ValueError:
            multimedia = []
    humanos = historial_humano
    if isinstance(humanos, str):
        try:
            humanos = json.loads(humanos)
        except ValueError:
            humanos = None
    modalidad = resolver_modalidad(humanos, datos.get("texto"))
    return {
        **datos,
        "estado_texto": "",
        "multimedia_registrada": multimedia if isinstance(multimedia, list) else [],
        "saludo_inicial_gestionado_por_flujo": True,
        "saludo_inicial_enviado": _numero_js(cantidad_previa) == 0,
        "modalidad_confirmada": modalidad if modalidad is not None else "sin_confirmar",
        "context_guard": True,
    }
