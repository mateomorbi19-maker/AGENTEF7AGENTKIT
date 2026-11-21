"""El prompt de F7 que se arma en cada turno, como «Clasificar y Ensamblar» en n8n.

Port de clasificarFase, resumirMultimedia y ensamblarPrompt del nodo
«Clasificar y Ensamblar» de referencia-f7/n8n/agente-principal-unificado.json
(iguales a referencia-f7/logica/prompt-f7/ensamblar.mjs). Los bloques salen de
prompts/f7/SYSTEM_PROMPT_F7_V1.md y los metadatos de las piezas, del catálogo
de multimedia. El prompt sale idéntico byte a byte al de n8n.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .precios.motor import trabajo_sin_butacas

PROMPT_VERSION = "f7-brief-2026-11-05.v9.4-medios-pago-total"

RUTA_PROMPT = Path(__file__).resolve().parents[3] / "prompts" / "f7" / "SYSTEM_PROMPT_F7_V1.md"
RUTA_CATALOGO = Path(__file__).resolve().parent / "multimedia" / "catalogo.json"

FASE_A_BLOQUES: dict[str, list[str]] = {
    "inicio": ["base", "recorrido", "conocimiento", "inicio", "errores", "decision"],
    "multimedia": ["base", "recorrido", "conocimiento", "multimedia", "errores", "decision"],
    "cotizacion": ["base", "recorrido", "conocimiento", "cotizacion", "errores", "decision"],
    "candela": ["base", "recorrido", "conocimiento", "candela", "errores", "decision"],
    "objeciones": ["base", "recorrido", "conocimiento", "objeciones", "errores", "decision"],
    "seguimiento": ["base", "recorrido", "conocimiento", "seguimiento", "errores", "decision"],
}

_WS = "\t\n\x0b\x0c\r \xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
_WS_CHARS = frozenset(
    "\t\n\x0b\x0c\r \xa0\u1680\u2028\u2029\u202f\u205f\u3000\ufeff"
    + "".join(chr(c) for c in range(0x2000, 0x200B))
)
_DOT = r"[^\n\r\u2028\u2029]"
_A = re.ASCII
_DIACRITICOS = re.compile("[\u0300-\u036f]")

# Mismas regex y mismo orden que clasificarFase («.» de JS no cruza saltos de línea).
_F_CANDELA = re.compile(
    r"\b(alias|comprobante|sene|pagado|pague|reintegro|reclamo|candela|humano|persona|alguien|operador|turno)\b"
    r"|quiero (?:comprar|encargar|reservar)|(?:pagar|abonar) (?:ahora|ya)\b|quien" + _DOT
    + r"*(?:ver|revisar|confirmar|atender)|no llego|pedido" + _DOT + r"*(?:estado|seguimiento)"
    # Prueba del 21/11 (R20): pedir un día para ir es pedir turno, aunque no diga «turno».
    r"|\bpuedo (?:ir|pasar|llevar\w*)\b[^.?!\n]*\b(?:hoy|manana|lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b"
    r"|\bcuando puedo (?:ir|pasar|llevar\w*)\b|\bque dias? puedo\b",
    _A,
)
_F_MEDIO = re.compile(r"\b(efectivo|transferencia|tarjeta|credito|debito|cuotas?)\b", _A)
_F_PREGUNTA_PRECIO = re.compile(r"\b(cuanto|precio\w*|valor|sale|salen|cuesta|cuestan|menos|descuento)\b", _A)
_F_DESCUENTO = re.compile(r"\bdescuento\b|quiero pagar", _A)
_F_OBJECIONES = re.compile(
    r"\b(caro|cara|costoso|desconfio)\b|sin senar|sin sena|antes de senar|ver" + _DOT + r"*persona"
    # Prueba del 21/11 (R14): «es carísimo, en Mercado Libre las consigo a…» no traía la respuesta
    # del guion. Precio alto, comparación con otro vendedor y dudas para señar.
    r"|\b(?:car[oa]s|carisim[oa]s?|costos[oa]s?|mucha plata|muy salad[oa]s?)\b"
    r"|\ben otros? (?:lados?|lugar(?:es)?|local(?:es)?|negocios?)\b|\bme cobran\b|\b(?:lo|la|los|las) consigo\b"
    r"|\bsin ver\b|\bconfiables?\b|\bestafa\w*|\btengo miedo\b",
    _A,
)
_F_MULTIMEDIA = re.compile(
    r"\b(foto\w*|video\w*|catalogo|disenos?|colores?|comparacion|diferencia\w*|mostra\w*|muestr\w*)\b", _A
)
_F_COTIZACION = re.compile(
    r"\b(precio\w*|valor|cuanto|cuotas?|transferencia|efectivo|tarjeta|credito|debito|pago\w*|total)\b", _A
)
_F_INICIO = re.compile(
    r"^(hola|buenas|buen(?:os)? dias?|buenas tardes|buenas noches|quiero (?:info|informacion))[!?." + _WS + r"]*\Z",
    _A,
)
_MARCADOR = re.compile(r"<!-- BLOQUE ([a-z_]+) -->")

# Corrección del 20/11 (campaña de pruebas): el paso 1 bis del recorrido (retapizar
# o «tipo tapizado»). Con «precio de fundas tipo tapizado para una Hilux» el modelo
# lo salteó: ahora el prompt del turno avisa cuando la pregunta está pendiente.
AVISO_PASO_1BIS = "PASO 1 BIS PENDIENTE"
# El trabajo pedido con su verbo o su nombre: retapizar, tapizar, tapizan, tapicería, «tipo tapizado».
_RX_PIDE_TAPIZAR = re.compile(
    r"\bretapi[zc]\w*|\btapi[zc](?:ar\w*|an|en|as|o|amos|eria|ero)\b|\btipo\s+tapizados?\b", _A
)
# «cambiar el tapizado», «renovar mi tapizado».
_RX_CAMBIAR_TAPIZADO = re.compile(r"\b(?:cambi|renov|rehac|restaur|arregl|repar|hac)\w*\s+(?:[a-z]+\s+)?tapizados?\b", _A)
# El sustantivo suelto («hacen tapizados?», «precio de tapizado») es un pedido, salvo que nombre
# el tapizado que ya tiene el auto («q no destruyan el tapizado», «cuidar mi tapizado»).
_RX_TAPIZADO_NOMBRE = re.compile(r"(?:\b([a-z]+)\s+)?\btapizados?\b", _A)
_RX_BUTACAS = re.compile(r"\b(?:butacas?|asientos?)\b", _A)
_TAPIZADO_QUE_YA_TIENE = frozenset(
    "el mi su tu del al los mis sus tus este ese tengo tiene tienen con sin nuestro".split()
)
# Prueba del 21/11 (R13): «quiero cambiarle el tapizado» ya contesta la pregunta del paso 1 bis.
_RX_ELIGE_TAPICERIA = re.compile(
    r"\b(?:cambi|renov|rehac)\w*\s+(?:(?:todo|completo)\s+)?(?:(?:el|los|mi|mis|su)\s+)?tapizados?\b"
    r"|\btapizados?\s+nuevos?\b",
    _A,
)
_RX_NO_QUIERE_FUNDAS = re.compile(r"\bno\s+(?:quiero|busco|me\s+interesan)\s+(?:(?:las?|unas?)\s+)?fundas?\b", _A)
_RX_FUNDAS = re.compile(r"\bfundas?\b", _A)


def ya_eligio_tapiceria(texto: object) -> bool:
    """¿El lote ya dice que quiere cambiar el tapizado, y no fundas? «Retapizar» solo no alcanza."""
    t = "" if texto is None else (texto if isinstance(texto, str) else str(texto))
    t = _DIACRITICOS.sub("", unicodedata.normalize("NFD", t)).lower()
    if _RX_NO_QUIERE_FUNDAS.search(t):
        return True
    return bool(_RX_ELIGE_TAPICERIA.search(t)) and not _RX_FUNDAS.search(t)


_RX_PASO_1BIS = re.compile(r"^1 bis\.(.*?)^2\. ", re.S | re.M)
_RX_FRASE_EN_LINEA = re.compile(r"^«([^«»]+)»", re.M)


def nombra_tapizado(texto: object) -> bool:
    """¿El lote pide tapizar, retapizar, un tapizado o tapicería?

    Nombrar el tapizado que ya tiene el auto para cuidarlo con fundas no cuenta (re-prueba del
    20/11: el aviso saltó con «q no destruyan el tapizado»).
    """
    t = "" if texto is None else (texto if isinstance(texto, str) else str(texto))
    t = _DIACRITICOS.sub("", unicodedata.normalize("NFD", t)).lower()
    # Un techo, unos paneles de puerta o el volante no son tapicería de butacas (re-prueba, C19).
    if trabajo_sin_butacas({"producto": "tapiceria", "configuracion": t}) and not _RX_BUTACAS.search(t):
        return False
    # Campaña de multimedia del 21/11: decir que van por encima o que cubren ya lo aclara, y si
    # pregunta la diferencia entre las dos fundas va el video comparativo (decisión de Mateo).
    if _RX_YA_DIJO_FUNDAS.search(t):
        return False
    if _RX_COMPARA_FUNDAS.search(t) and not _RX_VERBO_TAPIZAR.search(t):
        return False
    if _RX_PIDE_TAPIZAR.search(t) or _RX_CAMBIAR_TAPIZADO.search(t):
        return True
    return any(m.group(1) not in _TAPIZADO_QUE_YA_TIENE for m in _RX_TAPIZADO_NOMBRE.finditer(t))


# Campaña de multimedia del 21/11.
_RX_COMPARA_FUNDAS = re.compile(
    r"\b(?:diferencia\w*|comparacion|compar[ae]\w*|cual\s+(?:me\s+)?conviene|cual\s+es\s+mejor|estoy\s+entre|"
    r"dudo\s+entre|no\s+se\s+cual)\b",
    _A,
)
_RX_YA_DIJO_FUNDAS = re.compile(r"\bpor\s+encima\b|\bque\s+cubr\w+|\bpara\s+cubrir\b|\bproteg\w+", _A)
_RX_VERBO_TAPIZAR = re.compile(r"\bretapi[zc]\w*|\btapi[zc](?:ar\w*|an|en|as|o|amos|eria|ero)\b", _A)
_RX_PIDE_FOTOS = re.compile(r"\b(?:fotos?|fotitos?|imagen(?:es)?)\b", _A)
_RX_PIDE_VIDEO = re.compile(r"\bvideos?\b", _A)
# «videos no puedo ver» vale para toda la charla; «no pude abrir el video» es un pedido de reenvío.
_RX_SIN_VIDEO = re.compile(
    r"\bvideos?\s+no\s+puedo\b|\bno\s+puedo\s+ver\s+videos\b|\bsin\s+videos?\b|\bsolo\s+fotos?\b"
    r"|\bfotos?\s+(?:nomas|solamente)\b|\bnada\s+de\s+videos?\b",
    _A,
)
_RX_PIDE_REENVIO = re.compile(
    r"\b(?:de\s+nuevo|otra\s+vez|nuevamente|reenvi\w+|volve\w*\s+a\s+(?:mandar|pasar|enviar)\w*)\b"
    r"|\bno\s+(?:me\s+)?(?:carg[oa]\w*|lleg[oa]\w*|abr[ei]\w*|anda\b|se\s+ve\b)"
    r"|\bno\s+(?:lo|la|los|las)\s+(?:pude|puedo|veo)\b|\bse\s+me\s+borr\w+",
    _A,
)
# «mandame el video» pide que se lo manden; «se ve en algún video?» solo lo nombra.
_RX_PIDE_ENVIO = re.compile(
    r"\b(?:mand|pas|envi|mostr|compart|reenvi)\w*\b[^.?!]*\b(?:videos?|fotos?|fotitos?|imagen(?:es)?|material)\b"
    r"|\bquiero\s+ver\b",
    _A,
)
_RX_CATALOGO = re.compile(r"Catálogo:\s*(https?://[^\s;]+)")
_RX_PIDE_PRECIO = re.compile(r"\b(?:cuanto|precios?|valor|sale|salen|cuesta|cuestan|cotizacion|presupuesto)\b", _A)


def _sin_tildes(texto: object) -> str:
    t = "" if texto is None else (texto if isinstance(texto, str) else str(texto))
    return _DIACRITICOS.sub("", unicodedata.normalize("NFD", t)).lower()


def pedido_de_material(texto: object, historial_humano=()) -> dict:
    """Qué pide el cliente en este lote: fotos, video o que le reenvíen lo que ya tiene.

    `sin_video` mira también los mensajes anteriores: si avisó que no puede ver videos, vale
    para toda la conversación. Pedir de nuevo el precio no es pedir de nuevo el material.
    """
    t = _sin_tildes(texto)
    previos = [_sin_tildes(m) for m in historial_humano if isinstance(m, str)]
    return {
        "fotos": bool(_RX_PIDE_FOTOS.search(t)),
        "video": bool(_RX_PIDE_VIDEO.search(t)),
        "reenvio": bool(_RX_PIDE_REENVIO.search(t)) and not _RX_PIDE_PRECIO.search(t),
        "pide_envio": bool(_RX_PIDE_ENVIO.search(t)),
        "sin_video": any(_RX_SIN_VIDEO.search(m) for m in [*previos, t]),
    }


_RX_FRASE_CITADA = re.compile(r"«([^«»\n]+)»")


_RX_UBICACION_HORARIO = re.compile(r"Ubicación/horario al consultarlo:\n((?:«[^«»\n]+»\n?)+)")


def frases_de_ubicacion_y_horario(bloques: dict[str, str]) -> list[tuple[str, str]]:
    """Las frases fijas del guion para la dirección y el horario, en su orden: (tipo, frase)."""
    for texto in bloques.values():
        m = _RX_UBICACION_HORARIO.search(texto or "")
        if m:
            return [("horario" if " hs" in f else "ubicacion", f) for f in _RX_FRASE_EN_LINEA.findall(m.group(1))]
    return []


def catalogo_del_guion(bloques: dict[str, str]) -> str | None:
    """El link del catálogo, tal como está en el guion."""
    for texto in bloques.values():
        m = _RX_CATALOGO.search(texto or "")
        if m:
            return m.group(1)
    return None


def frases_del_guion(bloques: dict[str, str]) -> list[str]:
    """Las frases citadas del guion, de una línea y de cuatro palabras o más.

    Re-prueba de multimedia del 21/11: sirven para que una frase copiada con tildes o signos
    agregados salga como está escrita en el guion.
    """
    frases = []
    for texto in bloques.values():
        for frase in _RX_FRASE_CITADA.findall(texto or ""):
            frase = _js_trim(frase)
            if len(frase.split()) >= 4 and frase not in frases:
                frases.append(frase)
    return frases


def frases_paso_1bis(bloques: dict[str, str]) -> list[str]:
    """Las frases literales del paso 1 bis, en orden: la pregunta, el taller y las fundas.

    Salen del prompt y no están copiadas acá, para que sigan valiendo si Mateo las
    vuelve a redactar. Son las líneas que arrancan con «» dentro del párrafo «1 bis.».
    """
    parrafo = _RX_PASO_1BIS.search(bloques.get("recorrido") or "")
    if not parrafo:
        return []
    return [_js_trim(f).lstrip("¿") for f in _RX_FRASE_EN_LINEA.findall(parrafo.group(1))]


def _js_trim(s: str) -> str:
    inicio, fin = 0, len(s)
    while inicio < fin and s[inicio] in _WS_CHARS:
        inicio += 1
    while fin > inicio and s[fin - 1] in _WS_CHARS:
        fin -= 1
    return s[inicio:fin]


def clasificar_fase(texto: object) -> str:
    """La fase orientativa del lote: candela, cotizacion, objeciones, multimedia, inicio o seguimiento."""
    t = "" if texto is None else (texto if isinstance(texto, str) else str(texto))
    t = _DIACRITICOS.sub("", unicodedata.normalize("NFD", t)).lower()
    if _F_CANDELA.search(t):
        return "candela"
    if _F_MEDIO.search(t) and _F_PREGUNTA_PRECIO.search(t):
        return "cotizacion"
    if _F_DESCUENTO.search(t):
        return "candela"
    if _F_OBJECIONES.search(t):
        return "objeciones"
    if _F_MULTIMEDIA.search(t):
        return "multimedia"
    if _F_COTIZACION.search(t):
        return "cotizacion"
    if _F_INICIO.search(_js_trim(t)):
        return "inicio"
    return "seguimiento"


def leer_bloques(ruta: Path | str = RUTA_PROMPT) -> dict[str, str]:
    """Lee los bloques del prompt, partidos por <!-- BLOQUE nombre --> y con trim.

    Falla (ValueError) si un bloque está repetido o si falta uno que usa alguna fase.
    """
    documento = Path(ruta).read_bytes().decode("utf-8")
    partes = _MARCADOR.split(documento)
    bloques: dict[str, str] = {}
    for i in range(1, len(partes), 2):
        if partes[i] in bloques:
            raise ValueError(f"Bloque duplicado: {partes[i]}")
        bloques[partes[i]] = _js_trim(partes[i + 1])
    for clave in dict.fromkeys(k for usados in FASE_A_BLOQUES.values() for k in usados):
        if not bloques.get(clave):
            raise ValueError(f"Falta bloque de prompt: {clave}")
    return bloques


def leer_metadatos_catalogo(ruta: Path | str = RUTA_CATALOGO) -> dict[str, dict]:
    """Las piezas habilitadas del catálogo: id → version, titulo, productos, formato y contenidos."""
    catalogo = json.loads(Path(ruta).read_bytes().decode("utf-8"))
    metadatos: dict[str, dict] = {}
    for a in catalogo["assets"]:
        if not a.get("habilitado"):
            continue
        contenidos = [
            r["contenido"]
            for r in catalogo["rutas"]
            if any(a["id"] in o["asset_ids"] for o in r["opciones"])
        ]
        metadatos[a["id"]] = {
            "version": a.get("version"),
            "titulo": a.get("titulo"),
            "productos": a.get("productos_visibles"),
            "formato": a.get("formato"),
            "contenidos": list(dict.fromkeys(contenidos)),
        }
    return metadatos


def _igual_js(a: object, b: object) -> bool:
    """=== de JS para los valores de un JSON (sin confundir 1, 1.0 y true)."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    return type(a) is type(b) and isinstance(a, (str, type(None))) and a == b


