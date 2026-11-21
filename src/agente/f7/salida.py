"""Control de la salida comercial del principal (P13) y constancia de cotización en la memoria (P14).

Port tal cual de los nodos de `referencia-f7/n8n/agente-principal-unificado.json`
(versión publicada, igual a `nodes`): «Controlar salida comercial»,
«Requiere revision comercial?», «Derivar por control comercial»,
«Salida comercial confirmada», «Reparar memoria comercial» y
«Verificar memoria comercial». Mismas reglas, regex y textos byte a byte.
Lógica pura: no llama al modelo, a Chatwoot ni a Postgres.

Corrección del 20/11 (campaña de pruebas): n8n ya no se usa y en tres puntos, marcados
en el código, deja de ser igual al nodo:
- Con buscar_precio en el turno, los párrafos del modelo que son una respuesta (sin
  pregunta, sin precios y sin repetir la continuación) salen antes de la continuación.
- buscar_precio puede pedir el pase a Candela con cualquier estado
  (`requiere_derivacion: "revision_especial"`), no solo con metodo_no_confirmado.
- `corregir_frases(texto)` deja la pregunta de modalidad en su forma literal y quita los
  anuncios de material ya enviado. No la llama el control: la llama el turno sobre el
  texto final.

Cómo se usa en un turno (el mismo camino que en n8n):

1. `controlar_salida_comercial(agente, texto_cliente=lote)`
   - `agente["output"]`: el texto crudo del modelo (str).
   - `agente["intermediateSteps"]`: lista de pasos, uno por llamada a
     herramienta, con la forma de n8n:
     `{"action": {"tool": "buscar_precio", "toolInput": {...}}, "observation": <resultado>}`.
     `tool` es el nombre de la herramienta (`buscar_precio`, `derivar_humano`
     o `enviar_multimedia`; las demás se ignoran). `observation` es el objeto
     JSON que devolvió la herramienta: se acepta como dict, como string JSON
     o como lista de un solo dict (igual que el nodo).
   - `texto_cliente`: el texto del cliente del turno (el lote ya juntado,
     lo que en n8n es `datos_finales1.texto`).
2. Si `requiere_revision_comercial(salida)` da True, hay que llamar a la
   herramienta de derivación con `motivo=MOTIVO_DERIVACION_CONTROL`
   ("revision_especial") y el sufijo `derivacion-v1` en el solicitud_id.
   Su resultado (dict) es el `dato` del paso 3. Si da False, `dato` es la
   misma `salida` del paso 1.
3. `final = salida_comercial_confirmada(dato, raw=agente["output"], texto_cliente=lote)`.
4. Memoria: `segura = texto_para_memoria(final, raw)`; el último mensaje `ai`
   de la memoria pasa de `raw` a `segura` con `reparar_memoria_comercial`, y
   `verificar_memoria_comercial(final, memoria)` corta el turno si no se pudo.

Qué devuelve el control (paso 1 y paso 3), con las claves de n8n:
- `output` (str): lo único que sale al cliente. Vacío = silencio (P17).
- `requiere_derivacion` (bool): True = callar y derivar con revision_especial.
- `bot_pausado` (bool): True = la herramienta dejó la conversación con humano.
- `estado` (opcional): el estado que dejó la herramienta.
- `control_salida` (dict): `motivo` (control_humano, resultado_derivacion,
  revision_especial, solicitud_humana_no_atendida, continuacion_de_herramienta,
  precio_sin_contrato, registro_interno_no_publicable, importe_sin_herramienta,
  cotizacion_sin_accion o texto_sin_importes), `modificada`,
  `importe_modelo_bloqueado`, `resultado_incierto`, `faq_pendientes`,
  `faq_preservadas` y, según el caso, `bot_pausado`, `estado`,
  `solicitud_humana_detectada` y (paso 3, después de derivar) `origen`.
- `memoria_output` (opcional): lo que va a la memoria en vez de `output`
  (la salida más la nota «[Registro interno de cotización confirmada] {...}»).

Ejemplo (importes inventados, no hay importes acá):

    agente = {
        "output": "Te paso el presupuesto",
        "intermediateSteps": [{
            "action": {"tool": "buscar_precio", "toolInput": {"pedido": {}}},
            "observation": {"estado": "cotizado", "cotizacion_enviada": True,
                "envio": {"estado": "aceptado", "chatwoot_message_id": 55},
                "items": [{"producto": "fundas", "modelo": "Suran",
                    "configuracion": "5 plazas", "cantidad": 1, "estado": "cotizado"}],
                "metodo_pago": "transferencia", "continuacion_obligatoria": ""},
        }],
    }
    salida = controlar_salida_comercial(agente, texto_cliente="precio fundas suran")
    # salida["output"] == ""  (la cotización ya la mandó la herramienta)
    # salida["requiere_derivacion"] is False
    # salida["control_salida"]["motivo"] == "continuacion_de_herramienta"
    # salida["memoria_output"] == '[Registro interno de cotización confirmada] '
    #   '{"herramienta":"buscar_precio","estado":"cotizado","situacion":"aceptada_por_chatwoot",'
    #   '"items":[{"producto":"fundas","modelo":"Suran","configuracion":"5 plazas",'
    #   '"cantidad":1,"estado":"cotizado"}],"metodo_pago":"transferencia"}'

Para que coincida con JS: `\\b`, `\\d` y `\\w` son ASCII (re.ASCII); `\\s`,
`.`, `$` y `.trim()` se escriben con los conjuntos de JS; los largos y los
topes `{0,90}` cuentan unidades UTF-16 como en JS.
"""

from __future__ import annotations

import functools
import json
import re
import unicodedata

from .precios.herramienta import PREGUNTA_MODALIDAD

MOTIVO_DERIVACION_CONTROL = "revision_especial"

TEXTO_PASE_NO_CONFIRMADO = "No pude confirmar el pase. Esa parte necesita revisión del equipo."
TEXTO_PRECIO_SIN_CONTRATO = (
    "No pude confirmar el resultado de la consulta de precios. Esa parte necesita revisión del equipo."
)
MARCA_MEMORIA = "[Registro interno de cotización confirmada] "


class ErrorDeSalida(Exception):
    """El turno no puede seguir (en n8n: el nodo tira error y va a «Conservar error»)."""


# ---------------------------------------------------------------- equivalencias JS

# Lo que JS considera espacio en \s y en .trim().
_WS = "\t\n\x0b\x0c\r \xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
_WS_CHARS = "\t\n\x0b\x0c\r \xa0\u1680" + "".join(chr(c) for c in range(0x2000, 0x200B)) + "\u2028\u2029\u202f\u205f\u3000\ufeff"
S = "[" + _WS + "]"
NS = "[^" + _WS + "]"
# El punto de JS no toma fines de línea.
DOT = "[^\n\r\u2028\u2029]"
_A = re.ASCII


class _Undef:
    """El `undefined` de JS (clave ausente), distinto de None (`null`)."""

    def __repr__(self) -> str:
        return "undefined"


UNDEF = _Undef()


def _get(obj, clave):
    """`obj?.clave` de JS."""
    if isinstance(obj, dict):
        return obj.get(clave, UNDEF)
    return UNDEF


def _nulo(v) -> bool:
    return v is None or v is UNDEF


def _truthy(v) -> bool:
    if _nulo(v) or v is False:
        return False
    if isinstance(v, bool):
        return True
    if isinstance(v, (int, float)):
        return v == v and v != 0
    if isinstance(v, str):
        return v != ""
    return True


def _safe_int(v) -> bool:
    """Number.isSafeInteger."""
    if isinstance(v, bool):
        return False
    if isinstance(v, int):
        return abs(v) <= 9007199254740991
    if isinstance(v, float):
        return v == v and v not in (float("inf"), float("-inf")) and v.is_integer() and abs(v) <= 9007199254740991
    return False


def _utf16(s: str) -> str:
    """Parte los caracteres fuera del BMP en dos sustitutos, como los ve JS."""
    if all(ord(c) <= 0xFFFF for c in s):
        return s
    out = []
    for c in s:
        o = ord(c)
        if o > 0xFFFF:
            o -= 0x10000
            out.append(chr(0xD800 + (o >> 10)))
            out.append(chr(0xDC00 + (o & 0x3FF)))
        else:
            out.append(c)
    return "".join(out)


def _sin_marcas(s: str) -> str:
    return re.sub("[\u0300-\u036f]", "", unicodedata.normalize("NFD", s))