def ultimo_material(registros: object, metadatos: dict) -> list[dict]:
    """Las piezas del último envío de fotos o videos, en el orden en que salieron.

    Las filas vienen de la más reciente a la más vieja; las que salieron juntas comparten `lote`.
    """
    if not isinstance(registros, list):
        return []
    filas = [r for r in registros
             if isinstance(r, dict) and r.get("aceptado") is True and r.get("asset_id") in metadatos]
    if not filas:
        return []
    lote = filas[0].get("lote")
    juntas = [filas[0]]
    for fila in filas[1:]:
        if lote is None or fila.get("lote") != lote:
            break
        juntas.append(fila)
    return [metadatos[f["asset_id"]] for f in reversed(juntas)]


def _aviso_de_reenvio(registros: object, metadatos: dict) -> str:
    """El renglón del contexto para cuando el cliente pide que le manden algo otra vez."""
    aviso = ("- PEDIDO DE REENVÍO: el cliente dice que no pudo ver o abrir algo que ya recibió, o lo pide otra "
             "vez. Lo que no carga o no se abre es una foto o un video, no un mensaje de texto. ")
    ultimo = ultimo_material(registros, metadatos)
    if ultimo:
        titulos = ", ".join(f"«{p['titulo']}»" for p in ultimo)
        productos = ", ".join(dict.fromkeys(x for p in ultimo for x in p["productos"]))
        aviso += (f"Lo último que se le mandó fue {titulos} (material de {productos}; los títulos son internos). "
                  "Si no nombra otra cosa, reenviale eso en este turno con enviar_multimedia y "
                  "reenvio_solicitado true. ")
    else:
        aviso += "Si fue una foto o un video, reenviáselo con enviar_multimedia y reenvio_solicitado true. "
    return aviso + "No lo derives por esto ni le digas que busque más arriba."