def _trim(s: str) -> str:
    return s.strip(_WS_CHARS)


def _js_str(v) -> str:
    """String(v ?? '') para lo que llega acá (texto)."""
    if _nulo(v):
        return ""
    if isinstance(v, str):
        return v
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _json_parse(texto: str):
    def _no_constante(nombre):
        raise ValueError(nombre)

    return json.loads(texto, parse_constant=_no_constante)


def _json_stringify(valor) -> str:
    texto = json.dumps(valor, ensure_ascii=False, separators=(",", ":"))
    # JSON.stringify escapa los sustitutos sueltos.
    return re.sub("[\ud800-\udfff]", lambda m: "\\u%04x" % ord(m.group(0)), texto)


# ---------------------------------------------------------------- piezas del nodo


def observacion_unica(valor):
    """observacionUnica: el resultado de una herramienta como un solo dict, o None."""
    v = valor
    if isinstance(v, str):
        try:
            v = _json_parse(v)
        except Exception:
            return None
    if isinstance(v, list):
        if len(v) != 1:
            return None
        v = v[0]
    if not isinstance(v, dict):
        return None
    return v


_NUMERO = (
    "(?:un|uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|trece|catorce|quince|"
    "dieciseis|diecisiete|dieciocho|diecinueve|veinte|veinti[a-z]+|treinta|cuarenta|cincuenta|sesenta|"
    "setenta|ochenta|noventa|cien|ciento|doscientos|trescientos|cuatrocientos|quinientos|seiscientos|"
    "setecientos|ochocientos|novecientos|mil|millon|millones)"
)
_ESCRITO = _NUMERO + "(?:[ -]+(?:y|de|" + _NUMERO + ")){0,12}"
_RE_UNIDADES = re.compile(
    r"\b(?:\d+(?:[.,]\d+)?|" + _NUMERO + ")" + S + r"*(?:cuotas?|plazas?|butacas?|dias?|horas?|meses?|anos?)\b", _A
)
_RE_URLS = re.compile(r"https?://" + NS + "+|www\\." + NS + "+", _A)
_RE_IMPORTE = [
    ("t", re.compile(r"(?:\$|\bars\b|\busd\b)" + S + r"*\d", _A)),
    ("u", re.compile(r"\b\d{5,}\b", _A)),
    ("u", re.compile(r"\b\d+(?:[.,]\d+)?" + S + r"*k\b", _A)),
    ("t", re.compile(r"\b\d[\d.,]*" + S + r"*(?:pesos|dolares)\b", _A)),
    ("t", re.compile(r"\b\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?\b", _A)),
    ("t", re.compile(r"\b" + _ESCRITO + S + r"+(?:pesos|dolares)\b", _A)),
    ("t", re.compile(r"\b" + _NUMERO + "(?:[ -]+(?:y|" + _NUMERO + ")){0,8}" + S + r"+(?:mil|millon|millones)\b", _A)),
    (
        "s",
        re.compile(
            r"\b(?:(?:total|precio|valor|importe)(?:" + S + r"+(?:total|final))?(?:" + S + "*:" + S + "*|" + S
            + r"+(?:es(?:" + S + r"+de)?|son|seria(?:" + S + r"+de)?|serian|de)" + S + r"+)|(?:cuesta|sale|queda|vale)(?:"
            + S + r"+en)?" + S + r"+)(?:\d+|" + _NUMERO + r")\b(?!" + S
            + r"+(?:juegos?|productos?|articulos?|unidades?|butacas?|plazas?|cuotas?|dias?|horas?|meses?|anos?)\b)",
            _A,
        ),
    ),
    ("t", re.compile(r"\bcuotas?" + S + r"+de" + S + r"+\d+\b", _A)),
    ("t", re.compile(r"\b\d+(?:[.,]\d+)?" + S + r"*(?:mil|millones)\b", _A)),
]


def contiene_importe(texto) -> bool:
    """contieneImporte: True si el texto trae algo que se lee como dinero."""
    t = _sin_marcas(_js_str(texto)).lower()
    textos = {"t": t, "s": _RE_UNIDADES.sub("cantidad", t), "u": _RE_URLS.sub("enlace", t)}
    return any(re_.search(textos[cual]) for cual, re_ in _RE_IMPORTE)


def _normalizar_faq(s) -> str:
    return _trim(re.sub(S + "+", " ", _sin_marcas(_js_str(s)).lower()))


_RE_PREGUNTA = re.compile(
    r"[?¿]|\b(?:cuanto|cuando|donde|que|como|tienen|hay|atienden|abren|cierran|me (?:decis|confirmas|pasas|contas)|quiero saber)\b",
    _A,
)
_TEMAS = [
    ("demora", re.compile("tarda|demora|plazo|cuanto" + DOT + "*(?:hacer|confeccion|colocar)", _A)),
    ("garantia", re.compile("garantia", _A)),
    ("ubicacion", re.compile("donde|direccion|ubicacion", _A)),
    ("horario", re.compile("horario|atienden|abren|cierran", _A)),
    ("medidas", re.compile("medidas?|compatib|le va|sirve para", _A)),
    ("logo", re.compile("logo|puede decir|puedo poner|bordad|texto|nombre", _A)),
]
_REGLAS_FAQ = [
    ("demora", "fundas", re.compile(r"^(?:la )?confeccion(?: aproximada)?(?: es de| tarda| demora| lleva)? (?:aproximadamente )?5 dias habiles desde (?:la )?sena\Z", _A), "La confección aproximada es de 5 días hábiles desde la seña."),
    ("demora", "tipo tapizado", re.compile(r"^(?:la )?confeccion(?: aproximada)?(?: es de| tarda| demora| lleva)? (?:aproximadamente )?7 dias habiles desde (?:la )?sena\Z", _A), "La confección aproximada es de 7 días hábiles desde la seña."),
    ("demora", "fundas", re.compile(r"^(?:la )?colocacion(?: es de| tarda| demora| lleva)? (?:entre )?4 (?:a|y) 5 horas\Z", _A), "La colocación lleva entre 4 y 5 horas."),
    ("demora", "tipo tapizado", re.compile(r"^(?:la )?colocacion(?: es de| tarda| demora| lleva)? una jornada laboral(?:, usualmente de 9 a 18)?\Z", _A), "La colocación lleva una jornada laboral, usualmente de 9 a 18."),
    ("garantia", "fundas", re.compile(r"^contas con garantia de fabrica por 90 dias desde su colocacion\Z", _A), "Contas con garantía de fábrica por 90 días desde su colocación"),
    ("garantia", "tipo tapizado", re.compile(r"^contas con garantia de fabrica por 90 dias desde su colocacion\Z", _A), "Contas con garantía de fábrica por 90 días desde su colocación"),
    ("ubicacion", None, re.compile(r"^(?:📍)?la direccion es av[.]? olivera 1265" + S + r"*, caba\Z", _A), "📍La dirección es Av. Olivera 1265 , CABA."),
    ("ubicacion", None, re.compile(r"^nuestra ubicacion exacta la podes ver ingresando a este link https://maps[.]app[.]goo[.]gl/nsyib1thu4wcn2l8a\?g_st=ipc\Z", _A), "Nuestra ubicación exacta la podes ver ingresando a este link https://maps.app.goo.gl/Nsyib1THu4WCN2L8A?g_st=ipc"),
    ("horario", None, re.compile(r"^te esperamos de lunes a viernes de 9 a 18 hs y sabado de 9 a 14 hs\Z", _A), "Te esperamos de lunes a viernes de 9 a 18 hs y sábado de 9 a 14 hs"),
    ("logo", None, re.compile(r"^(?:el )?logo solicitado (?:necesita|requiere) confirmacion de candela\Z", _A), "El logo solicitado necesita confirmación de Candela."),
]
_RE_PARTIR_FRASES = re.compile(r"\n+|;|(?<=[.!?])" + S + "+(?!" + NS + "*https?:)", _A)


def preservar_faq(raw, texto_cliente, resultado: dict) -> dict:
    """preservarFaq: frases FAQ de la lista cerrada que el cliente preguntó y el modelo escribió literal."""
    cliente = _normalizar_faq(texto_cliente)
    if not _RE_PREGUNTA.search(cliente):
        return {"texto": "", "faq_preservadas": [], "faq_pendientes": []}
    temas = [tema for tema, re_ in _TEMAS if re_.search(cliente)]
    items = _get(resultado, "items")
    if _nulo(items):
        items = []
    if not isinstance(items, list):
        raise ErrorDeSalida("resultado.items no es una lista")  # en JS: .map tira TypeError
    productos_vistos = []
    for i in items:
        if i is None or i is UNDEF:
            raise ErrorDeSalida("item nulo en resultado.items")  # en JS: i.producto tira TypeError
        p = _get(i, "producto")
        if not any(p is q or (type(p) is type(q) and p == q) for q in productos_vistos):
            productos_vistos.append(p)
    uno = productos_vistos[0] if len(productos_vistos) == 1 else None
    frases = [
        re.sub(r"[.!?]+\Z", "", _normalizar_faq(s))
        for s in _RE_PARTIR_FRASES.split(re.sub(r"\bAv\.", "Av", _js_str(raw), flags=_A))
    ]
    elegidas = [
        r
        for r in _REGLAS_FAQ
        if r[0] in temas
        and (not r[1] or (isinstance(uno, str) and r[1] == uno))
        and any(r[2].search(f) for f in frases)
    ]
    preservadas = list(dict.fromkeys(r[0] for r in elegidas))
    return {
        "texto": "\n\n".join(dict.fromkeys(r[3] for r in elegidas)),
        "faq_preservadas": preservadas,
        "faq_pendientes": [t for t in temas if t not in preservadas],
    }


_NEG = re.compile(r"\b(?:no|nunca|tampoco|si|quizas|tal vez|mas adelante|dije|dicho)\b|[\"“”«»]", _A)
_RE_CONSULTA_PAGO = (
    re.compile(r"\b(?:efectivo|transferencia|cuotas|debito|tarjeta|medios? de pago)\b", _A),
    re.compile(
        r"\b(?:cuanto (?:sale|cuesta|vale|seria|queda|quedaria)|que (?:precio|valor)|(?:puedo|se puede) pagar|aceptan)\b|\b(?:precio|valor|importe|costo)"
        + S + r"*\?",
        _A,
    ),
    re.compile(r"\b(?:ahora|ya|comprar|reservar|reservame|agendame)\b", _A),
)


def _r(p):
    return re.compile(p.replace("\\s", S), _A)


_PAGO_ALIAS = (_r(r"\b(?:pasame|dame|mandame|enviame|necesito|quiero|me pasas|me podes pasar)\s+(?:(?:el|tu|su)\s+)?(?:alias|cbu)\b"), _r(r"\b(?:uso|puedo usar)\s+(?:el\s+)?alias\b"))
_PAGO_YA = _r(r"\b(?:ya pague|ya transferi|voy a pagar|voy a transferir)\b")
_PAGO_QUIERO = _r(r"\bquiero pagar\b")
_PERSONA = (
    _r(r"\b(?:quiero|necesito|quisiera)\s+(?:hablar|seguir|continuar)\s+con\s+(?:una?\s+)?(?:persona|humano|asesor|alguien|candela)\b"),
    _r(r"\b(?:me pasas|pasame|me podes pasar|lo veo|lo hablo)\s+con\s+(?:una?\s+)?(?:persona|humano|asesor|alguien|candela)\b"),
    _r(r"\bcon candela para (?:encargar|pagar|reservar)\b"),
    _r(r"\b(?:alguien me lo puede confirmar|quien me lo puede ver)\b"),
)
_TURNO = (_r(r"\b(?:quiero|necesito|quisiera)\s+(?:(?:un|sacar|reservar|coordinar|agendar)\s+)?turno\b"), _r(r"\b(?:reservame|agendame|dame)\s+(?:un\s+)?turno\b"))
_RESERVA = _r(r"\b(?:quiero|necesito|quisiera)\s+reservar\b")
_RECLAMO = (_r(r"\b(?:quiero|necesito|tengo)\s+(?:(?:hacer|presentar)\s+)?(?:un\s+)?reclamo\b"), _r(r"\bme (?:la|lo) cambian\b"), _r(r"\b(?:rompio|rota|roto|reclamo)\b"))


def solicitud_humana_explicita(texto):
    """solicitudHumanaExplicita: 'pago', 'persona', 'turno', 'reserva', 'posventa' o None."""
    if not isinstance(texto, str) or len(_utf16(texto)) > 20000:
        return None
    t = _sin_marcas(texto).lower()
    if (
        re.search(r"\bya (?:la |lo )?mande\b", t, _A)
        and re.search(r"\bme confirmas si llego\b", t, _A)
        and not re.search(r"(?:\bno\b|[\"“”«»])", t, _A)
    ):
        return "pago"
    consulta_pago = (
        bool(_RE_CONSULTA_PAGO[0].search(t))
        and bool(_RE_CONSULTA_PAGO[1].search(t))
        and not _RE_CONSULTA_PAGO[2].search(t)
    )
    for parte in re.split(r"[\n,;.!]+", t):
        f = _trim(re.sub(S + "+", " ", parte))
        if not f or _NEG.search(f):
            continue
        if _PAGO_ALIAS[0].search(f) or _PAGO_ALIAS[1].search(f):
            return "pago"
        if _PAGO_YA.search(f) or (_PAGO_QUIERO.search(f) and not consulta_pago):
            return "pago"
        if any(p.search(f) for p in _PERSONA):
            return "persona"
        if _TURNO[0].search(f) or _TURNO[1].search(f):
            return "turno"
        if _RESERVA.search(f):
            return "reserva"
        if _RECLAMO[0].search(f) or (_RECLAMO[1].search(f) and _RECLAMO[2].search(t)):
            return "posventa"
    return None


_PRODUCTOS = ("fundas", "tipo tapizado", "tapiceria", "alfombra", "funda baul", "cobertor caja", "espuma", "otros", "cubrevolante")
_ESTADOS_ITEM = ("cotizado", "requiere_aclaracion", "sin_precio", "no_encontrado")


def _en(v, opciones) -> bool:
    """`[...].includes(v)` con strings: sin igualar True con 1."""
    return isinstance(v, str) and v in opciones


def _texto_seguro(v) -> bool:
    if _nulo(v):
        return True
    if not isinstance(v, str):
        return False
    return (
        len(_utf16(v)) <= 500
        and not re.search("[\u0000-\u001f\u007f<>`]", v)
        and not re.search(r"https?://|www[.]", v, re.ASCII | re.IGNORECASE)
        and not contiene_importe(v)
    )


def memoria_cotizacion_confirmada(resultado):
    """memoriaCotizacionConfirmada: la nota interna de la cotización, o None si no corresponde."""
    if not _truthy(resultado) or not isinstance(resultado, dict):
        return None
    envio = _get(resultado, "envio")
    items = _get(resultado, "items")
    if (
        not _en(_get(resultado, "estado"), ("cotizado", "parcial"))
        or _get(resultado, "cotizacion_enviada") is not True
        or not _en(_get(envio, "estado"), ("aceptado", "omitido"))
        or not _safe_int(_get(envio, "chatwoot_message_id"))
        or _get(envio, "chatwoot_message_id") <= 0
        or not isinstance(items, list)
        or len(items) < 1
        or len(items) > 10
    ):
        return None
    metodo = _get(resultado, "metodo_pago")
    if metodo is not UNDEF and not _en(metodo, ("transferencia", "efectivo", "cuotas")):
        return None
    pregunta = _get(resultado, "pregunta_comercial_incluida")
    if pregunta is not UNDEF and not isinstance(pregunta, bool):
        return None
    for i in items:
        cantidad = _get(i, "cantidad")
        if (
            not _truthy(i)
            or not _en(_get(i, "producto"), _PRODUCTOS)
            or not _en(_get(i, "estado"), _ESTADOS_ITEM)
            or not _safe_int(cantidad)
            or cantidad < 1
            or cantidad > 10
            or not _texto_seguro(_get(i, "modelo"))
            or not _texto_seguro(_get(i, "configuracion"))
        ):
            return None
    cotizados = sum(1 for i in items if i["estado"] == "cotizado")
    estado = resultado["estado"]
    if (
        not cotizados
        or (estado == "cotizado" and cotizados != len(items))
        or (estado == "parcial" and cotizados == len(items))
    ):
        return None
    lista = [
        {
            "producto": i["producto"],
            "modelo": None if _nulo(_get(i, "modelo")) else i["modelo"],
            "configuracion": None if _nulo(_get(i, "configuracion")) else i["configuracion"],
            "cantidad": int(i["cantidad"]),
            "estado": i["estado"],
        }
        for i in items
    ]
    nota = {
        "herramienta": "buscar_precio",
        "estado": estado,
        "situacion": "aceptada_por_chatwoot" if envio["estado"] == "aceptado" else "ya_aceptada_por_chatwoot",
        "items": lista,
    }
    if metodo is not UNDEF:
        nota["metodo_pago"] = metodo
    if pregunta is not UNDEF:
        nota["pregunta_comercial_incluida"] = pregunta
    return MARCA_MEMORIA + _json_stringify(nota)