def resumir_multimedia(registros: object, metadatos: dict) -> list[dict]:
    """Las piezas ya mandadas o inciertas, una por pieza, con la versión vigente del catálogo."""
    if not isinstance(registros, list):
        return []
    usados: set[str] = set()
    salida: list[dict] = []
    for r in registros[:60]:
        if not isinstance(r, dict) or not isinstance(r.get("asset_id"), str) or r["asset_id"] not in metadatos:
            continue
        meta = metadatos[r["asset_id"]]
        if "version" not in r or not _igual_js(r["version"], meta["version"]) or r["asset_id"] in usados:
            continue
        aceptado = r.get("aceptado") is True
        incierto = r.get("hay_envio_incierto") is True
        if not aceptado and not incierto:
            continue
        usados.add(r["asset_id"])
        salida.append({
            "pieza": r["asset_id"],
            "titulo": meta["titulo"],
            "productos": meta["productos"],
            "contenidos": meta["contenidos"],
            "formato": meta["formato"],
            "aceptado_por_chatwoot": aceptado,
            "hay_envio_incierto": incierto,
        })
    return salida


_FECHA_ISO = re.compile(
    r"^(?:[0-9]{4}|[+-][0-9]{6})(?:-[0-9]{2}(?:-[0-9]{2})?)?"
    r"(?:T[0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?(?:Z|[+-][0-9]{2}:[0-9]{2})?)?\Z"
)