_ETIQUETA = r"(?:registro|resumen|nota|memoria|evento)" + S + r"+intern[oa]"
_TEMA = r"(?:cotizacion|presupuesto|buscar_precio)"
_RE_REGISTRO = (
    re.compile(r"\b" + _ETIQUETA + r"\b[^.!?]{0,90}\b" + _TEMA + r"\b", _A),
    re.compile(r"\b" + _TEMA + r"\b[^.!?]{0,90}\b" + _ETIQUETA + r"\b", _A),
    re.compile(r"\bpregunta[_ ]+comercial[_ ]+incluida[\"']?" + S + "*[:=]", _A),
    re.compile(r"\bsituacion[\"']?" + S + "*[:=]" + S + r"*[\"']?(?:ya[_ ]+)?aceptada[_ ]+por[_ ]+chatwoot\b", _A),
    re.compile(r"\bherramienta[\"']?" + S + "*[:=]" + S + r"*[\"']?buscar_precio\b", _A),
)


def contiene_registro_interno(texto) -> bool:
    """contieneRegistroInterno: el modelo copió la nota interna o su estructura."""
    t = re.sub("[\u0300-\u036f\u200b-\u200d\ufeff]", "", unicodedata.normalize("NFD", _js_str(texto))).lower()
    t = re.sub("[“”]", '"', t)
    t = re.sub("[‘’]", "'", t)
    t = re.sub(r"\\([\"'])", r"\1", t)
    t = _utf16(re.sub(S + "+", " ", t))
    return any(r.search(t) for r in _RE_REGISTRO)


_RE_ANUNCIO_PASADO = re.compile(r"\b(?:te" + S + r"+)?(envie|mande|pase|actualice|enviad[oa]|actualizad[oa])\b" + DOT + "{0,45}?(?:cotizacion|presupuesto)", _A)
_RE_PARA_QUE = re.compile(r"\bpara que" + S + r"+\Z", _A)
_RE_ANUNCIO_PARTICIPIO = re.compile(r"(?:cotizacion|presupuesto)\b" + DOT + "{0,30}(?:enviad[oa]|actualizad[oa])", _A)
_RE_ANUNCIO_FUTURO = re.compile(r"\bte" + S + r"+(?:paso|envio|mando)\b" + DOT + "{0,45}?(?:cotizacion|presupuesto)", _A)
_RE_CONDICION = re.compile(r"\b(?:asi|para que|cuando|apenas|en cuanto|una vez que)\b|\bsi" + S + "+[a-z]", _A)


def anuncia_cotizacion_sin_accion(n: str) -> bool:
    """anunciaCotizacionSinAccion: recibe el texto ya sin tildes y en minúsculas."""
    for frase in re.split(r"[.!?\n]+", _utf16(n)):
        hubo = False
        for m in _RE_ANUNCIO_PASADO.finditer(frase):
            if re.fullmatch("envie|mande|pase", m.group(1)) and _RE_PARA_QUE.search(frase[: m.start()]):
                continue
            hubo = True
            break
        if hubo:
            return True
        if _RE_ANUNCIO_PARTICIPIO.search(frase):
            return True
        for m in _RE_ANUNCIO_FUTURO.finditer(frase):
            if not _RE_CONDICION.search(frase[: m.start()]):
                return True
    return False


# ---------------------------------------------------------------- Corrección del 20/11 (campaña de pruebas)
# Desde acá ya no es port de n8n: salió de la campaña de pruebas con conversaciones reales.
# - corregir_frases(): la pregunta de modalidad vuelve a su forma literal y se van los
#   anuncios de material ya enviado.
# - _parrafos_de_respuesta(): cuando corrió buscar_precio, lo que el modelo le contestó al
#   cliente sobre otra cosa (colocación, logo, plazos) ya no se descarta.

_RE_FIN_ORACION = re.compile(r"[ \t\r]*\n[ \t\r\n]*|(?<=[.!?…])(?<!\bAv\.)[ \t]+")
# Palabras sin contenido: no cuentan para decidir si dos frases dicen lo mismo.
_VACIAS = frozenset(
    "algo ante con contra del desde donde durante ella ellas ello ellos entre era esa esas ese eso esos esta "
    "estan estas este esto estos fue hay las les los mas mis muy nos nuestra nuestras nuestro nuestros para "
    "pero por que sea ser sin sobre son sus tambien tus una unas uno unos vos".split()
)


def _tramos(texto: str) -> list:
    """Dónde empieza y dónde termina cada oración; lo que queda entre dos es el separador."""
    tramos, inicio = [], 0
    for m in _RE_FIN_ORACION.finditer(texto):
        if m.start() > inicio:
            tramos.append((inicio, m.start()))
        inicio = m.end()
    if inicio < len(texto):
        tramos.append((inicio, len(texto)))
    return tramos


def _plano(texto: str) -> str:
    """Minúsculas, sin tildes ni signos: las palabras separadas por un espacio."""
    return " ".join(re.sub("[^a-z0-9]+", " ", _sin_marcas(texto).lower()).split())


def _raices(texto: str) -> frozenset:
    """Las palabras con contenido, recortadas: «confirmá» y «confirmes» cuentan como la misma."""
    return frozenset(
        (p[:-1] if len(p) > 3 and p.endswith("s") else p)[:6]
        for p in _plano(texto).split()
        if p not in _VACIAS and (len(p) > 2 or p.isdigit())
    )


def _parecido(a: frozenset, b: frozenset) -> float:
    """Qué parte de las palabras comparten dos frases (0 a 1)."""
    return len(a & b) / len(a | b) if a and b else 0.0


def _unir(piezas: list, separadores: list) -> str:
    """Junta las piezas que quedan (las vacías se saltean) con el separador más fuerte que había entre ellas."""
    salida, pendiente = [], None
    for k, pieza in enumerate(piezas):
        if pieza:
            if salida:
                salida.append(pendiente)
            salida.append(pieza)
            pendiente = None
        if k < len(separadores) and (pendiente is None or separadores[k].count("\n") >= pendiente.count("\n")):
            pendiente = separadores[k]
    return "".join(salida)


# -- Frases fijas del guion (las oraciones llegan sin tildes y en minúsculas) --

_M_ENVIO = r"(?:envi|mand)[a-z]*"
_M_TALLER = r"(?:taller(?:es)?|caba|retir[a-z]*|coloc[a-z]*)"
_M_HASTA_LA_O = r"(?:[ ,]+[a-z0-9]+){0,4}?[ ,]+o[ ,]+(?:[a-z0-9]+[ ,]+){0,6}?"
# «envío o … taller» (o al revés): las dos opciones unidas por una «o», con pocas palabras en el medio.
_RE_ENVIO_O_TALLER = (
    re.compile(r"\b" + _M_ENVIO + r"\b" + _M_HASTA_LA_O + _M_TALLER + r"\b", _A),
    re.compile(r"\b" + _M_TALLER + r"\b" + _M_HASTA_LA_O + _M_ENVIO + r"\b", _A),
)
# «¿te mando el video o las fotos del taller?» elige material, no modalidad.
_RE_MATERIAL_EN_MEDIO = re.compile(r"\b(?:videos?|fotos?|imagen(?:es)?|catalogos?|audios?)\b", _A)
# Pregunta o le pide al cliente que elija. «opciones», «preferencia» o «lo cual» solos no alcanzan:
# «Las dos opciones, envío o colocación en el taller, tienen la misma garantía» es una respuesta.
_RE_PIDE_ELEGIR = re.compile(
    r"[?¿]|\b(?:prefer(?:is|irias?)|prefier(?:as?|es?)|quer(?:es|ias|rias)|quier(?:es|as)|quisieras?|"
    r"necesit(?:o|amos|aria|ariamos)|contanos|contame|decime|decinos|indicame|indicanos|avisame|avisanos|"
    r"confirmame|confirmanos|eleg(?:i|is)|elij(?:as?)|podes elegir)\b|(?<!\blo )(?<!\bla )(?<!\bel )\bcual\b",
    _A,
)
# Otra frase fija del guion, que no se toca: «El efectivo es solo para el taller de CABA.
# ¿Preferís venir al taller o mantener el envío?»
_RE_OTRA_ELECCION = re.compile(r"\b(?:efectivo|manten[a-z]*)\b", _A)
_RE_INSISTE = re.compile(
    r"\b(?:cual(?:es)?|que)(?: de (?:las|los|esas|estas|ambas)(?: dos)?(?: (?:opciones|alternativas))?"
    r"| (?:opcion|alternativa))?(?: (?:te|les))? (?:pref[ie]{1,2}r[a-z]*|eleg[a-z]*|elij[a-z]*|conviene|queda[a-z]*|sirve)\b"
    r"|\b(?:cual|que) (?:opcion|alternativa)\b|\bcual de (?:las|los) dos\b|\bcon cual\b",
    _A,
)
_RE_PREGUNTA_O_PEDIDO = re.compile(r"[?¿]|\b(?:decime|contame|contanos|avisame|indicame|confirmame)\b", _A)
# La frase literal, con cualquier espacio o salto entre sus palabras.
_RE_MODALIDAD_LITERAL = re.compile(r"\s+".join(re.escape(p) for p in PREGUNTA_MODALIDAD.split()))
# Las palabras de su primera oración: «Hacemos envios a todo el pais y nuestro taller esta situado en CABA.»
_RAICES_PRESENTA_MODALIDAD = _raices(PREGUNTA_MODALIDAD[slice(*_tramos(PREGUNTA_MODALIDAD)[0])])