def _dias_desde_1970(anio: int, mes: int, dia: int) -> int:
    """Días del calendario gregoriano proléptico desde 1970-01-01 (como Date de JS)."""
    anio -= mes <= 2
    era = (anio if anio >= 0 else anio - 399) // 400
    yoe = anio - era * 400
    doy = (153 * (mes + (-3 if mes > 2 else 9)) + 2) // 5 + dia - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def _fecha_valida(fecha: object) -> bool:
    """Number.isFinite(Date.parse(fecha)) para fechas ISO (el formato que arma fecha_buenos_aires).

    Otros formatos que V8 también entiende cuentan como inválidos: acá solo
    llega la fecha que arma fecha_buenos_aires.
    """
    if not isinstance(fecha, str) or not _FECHA_ISO.match(fecha) or fecha.startswith("-000000"):
        return False
    m = re.match(
        r"^([+-]?[0-9]+)(?:-([0-9]{2})(?:-([0-9]{2}))?)?"
        r"(?:T([0-9]{2}):([0-9]{2})(?::([0-9]{2})(?:\.([0-9]+))?)?(?:Z|([+-])([0-9]{2}):([0-9]{2}))?)?\Z",
        fecha,
    )
    anio, mes, dia = int(m.group(1)), int(m.group(2) or 1), int(m.group(3) or 1)
    hora, minuto, seg = int(m.group(4) or 0), int(m.group(5) or 0), int(m.group(6) or 0)
    ms = int((m.group(7) or "0")[:3].ljust(3, "0"))
    if not (1 <= mes <= 12 and 1 <= dia <= 31 and minuto <= 59 and seg <= 59):
        return False
    if hora > 24 or (hora == 24 and (minuto or seg or ms)):
        return False
    desfase = 0
    if m.group(8):
        if int(m.group(9)) > 23 or int(m.group(10)) > 59:
            return False
        desfase = (int(m.group(9)) * 60 + int(m.group(10))) * (1 if m.group(8) == "+" else -1)
    total = ((_dias_desde_1970(anio, mes, dia) * 24 + hora) * 60 + minuto - desfase) * 60000 + seg * 1000 + ms
    return abs(total) <= 8_640_000_000_000_000