_M_MATERIAL_UNO = (
    r"(?:(?:el|la|los|las|un|una|unos|unas) )?(?:videos?|fotos?|imagen(?:es)?|material|archivos?)"
    r"(?: comparativo)?(?: del? [a-z0-9 ]{1,40}?)?"
)
_M_MATERIAL = _M_MATERIAL_UNO + r"(?: y " + _M_MATERIAL_UNO + r")?"
_M_ENVIADO = r"(?:enviad[oa]s?|mandad[oa]s?)"
_M_ENTRADA = r"(?:(?:listo|perfecto|dale|genial|bueno)[, ]+)?"
_RE_ANUNCIO_MATERIAL = (
    # «El video ya quedó enviado», «Las fotos ya fueron enviadas», «El video ya se envió»
    re.compile(
        _M_ENTRADA + _M_MATERIAL + r" (?:ya )?(?:(?:te )?(?:quedo|quedaron|fue|fueron|esta|estan) (?:ya )?"
        + _M_ENVIADO + r"|se (?:envio|enviaron|mando|mandaron))(?: (?:arriba|recien|antes))?",
        _A,
    ),
    # «Ya quedaron enviadas las fotos»
    re.compile(
        _M_ENTRADA + r"(?:ya )?(?:quedo|quedaron|fue|fueron|esta|estan) (?:ya )?" + _M_ENVIADO + " " + _M_MATERIAL, _A
    ),
    # «Ya te envié el video», «Te mandé las fotos de los diseños»
    re.compile(
        _M_ENTRADA + r"(?:(?:ya|ahi|aca|recien) )*(?:te )?(?:(?:lo|la|los|las) )?"
        r"(?:envie|mande|pase|enviamos|mandamos|pasamos|acabo de (?:enviar|mandar|pasar)) " + _M_MATERIAL
        + r"(?: (?:arriba|recien))?",
        _A,
    ),
)


def _anuncia_material_enviado(oracion: str) -> bool:
    """La oración entera solo avisa que un video o unas fotos ya se mandaron."""
    frase = oracion.strip(" .!¡…")
    return any(p.fullmatch(frase) for p in _RE_ANUNCIO_MATERIAL)


def _es_pregunta_de_modalidad(oraciones: list, i: int) -> bool:
    """La oración i pide elegir entre envío y taller (la literal del guion o una reformulada)."""
    n = oraciones[i]
    if _RE_OTRA_ELECCION.search(n) or (i and _RE_OTRA_ELECCION.search(oraciones[i - 1])):
        return False
    if not _RE_PIDE_ELEGIR.search(n):
        return False
    for patron in _RE_ENVIO_O_TALLER:
        m = patron.search(n)
        while m:
            if not _RE_MATERIAL_EN_MEDIO.search(m.group(0)):
                return True
            m = patron.search(n, m.start() + 1)
    return False


def _presenta_la_modalidad(oracion: str) -> bool:
    """No agrega nada a la primera mitad de la literal («Hacemos envios a todo el pais y …»)."""
    raices = _raices(oracion)
    return (
        not re.search("[?¿]", oracion)
        and len(raices) >= 2
        and (raices <= _RAICES_PRESENTA_MODALIDAD or _parecido(raices, _RAICES_PRESENTA_MODALIDAD) >= 0.6)
    )


def _insiste_con_la_eleccion(oracion: str) -> bool:
    """Solo insiste con que elija: «Cuál de las dos opciones te queda mejor?»."""
    return bool(_RE_PREGUNTA_O_PEDIDO.search(oracion)) and bool(_RE_INSISTE.search(oracion))


_VOCALES = {"a": "aá", "e": "eé", "i": "ií", "o": "oó", "u": "uúü"}


@functools.lru_cache(maxsize=256)
def _patron_tal_cual(frase: str) -> re.Pattern:
    """La frase del guion aceptando tildes agregadas, un signo de apertura y otros espacios."""
    partes = ["[¿¡]?"]
    for c in frase:
        variantes = _VOCALES.get(c.lower())
        if variantes:
            partes.append("[" + variantes + variantes.upper() + "]")
        elif c.isspace():
            if partes[-1] != r"\s+":
                partes.append(r"\s+")
        else:
            partes.append(re.escape(c))
    return re.compile("".join(partes))


def frases_tal_cual(texto: str, frases) -> str:
    """Deja como en el guion las frases citadas que el modelo copió con tildes o signos de más.

    Re-prueba de multimedia del 21/11. Solo toca coincidencias palabra por palabra; no pasa la
    marca del registro interno de cotización.
    """
    if not isinstance(texto, str) or not texto:
        return texto
    corte = texto.find(MARCA_MEMORIA)
    cuerpo, resto = (texto, "") if corte < 0 else (texto[:corte], texto[corte:])
    for frase in frases or ():
        cuerpo = _patron_tal_cual(frase).sub(lambda m, f=frase: f, cuerpo)
    return cuerpo + resto


# Decisión de Mateo del 21/11: no se dice «No tengo fotos».
# Entre «no tengo» y «fotos» solo entran palabras de relleno: «no hay problema, te mando el video»
# o «no tenemos cuero natural, el material es…» no niegan nada.
_M_RELLENO = (
    r"(?:\s+(?:ningun[ao]?s?|es[eao]s?|est[eao]s?|el|la|los|las|un|una|unos|unas|mas|otr[ao]s?|disponibles?|"
    r"todavia|aun|tampoco|ni|de|por|canal|medio|aca|en|momento|ahora|actualmente))*"
)
_RE_NIEGA_FOTOS = (
    re.compile(
        r"\bno\s+(?:tenemos|tengo|tienen?|hay|existen?|(?:contamos|cuento|cuentan?)\s+con"
        r"|(?:disponemos|dispongo|disponen?)\s+de"
        r"|(?:te\s+)?(?:puedo|podemos|podria|podriamos)\s+(?:mandar|enviar|pasar|compartir|mostrar)(?:te|les|le)?)"
        + _M_RELLENO + r"\s+(?P<cosa>fotos?|fotitos?|imagen(?:es)?|videos?|material|contenidos?)\b",
        _A,
    ),
    # «fotos no tengo», «fotos como tal no tenemos» (no «en el video se ve que no hay que desarmar»)
    re.compile(
        r"\b(?P<cosa>fotos?|fotitos?|imagen(?:es)?|videos?)(?:\s+\w+){0,3}?\s+no\s+"
        r"(?:tenemos|tengo|hay|contamos|cuento)\b(?!\s+que\b)",
        _A,
    ),
)
# «Material» también es el cuero y «contenido» puede ser cualquier cosa: cuentan solo si esa parte
# de la oración (entre comas) habla de mostrarlo o mandarlo.
_RE_MATERIAL_PARA_VER = re.compile(
    r"\b(?:visual(?:es)?|fotografic\w+|mostr\w+|envi\w+|mand\w+|compart\w+|ver(?:lo|la|los|las)?"
    r"|por\s+(?:aca|este\s+(?:medio|canal)))\b",
    _A,
)
_COSAS_AMBIGUAS = ("material", "contenido", "contenidos")