def ensamblar_prompt(entrada: dict, bloques: dict[str, str], fecha_actual: object, metadatos: dict | None = None) -> dict:
    """Arma el prompt del turno.

    entrada: texto (el lote), modalidad_confirmada, multimedia_registrada y
    saludo_inicial_enviado (lo que devuelve preparar_estado).
    Devuelve prompt_version, fase_detectada, bloques_usados y prompt_ensamblado.
    """
    metadatos = {} if metadatos is None else metadatos
    fase = clasificar_fase(entrada.get("texto"))
    usados = FASE_A_BLOQUES[fase]
    fecha = fecha_actual if _fecha_valida(fecha_actual) else "fecha no disponible"
    modalidad = entrada.get("modalidad_confirmada")
    modalidad = modalidad if isinstance(modalidad, str) and modalidad in ("caba", "envio") else "sin_confirmar"
    multimedia = json.dumps(
        resumir_multimedia(entrada.get("multimedia_registrada"), metadatos),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    contexto = "\n".join([
        "CONTEXTO OPERATIVO SUMINISTRADO POR EL WORKFLOW",
        f"Fecha actual en America/Argentina/Buenos_Aires: {fecha}",
        "CAPACIDADES OPERATIVAS",
        "- herramienta_disponible: enviar_multimedia",
        "- herramienta_precio_disponible: buscar_precio",
        "- derivacion_efectiva_disponible: true (derivar_humano; solo el resultado confirma pausa, asignación y aviso)",
        "- medidas_por_vehiculo_verificadas_disponibles: false",
        f"Modalidad humana: {modalidad}.",
        "- fuente_oficial_de_precios: https://docs.google.com/spreadsheets/d/1dl7hNofQp8v57h1Veodd3XqFctJxAvgAA2qXVtnE1ZU/edit (solo buscar_precio ejecuta la consulta)",
        "MULTIMEDIA REGISTRADA (datos internos, no copiar):",
        multimedia,
        "Aceptado no significa visto. No repitas sin pedido; no reintentes inciertos. Registro vacío no borra el historial.",
        "- El flujo ya envió su saludo inicial en este turno. No agregues otro saludo."
        if entrada.get("saludo_inicial_enviado") is True
        else "- No reinicies el saludo: continuá según el historial y el mensaje actual.",
        f"Fase orientativa: {fase}; manda el pedido actual y los datos del historial.",
    ])
    if fase == "candela":
        accion_final = "Gestión de compra/pago o persona: derivar_humano AHORA; consulta de precio por medio: buscar_precio."
    elif fase == "cotizacion":
        accion_final = "Precio pendiente + modelo/modalidad conocidos: buscar_precio AHORA, omitiendo anio si falta."
    else:
        accion_final = "Conservá lo respondido y no agregues requisitos; la última pregunta del bot no obliga al cliente."
    # Corrección del 20/11: el paso 1 bis pendiente va antes que cualquier otra acción.
    frases = frases_paso_1bis(bloques) if entrada.get("pregunta_tapizado_pendiente") is True else []
    if frases and ya_eligio_tapiceria(entrada.get("texto")):
        # Prueba del 21/11 (R13): se le preguntaba «cambiar tu tapizado o protegerlo con fundas?» a quien
        # acababa de escribir «quiero cambiarle el tapizado».
        contexto += (
            f"\n- {AVISO_PASO_1BIS}: el cliente ya dijo que quiere cambiar el tapizado y no fundas. No hagas "
            "la pregunta de retapizar: es tapicería. Si todavía no dijo que puede acercarse, hacé solo la "
            "pregunta del taller del paso 1 bis, tal cual."
        )
        accion_final = "Tapicería ya elegida: pregunta del taller del paso 1 bis, sin la pregunta de retapizar."
    elif frases:
        contexto += (
            f"\n- {AVISO_PASO_1BIS}: el cliente nombró tapizar o tapizado y la pregunta del paso 1 bis "
            f"todavía no se hizo en esta conversación. Hacela ahora, sola y tal cual: «{frases[0]}» "
            "Va antes de pedir el modelo, presentar, cotizar o llamar herramientas. Pedir «fundas tipo "
            "tapizado» no cuenta como aclaración. Única excepción: si ya dijo con claridad que quiere "
            "cambiar el tapizado y no fundas, seguí con la pregunta del taller del paso 1 bis."
        )
        accion_final = "Paso 1 bis pendiente: hacé solo la pregunta de tapizado, sin herramientas en este turno."
    # Campaña de multimedia del 21/11: el cliente pidió ver material y recibió la pregunta del paso
    # 1 bis. Cuando la contesta, ese pedido sigue en pie (se había perdido y salió otro producto).
    # Re-prueba del 21/11: ante «no me cargó, me lo pasás de nuevo?» el modelo pasaba a Candela.
    if entrada.get("reenvio_pedido") is True:
        contexto += "\n" + _aviso_de_reenvio(entrada.get("multimedia_registrada"), metadatos)
    pendiente = entrada.get("material_pendiente")
    if isinstance(pendiente, str) and _js_trim(pendiente):
        contexto += (
            f"\n- PEDIDO DE MATERIAL PENDIENTE: antes de la pregunta del paso 1 bis el cliente pidió ver material: "
            f"«{_js_trim(pendiente)}». Si ahora aclaró que son fundas, mandáselo en este turno con "
            "enviar_multimedia, del producto que nombró en ese mensaje (si dijo «tipo tapizado», producto "
            "tipo tapizado, no fundas)."
        )
    cuerpo = "\n\n".join(bloques.get(k) or "" for k in usados if k != "decision")
    decision = bloques.get("decision", "undefined")
    return {
        "prompt_version": PROMPT_VERSION,
        "fase_detectada": fase,
        "bloques_usados": list(usados),
        "prompt_ensamblado": cuerpo + "\n\n" + contexto + "\n\n" + decision + "\nACCIÓN FINAL: " + accion_final,
    }


def fecha_buenos_aires(ahora: datetime | None = None) -> str:
    """La hora de Buenos Aires como la da Luxon: 2026-11-15T14:03:07.123-03:00."""
    try:
        from zoneinfo import ZoneInfo

        zona = ZoneInfo("America/Argentina/Buenos_Aires")
    except Exception:  # sin datos de zonas (Windows sin tzdata): Argentina es UTC-3 fijo
        zona = timezone(timedelta(hours=-3))
    ahora = ahora or datetime.now(timezone.utc)
    return ahora.astimezone(zona).isoformat(timespec="milliseconds")


def armar_prompt_turno(entrada: dict, fecha_actual: str | None = None) -> dict:
    """Atajo: lee bloques y catálogo y ensambla con la hora actual de Buenos Aires."""
    return ensamblar_prompt(
        entrada,
        leer_bloques(),
        fecha_actual if fecha_actual is not None else fecha_buenos_aires(),
        leer_metadatos_catalogo(),
    )