def _niega_fotos(llano: str):
    """Dónde la oración (en minúsculas y sin tildes) dice que no hay fotos, videos o material."""
    for patron in _RE_NIEGA_FOTOS:
        for m in patron.finditer(llano):
            if m.group("cosa") not in _COSAS_AMBIGUAS:
                return m
            desde = max(llano.rfind(c, 0, m.start()) for c in ",;:") + 1
            hasta = min((p for p in (llano.find(c, m.end()) for c in ",;:") if p >= 0), default=len(llano))
            if _RE_MATERIAL_PARA_VER.search(llano[desde:hasta]):
                return m
    return None
_RE_PERO = re.compile(r",?\s*\bpero\s+", _A)


def sin_negar_fotos(texto: str, url_catalogo: str | None = None) -> str:
    """Saca las oraciones que dicen que no hay fotos o videos.

    Si la oración sigue con «pero…» queda esa parte; si era lo único que había, va el catálogo
    del guion (sin `url_catalogo` no va nada: en el turno ya salió material). No pasa la marca
    del registro interno de cotización.
    """
    if not isinstance(texto, str) or not texto:
        return texto
    corte = texto.find(MARCA_MEMORIA)
    cuerpo, resto = (texto, "") if corte < 0 else (texto[:corte], texto[corte:])
    tramos = _tramos(cuerpo)
    piezas = [cuerpo[a:b] for a, b in tramos]
    cambio = False
    for i, pieza in enumerate(piezas):
        llano = "".join(c for c in unicodedata.normalize("NFD", pieza.lower()) if unicodedata.category(c) != "Mn")
        niega = _niega_fotos(llano)
        if not niega:
            continue
        cambio = True
        pero = _RE_PERO.search(pieza)
        if pero and niega.start() < pero.start():
            queda = pieza[pero.end():]
        elif pero:
            queda = pieza[:pero.start()]
        else:
            queda = ""
        queda = queda.strip()
        piezas[i] = (queda[:1].upper() + queda[1:]) if queda else None
    if not cambio:
        return texto
    if not any(piezas):
        nuevo = f"Catálogo: {url_catalogo}" if url_catalogo else ""
    else:
        separadores = [cuerpo[tramos[k][1]:tramos[k + 1][0]] for k in range(len(tramos) - 1)]
        nuevo = cuerpo[:tramos[0][0]] + _unir(piezas, separadores) + cuerpo[tramos[-1][1]:]
    return nuevo + (("\n\n" if nuevo and not nuevo.endswith("\n") else "") + resto if resto else "")


def _sin_oraciones(texto: str, descartar) -> str:
    """El texto sin las oraciones que `descartar(oracion, indice, oraciones)` marca.

    No toca la marca del registro interno de cotización ni lo que viene después.
    """
    if not isinstance(texto, str) or not texto:
        return texto
    corte = texto.find(MARCA_MEMORIA)
    cuerpo, resto = (texto, "") if corte < 0 else (texto[:corte], texto[corte:])
    tramos = _tramos(cuerpo)
    piezas = [cuerpo[a:b] for a, b in tramos]
    fuera = [i for i in range(len(piezas)) if descartar(piezas[i], i, piezas)]
    if not fuera:
        return texto
    for i in fuera:
        piezas[i] = None
    if not any(piezas):
        nuevo = ""
    else:
        separadores = [cuerpo[tramos[k][1]:tramos[k + 1][0]] for k in range(len(tramos) - 1)]
        nuevo = cuerpo[:tramos[0][0]] + _unir(piezas, separadores) + cuerpo[tramos[-1][1]:]
    return nuevo + (("\n\n" if nuevo and not nuevo.endswith("\n") else "") + resto if resto else "")


# Prueba de «romper el flujo» del 21/11 (R08, R10): «Sí, tenemos fundas para el BYD Dolphin» y «…para
# camiones, incluido Scania», sin haber consultado la planilla. El guion pide no afirmar que hay un
# producto para un vehículo sin el resultado de buscar_precio.
_RE_AFIRMA_PARA = re.compile(
    r"^(?:si,?\s+(?:claro,?\s+)?)?(?:tenemos|contamos\s+con|hacemos|realizamos|fabricamos|confeccionamos|trabajamos)\b"
    r"[^.!?\n]*\b(?:fundas?|alfombras?|cubre\s?volantes?|cobertor(?:es)?|tapizados?|tapiceria|medidas|moldes?)\b"
    r"[^.!?\n]*\bpara\s+\S",
    _A,
)
_RE_EMPIEZA_CON_SI = re.compile(r"^si\b", _A)


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def sin_afirmar_disponibilidad(texto: str) -> str:
    """Saca las oraciones que afirman que hay un producto para un vehículo.

    Se usa cuando en el turno no hubo una cotización que lo respalde. «Si, hacemos envios a…» y lo
    que el guion sí afirma (qué trabajos hacen, la garantía, la presentación) no se tocan.
    """
    def afirma(oracion, _i, _todas) -> bool:
        llano = _sin_tildes(oracion).strip()
        if "envio" in llano:
            return False
        m = _RE_AFIRMA_PARA.search(llano)
        # Sin el «sí» adelante solo cuenta «tenemos…» o «contamos con…» (una respuesta a «tienen para…?»).
        return bool(m) and (bool(_RE_EMPIEZA_CON_SI.search(llano)) or llano.startswith(("tenemos", "contamos")))

    return _sin_oraciones(texto, afirma)


# Prueba del 21/11 (R27): cerró con «envío o taller?» y «crédito o débito?» juntas. El guion pide
# una sola pregunta por mensaje: después de la de modalidad no va otra.
_PREGUNTA_MODALIDAD_PLANA = "quisieras la opcion de envio o colocarlo en nuestro taller"


def una_sola_pregunta(texto: str) -> str:
    """Saca las preguntas que el modelo agrega después de la pregunta de envío o taller."""
    def sobra(oracion, i, todas) -> bool:
        if "?" not in oracion:
            return False
        return any(_PREGUNTA_MODALIDAD_PLANA in _plano(previa) for previa in todas[:i] if previa)

    return _sin_oraciones(texto, sobra)


def corregir_frases(texto: str) -> str:
    """Deja las frases fijas del guion como son, sobre el texto final que se le manda al cliente.

    - La pregunta de modalidad reformulada («necesito saber si preferís envío o retirarlo en
      nuestro taller») se cambia por la literal `PREGUNTA_MODALIDAD`, una sola vez, junto con la
      oración pegada que la presenta o que solo insiste («Cuál de las dos opciones te queda mejor?»).
    - Se quitan los anuncios de material ya enviado («El video ya quedó enviado»).
    Si el texto ya trae la pregunta literal no se toca ninguna pregunta de modalidad, y si no hay
    nada que corregir vuelve igual, byte a byte. Lo que sigue a la marca de la nota interna de
    cotización (`MARCA_MEMORIA`) tampoco se toca: no es texto para el cliente. Lógica pura.
    """
    if not isinstance(texto, str):
        return texto
    nota = texto.find(MARCA_MEMORIA)
    if nota >= 0:
        antes = corregir_frases(texto[:nota])
        return texto if antes == texto[:nota] else antes + texto[nota:]
    tramos = _tramos(texto)
    piezas = [texto[a:b] for a, b in tramos]
    oraciones = [_normalizar_faq(p) for p in piezas]
    cambio = False
    for i, oracion in enumerate(oraciones):
        if _anuncia_material_enviado(oracion):
            piezas[i], cambio = None, True
    if not _RE_MODALIDAD_LITERAL.search(texto):
        puesta, i, ultima = False, 0, -1
        while i < len(piezas):
            if piezas[i] is None or not _es_pregunta_de_modalidad(oraciones, i):
                i += 1
                continue
            desde = i
            while desde - 1 > ultima and _presenta_la_modalidad(oraciones[desde - 1]):
                desde -= 1
            hasta = i + 1 if i + 1 < len(piezas) and _insiste_con_la_eleccion(oraciones[i + 1]) else i
            piezas[desde:hasta + 1] = [None] * (hasta + 1 - desde)
            if not puesta:
                piezas[desde], puesta = PREGUNTA_MODALIDAD, True
            cambio, ultima, i = True, hasta, hasta + 1
    if not cambio:
        return texto
    if not any(piezas):
        return ""
    separadores = [texto[tramos[k][1]:tramos[k + 1][0]] for k in range(len(tramos) - 1)]
    return texto[:tramos[0][0]] + _unir(piezas, separadores) + texto[tramos[-1][1]:]


# -- Respuestas del modelo que acompañan a lo que resolvió buscar_precio --

_RE_PARRAFOS = re.compile(r"(?:[ \t\r]*\n){2,}[ \t]*")
_RE_HABLA_DE_PRECIO = re.compile(
    r"\b(?:precios?|valor(?:es)?|cotiz[a-z]*|presupuest[a-z]*|total(?:es)?|salen?|cuestan?|descuentos?)\b", _A
)
# El mismo corte de frases de preservar_faq, guardando el separador y sin cortar en «Av.».
_RE_CORTE_FAQ = re.compile(r"(\n+|;|(?<=[.!?])(?<!\bAv\.)" + S + "+(?!" + NS + "*https?:))", _A)
_RE_PIDE_DATO = re.compile(
    r"\b(?:decime|decinos|contame|contanos|pasame|pasanos|confirmame|confirmanos|indicame|indicanos|avisame|"
    r"avisanos|aclarame|necesito|necesitamos|necesitaria|necesitariamos|cual(?:es)?)\b"
    r"|\bme (?:decis|confirmas|pasas|contas|indicas)\b",
    _A,
)


_INTERJECCIONES = frozenset("perfecto listo dale genial buenisimo ok bien entendido barbaro".split())


def _es_respuesta(parrafo: str) -> bool:
    """El párrafo se puede mandar junto con lo que resolvió buscar_precio."""
    if _plano(parrafo) in _INTERJECCIONES:
        return False  # «Perfecto.», «¡Listo!»: no contestan nada
    n = _sin_marcas(parrafo).lower()
    if re.search("[?¿]", _RE_URLS.sub("", n)):
        return False  # la única pregunta del turno es la continuación de la herramienta
    if contiene_importe(parrafo) or _RE_HABLA_DE_PRECIO.search(n):
        return False  # del precio ya se ocupó la herramienta
    # (Hoy todo anuncio de cotización nombra «cotización» o «presupuesto» y ya cae en la línea
    # de arriba; el control queda escrito por si esa lista de palabras cambia.)
    if anuncia_cotizacion_sin_accion(n) or contiene_registro_interno(parrafo):
        return False
    # Pedir que elija entre envío y taller es una pregunta aunque no lleve el signo.
    oraciones = [_normalizar_faq(parrafo[a:b]) for a, b in _tramos(parrafo)]
    return not any(_es_pregunta_de_modalidad(oraciones, i) for i in range(len(oraciones)))


def _repite_continuacion(parrafo: str, continuacion: str) -> bool:
    """El párrafo copia la continuación de la herramienta o pide lo mismo con otras palabras."""
    if not _plano(continuacion):
        return False
    partes = [continuacion] + [continuacion[a:b] for a, b in _tramos(continuacion)]
    planas = [f" {_plano(p)} " for p in partes]
    raices = [_raices(p) for p in partes]
    for a, b in _tramos(parrafo):
        oracion = parrafo[a:b]
        plana, propias = f" {_plano(oracion)} ", _raices(oracion)
        if len(plana.split()) >= 4 and plana in planas[0]:
            return True  # copió un tramo de la continuación
        if any(len(p.split()) >= 3 and p in plana for p in planas):
            return True  # copió la continuación adentro de otra frase
        if any(len(propias & r) >= 2 and _parecido(propias, r) >= 0.6 for r in raices):
            return True  # casi las mismas palabras
        if _RE_PIDE_DATO.search(_sin_marcas(oracion).lower()) and len(propias & raices[0]) >= 2:
            return True  # pide el mismo dato de otra forma
    return False


def _sin_faq_repetida(parrafo: str, canonicas: frozenset, productos: frozenset):
    """El párrafo sin las frases que ya salen en su forma canónica; None si trae la frase fija de otro producto."""
    partes = _RE_CORTE_FAQ.split(parrafo)
    piezas, separadores = partes[0::2], partes[1::2]
    for k, pieza in enumerate(piezas):
        frase = re.sub(r"[.!?]+\Z", "", _normalizar_faq(re.sub(r"\bAv\.", "Av", pieza, flags=_A)))
        reglas = [r for r in _REGLAS_FAQ if r[2].search(frase)]
        if any(r[3] in canonicas for r in reglas):
            piezas[k] = None  # ya sale en su forma canónica
        elif reglas and productos and all(r[1] and r[1] not in productos for r in reglas):
            return None  # frase fija de otro producto: se sigue sin mandar
    return _trim(_unir(piezas, separadores)) if None in piezas else parrafo


def _parrafos_de_respuesta(raw: str, resultado: dict, faq: str) -> list:
    """Los párrafos del modelo que son una respuesta y pueden salir antes de la continuación.

    `resultado` es el de buscar_precio y `faq` lo que preservar_faq ya emite en forma canónica.
    """
    continuacion = _js_str(_get(resultado, "continuacion_obligatoria"))
    canonicas = frozenset(faq.split("\n\n")) - {""}
    items = _get(resultado, "items")
    productos = frozenset(
        p for p in (_get(i, "producto") for i in (items if isinstance(items, list) else [])) if isinstance(p, str)
    )
    salida = []
    for parrafo in (_trim(x) for x in _RE_PARRAFOS.split(raw)):
        if not parrafo or not _es_respuesta(parrafo) or _repite_continuacion(parrafo, continuacion):
            continue
        parrafo = _sin_faq_repetida(parrafo, canonicas, productos)
        if parrafo:
            salida.append(parrafo)
    return salida


# Campaña de multimedia del 21/11. Las oraciones del cliente (el grupo guarda si cerró con «?»),
# sus cláusulas, las palabras con las que pregunta o pide algo y las que hablan del precio.
_RE_ORACION_CLIENTE = re.compile(r"(\?+)|[.!\n;]+")
_RE_CLAUSULA_CLIENTE = re.compile(r",|\s+y\s+")
_RE_PIDE_O_PREGUNTA = re.compile(
    r"\b(?:cual(?:es)?|cuando|donde|cuanto|cuantos|tienen|tenes|hacen|pueden|incluye|decime|contame|pasame|"
    r"avisame|mostrame|mandame|explicame|saber)\b",
    _A,
)
_RE_PRECIO_DEL_CLIENTE = re.compile(
    r"\b(?:precios?|valor(?:es)?|cotiz[a-z]*|presupuest[a-z]*|total(?:es)?|salen?|saldrian?|cuestan?|cuotas?|"
    r"descuentos?)\b"
    # «cuánto tardan?» no pregunta el precio.
    r"|\bcuanto\b(?!\s+(?:tiempo\b|(?:se\s+)?(?:tard|demor|lleg|falta|esper)))",
    _A,
)


def _pregunto_otra_cosa(texto_cliente) -> bool:
    """El cliente preguntó o pidió algo además del precio (colocación, demora, logo, fotos…)."""
    if not isinstance(texto_cliente, str):
        return False
    plano = "".join(
        c for c in unicodedata.normalize("NFD", texto_cliente.lower()) if unicodedata.category(c) != "Mn"
    )
    partes = _RE_ORACION_CLIENTE.split(plano)
    for i in range(0, len(partes), 2):
        cerro_con_pregunta = i + 1 < len(partes) and bool(partes[i + 1])
        clausulas = [c.strip() for c in _RE_CLAUSULA_CLIENTE.split(partes[i] or "") if c and c.strip()]
        for k, clausula in enumerate(clausulas):
            # El signo de pregunta vale para la última cláusula: «tengo una Toro, …, cuánto sale?».
            pregunta = (
                (cerro_con_pregunta and k == len(clausulas) - 1)
                or "¿" in clausula
                or bool(_RE_PIDE_O_PREGUNTA.search(clausula))
            )
            if pregunta and not _RE_PRECIO_DEL_CLIENTE.search(clausula):
                return True
    return False


_ESTADOS_DERIVACION = ("pendiente_asignacion", "parcial", "fallido", "desconocido", "simulado", "entrada_invalida")
_ESTADOS_PRECIO = (
    "cotizado", "parcial", "requiere_aclaracion", "no_disponible", "entrada_invalida",
    "error_consulta", "requiere_modalidad", "metodo_no_confirmado", "metodo_no_disponible",
)
_ESTADOS_ENVIO_PRECIO = ("aceptado", "omitido", "fallido", "desconocido", "simulado", "no_corresponde")
# Corrección del 20/11 (campaña de pruebas): con estos envíos vale el pase que pide buscar_precio.
_ENVIOS_CON_PASE = ("no_corresponde", "aceptado", "omitido")
_HERRAMIENTAS = ("derivar_humano", "buscar_precio", "enviar_multimedia")


def controlar_salida_comercial(agente: dict | None = None, texto_cliente="") -> dict:
    """controlarSalidaComercial (nodo «Controlar salida comercial»). Ver el docstring del módulo."""
    agente = agente if isinstance(agente, dict) else {}
    raw = agente.get("output") if isinstance(agente.get("output"), str) else ""
    pasos = agente.get("intermediateSteps") if isinstance(agente.get("intermediateSteps"), list) else []
    observaciones = []
    for p in pasos:
        tool = _get(_get(p, "action"), "tool")
        if _en(tool, _HERRAMIENTAS):
            obs = p.get("observation", UNDEF)
            observaciones.append({"tool": tool, "valor": observacion_unica(obs)})

    def responder(output, motivo, requiere_derivacion=False, extra=None):
        extra = extra or {}
        salida = {
            "output": output,
            "requiere_derivacion": requiere_derivacion,
            "bot_pausado": extra.get("bot_pausado") is True,
        }
        if _truthy(extra.get("estado", UNDEF)):
            salida["estado"] = extra["estado"]
        control = {
            "motivo": motivo,
            "modificada": output != raw,
            "importe_modelo_bloqueado": contiene_importe(raw),
            "resultado_incierto": False,
            "faq_pendientes": [],
            "faq_preservadas": [],
        }
        control.update(extra)
        salida["control_salida"] = control
        return salida

    def es_pausa(v):
        return (
            _get(v, "bot_pausado") is True
            or _get(_get(v, "envio"), "estado") == "control_humano"
            or _en(_get(v, "estado"), ("derivado", "control_humano"))
        )

    pausa = next((o for o in observaciones if es_pausa(o["valor"])), None)
    if pausa:
        estado = _get(pausa["valor"], "estado")
        return responder("", "control_humano", False, {"bot_pausado": True, "estado": "control_humano" if _nulo(estado) else estado})

    humano = [o for o in observaciones if o["tool"] == "derivar_humano"]
    if humano:
        r = humano[-1]["valor"]
        valido = bool(r) and _en(_get(r, "estado"), _ESTADOS_DERIVACION) and isinstance(_get(r, "continuacion_obligatoria"), str)
        estado = _get(r, "estado")
        return responder(
            r["continuacion_obligatoria"] if valido else TEXTO_PASE_NO_CONFIRMADO,
            "resultado_derivacion",
            False,
            {"resultado_incierto": (not valido) or r["estado"] != "simulado", "estado": "desconocido" if _nulo(estado) else estado},
        )

    precios = [o for o in observaciones if o["tool"] == "buscar_precio"]
    ultimo_precio = precios[-1]["valor"] if precios else None
    # Corrección del 20/11 (campaña de pruebas): la herramienta puede pedir el pase a
    # Candela con cualquier estado (antes solo con metodo_no_confirmado y sin envío).
    if (
        _get(ultimo_precio, "requiere_derivacion") == "revision_especial"
        and _en(_get(_get(ultimo_precio, "envio"), "estado"), _ENVIOS_CON_PASE)
    ):
        return responder("", "revision_especial", True)

    solicitud = solicitud_humana_explicita(texto_cliente)
    if solicitud:
        return responder("", "solicitud_humana_no_atendida", True, {"solicitud_humana_detectada": solicitud})

    if precios:
        r = precios[-1]["valor"]
        if (
            r
            and _en(_get(r, "estado"), _ESTADOS_PRECIO)
            and _en(_get(_get(r, "envio"), "estado"), _ESTADOS_ENVIO_PRECIO)
            and isinstance(_get(r, "continuacion_obligatoria"), str)
        ):
            faq = preservar_faq(raw, texto_cliente, r)
            texto = faq.pop("texto")
            # Corrección del 20/11 (campaña de pruebas): lo que el modelo le contestó al cliente
            # sobre otra cosa sale antes de la continuación (antes se descartaba).
            # Campaña de multimedia del 21/11: solo si el cliente preguntó otra cosa además del
            # precio. Sin eso salía relleno del modelo («No tengo nada más para agregar por ahora»).
            respuestas = _parrafos_de_respuesta(raw, r, texto) if _pregunto_otra_cosa(texto_cliente) else []
            salida = responder(
                "\n\n".join(x for x in (texto, *respuestas, r["continuacion_obligatoria"]) if x),
                "continuacion_de_herramienta",
                False,
                {**faq, "resultado_incierto": r["envio"]["estado"] in ("fallido", "desconocido") or r["estado"] == "error_consulta"},
            )
            memoria = memoria_cotizacion_confirmada(r)
            if memoria:
                salida["memoria_output"] = "\n\n".join(x for x in (salida["output"], memoria) if x)
            return salida
        return responder(TEXTO_PRECIO_SIN_CONTRATO, "precio_sin_contrato", False, {"resultado_incierto": True})

    if contiene_registro_interno(raw):
        return responder("", "registro_interno_no_publicable", True)
    if contiene_importe(raw):
        return responder("", "importe_sin_herramienta", True)
    n = _sin_marcas(raw).lower()
    if anuncia_cotizacion_sin_accion(n):
        return responder("", "cotizacion_sin_accion", True)
    return responder(raw, "texto_sin_importes")


def requiere_revision_comercial(salida: dict) -> bool:
    """Nodo «Requiere revision comercial?»: True = derivar con revision_especial."""
    return isinstance(salida, dict) and salida.get("requiere_derivacion") is True


def salida_comercial_confirmada(dato: dict, raw, texto_cliente="") -> dict:
    """Nodo «Salida comercial confirmada»: segunda pasada después de la derivación automática.

    `dato` es la salida del control (si no hubo que derivar) o el resultado de
    `derivar_humano` llamado por el control. `raw` es la salida cruda del modelo.
    """
    if isinstance(dato, dict) and _truthy(dato.get("control_salida", UNDEF)) and isinstance(dato.get("output"), str):
        return dato
    resultado = controlar_salida_comercial(
        {"output": raw, "intermediateSteps": [{"action": {"tool": "derivar_humano"}, "observation": dato}]},
        texto_cliente=texto_cliente,
    )
    resultado["control_salida"]["origen"] = "revision_deterministica"
    return resultado


def texto_para_memoria(final: dict, raw) -> str:
    """La salida segura que reemplaza a la cruda en la memoria (memoria_output ?? output)."""
    segura = final.get("memoria_output")
    if segura is None:
        segura = final.get("output")
    if not isinstance(raw, str) or not isinstance(segura, str):
        raise ErrorDeSalida("Datos de memoria no verificables")
    return segura


def reparar_memoria_comercial(ultimo_ai, raw: str, segura: str) -> dict:
    """La consulta de «Reparar memoria comercial», sin Postgres.

    `ultimo_ai` es el contenido del último mensaje `ai` de la sesión (None si
    no hay o no es texto). Devuelve memoria_confirmada, estado_memoria y
    `contenido`: cómo tiene que quedar ese último mensaje `ai`.
    """
    if raw == segura:
        return {"memoria_confirmada": True, "estado_memoria": "sin_cambio", "contenido": ultimo_ai}
    if isinstance(ultimo_ai, str) and ultimo_ai == raw:
        return {"memoria_confirmada": True, "estado_memoria": "actualizada", "contenido": segura}
    if isinstance(ultimo_ai, str) and ultimo_ai == segura:
        return {"memoria_confirmada": True, "estado_memoria": "ya_corregida", "contenido": ultimo_ai}
    return {"memoria_confirmada": False, "estado_memoria": "no_verificable", "contenido": ultimo_ai}


def verificar_memoria_comercial(final: dict, memoria: dict) -> dict:
    """Nodo «Verificar memoria comercial»: sin memoria confirmada, el turno no responde."""
    if memoria.get("memoria_confirmada") is not True:
        raise ErrorDeSalida("No se pudo verificar la memoria comercial")
    return {**final, "memoria_comercial": memoria}
