"""Lo que ve el modelo de enviar_multimedia, byte a byte.

Fuente: el nodo «enviar_multimedia» de referencia-f7/n8n/agente-principal-unificado.json
(la descripción de la herramienta y la del argumento en $fromAI). Coinciden con
referencia-f7/prompt/ENVIAR_MULTIMEDIA_F7.md y SOLICITUDES_MULTIMEDIA_F7.md.
El guion es contrato: no tocar sin aprobación de Mateo.

Desde el 21/11/2026 el modelo ve esa base con dos decisiones de Mateo encima (al final
del archivo): si piden fotos va el video, y la lista del material que existe.
"""

DESCRIPCION_BASE = "\n".join([
    'Envía fotos y videos comerciales de F7 a la conversación actual de WhatsApp, sin pie de foto ni texto adjunto. Usá esta herramienta cuando el cliente pida ver un producto, fotos, videos, diseños, colores, calidad o comparación, o cuando el recorrido comercial indique mostrar las opciones aplicables después de definir modalidad. No consulta precios, medidas, stock ni realiza derivación humana.',
    '',
    'Único argumento del modelo: `solicitudes`, un ARRAY JSON (no string, no objeto contenedor). Cada elemento tiene `producto`, `contenido` y, si corresponde, `formato`, `disenos`, `reenvio_solicitado`.',
    '',
    'COMPARACIÓN: exige DOS solicitudes en la misma llamada, una de fundas y otra de tipo tapizado, las dos con contenido comparacion. Si pide video, ambas llevan formato video. Mandar solo fundas/comparacion es entrada_invalida. Antes de invocar, comprobá que el array tenga las dos categorías.',
    '',
    '- producto: `fundas`, `tipo tapizado`, `alfombra`, `cubrevolante`. Usá estos nombres exactos; cubrevolante es singular. No existe producto `todos`.',
    '- El enum `fundas` significa exclusivamente fundas a medida. Una mención genérica del cliente a «fundas» no elige esa categoría: resolvé si quiere conocer ambas alternativas o una concreta, usando el contexto o una aclaración breve.',
    '- contenido: `presentacion`, `disenos`, `colores`, `calidad`, `comparacion`.',
    '- formato opcional: `auto` (por defecto), `foto` o `video`. Respetá un formato expresamente solicitado. Si pidió solo fotos y no existen, no mandes un video como reemplazo.',
    '- disenos opcional: solo para contenido `disenos`, array con `baston`, `vip`, `hexagonal`, `diamante`, `ultra`. Omitilo para mostrar todos los diseños del producto. No pases nombres de colores como diseños.',
    '- reenvio_solicitado opcional: true solo si pidió explícitamente volver a ver material. No fuerza reenvío de un mismo pedido ni elimina la protección de duplicados.',
    '',
    'Reuní TODOS los productos y contenidos solicitados en UNA llamada por turno. Máximo 16 solicitudes. No mandes un producto que el cliente excluyó. «Todos» se resuelve por contexto: todos los diseños de fundas no son todos los productos. Si el referente es ambiguo, aclaralo antes. Si pide los cuatro productos principales, enumeralos. Tapicería y cobertores no están disponibles en esta herramienta; no inventes un producto o uses otro para representarlos.',
    '',
    'Ejemplos de solicitudes:',
    'Solo fundas a medida: [{"producto":"fundas","contenido":"presentacion"}].',
    'Solo tipo tapizado: [{"producto":"tipo tapizado","contenido":"presentacion"}].',
    'Fundas y cubrevolante: [{"producto":"fundas","contenido":"presentacion"},{"producto":"cubrevolante","contenido":"presentacion"}].',
    'Los cuatro: [{"producto":"fundas","contenido":"presentacion"},{"producto":"tipo tapizado","contenido":"presentacion"},{"producto":"alfombra","contenido":"presentacion"},{"producto":"cubrevolante","contenido":"presentacion"}].',
    'Comparar ambas fundas en video: [{"producto":"fundas","contenido":"comparacion","formato":"video"},{"producto":"tipo tapizado","contenido":"comparacion","formato":"video"}]. La comparación necesita ambas categorías. Para mostrar solo una, usá su presentación exclusiva.',
    'Dos diseños de fundas: [{"producto":"fundas","contenido":"disenos","disenos":["baston","ultra"],"formato":"foto"}].',
    'Todos sus diseños: [{"producto":"fundas","contenido":"disenos"}].',
    'Carta de colores de fundas: [{"producto":"fundas","contenido":"colores"}].',
    '',
    'El workflow selecciona archivos y evita repetir piezas compartidas. No decidas URLs, IDs de archivo, destinatario, cuenta, modo ni identificador del pedido: esos campos los fija el flujo. Mostrar un video o una foto nunca confirma compatibilidad, disponibilidad, diseño elegido ni precio.',
    '',
    'Esperá el resultado y mirá el detalle por solicitud. `aceptados` confirma mensajes creados, no entrega/lectura; `omitidos` ya estaban aceptados en ese pedido; `simulados` no hizo envíos. Ante `faltantes` o `fallidos`, informá la parte que no se pudo compartir sin negar los aceptados. Ante `desconocidos`, no asegures éxito/fracaso y no reintentes. Ante `control_humano`, detené la atención automática. No repitas la herramienta para sortear un error o límite de tiempo. No reproduzcas títulos internos como pies de foto o mensajes separados.',
    '',
])

# Termina en salto de línea, igual que en el export.
SOLICITUDES_BASE = "\n".join([
    'Array JSON de solicitudes (no string, no objeto contenedor). Para comparar las dos fundas deben venir DOS elementos: [{"producto":"fundas","contenido":"comparacion","formato":"video"},{"producto":"tipo tapizado","contenido":"comparacion","formato":"video"}]. Una sola categoría con comparacion es inválida. Conservá foto/video según lo pedido.',
    'Cada elemento requiere producto (fundas | tipo tapizado | alfombra | cubrevolante) y contenido (presentacion | disenos | colores | calidad | comparacion). Opcionales: formato (auto | foto | video), disenos (baston | vip | hexagonal | diamante | ultra, solo con disenos), reenvio_solicitado (boolean). Para un solo producto usá presentacion, no comparacion. Para todos los diseños omití disenos; para dos diseños pasá exactamente esos dos. Agrupá todos los pedidos del turno. No incluyas cuenta, conversación, modo, IDs ni URLs.',
    '',
])


# ---------------------------------------------------------------------------
# Decisiones de Mateo del 21/11 (campaña de multimedia). La base de arriba queda como en n8n; lo
# que ve el modelo es esa base con estos cambios:
# - Si piden fotos va el video del producto y nunca se dice que no hay fotos.
# - Al final se lista el material que existe, sacado del catálogo, para que el modelo sepa qué
#   puede mandar (pasó a Candela una consulta por el respaldo rebatible teniendo ese video).
from .seleccion import CONTENIDOS, PRODUCTOS, cargar_catalogo, planificar_seleccion  # noqa: E402

_FORMATO_VIEJO = ("Respetá un formato expresamente solicitado. Si pidió solo fotos y no existen, no mandes un "
                  "video como reemplazo.")
_FORMATO_NUEVO = ("Si pide un video, usá video. Si pide fotos de un producto, pedí igual su material: cuando no hay "
                  "fotos el flujo manda el video, o las fotos de diseños si ya lo tiene. No avises el cambio, no "
                  "digas que son fotos y nunca digas que no hay fotos. Si el resultado trae `indicacion`, seguila.")
_SOLICITUDES_VIEJO = "Conservá foto/video según lo pedido."
_SOLICITUDES_NUEVO = "Si pide video, formato video."


def _piezas(catalogo: dict, solicitudes: list[dict]) -> list[dict]:
    """Las piezas del catálogo que salen para esas solicitudes."""
    plan = planificar_seleccion({"solicitudes": solicitudes, "modo": "simular", "account_id": 1,
                                 "conversation_id": 1, "solicitud_id": "cw:1:1:1:multimedia-v1"}, catalogo)
    por_id = {a["id"]: a for a in catalogo["assets"]}
    return [por_id[p["asset_id"]] for p in plan.get("plan") or []] if plan.get("ok") is True else []


def _renglon(piezas: list[dict]) -> str:
    partes = []
    for formato, uno, varios in (("video", "video", "videos"), ("foto", "foto", "fotos")):
        titulos = [f"«{p['titulo']}»" for p in piezas if p.get("formato") == formato]
        if titulos:
            partes.append(f"{varios if len(titulos) > 1 else uno} " + ", ".join(titulos))
    return " y ".join(partes)


_COMPARTIDO = {"disenos": "los diseños", "colores": "la carta de colores"}


def material_que_existe(catalogo: dict) -> str:
    """La lista, para el modelo, de lo que sale con cada pedido. Se arma del catálogo."""
    lineas = ["MATERIAL QUE EXISTE (es todo lo que se puede mandar; lo que no figura acá no existe):"]
    for producto in PRODUCTOS:
        partes = []
        for contenido in CONTENIDOS:
            piezas = [] if contenido == "comparacion" else _piezas(catalogo, [{"producto": producto, "contenido": contenido}])
            if piezas:
                partes.append(f"{contenido} = {_renglon(piezas)}")
        if partes:
            lineas.append(f"- {producto}: " + "; ".join(partes) + ".")
    comparacion = _piezas(catalogo, [{"producto": "fundas", "contenido": "comparacion"},
                                     {"producto": "tipo tapizado", "contenido": "comparacion"}])
    if comparacion:
        lineas.append(f"- comparacion de fundas y tipo tapizado (las dos solicitudes juntas): {_renglon(comparacion)}.")
    # Re-prueba del 21/11: ante «y de los diseños de las fundas?» preguntaba de cuál de las dos.
    iguales = [nombre for contenido, nombre in _COMPARTIDO.items()
               if (piezas := _piezas(catalogo, [{"producto": "fundas", "contenido": contenido}]))
               and piezas == _piezas(catalogo, [{"producto": "tipo tapizado", "contenido": contenido}])]
    if iguales:
        lineas.append(" y ".join(iguales).capitalize() + " son las mismas fotos para fundas y tipo tapizado: si "
                      "los piden, mandalos sin preguntar de cuál.")
    lineas.append("Si el cliente pregunta por algo que muestra una de estas piezas (por ejemplo, si se puede rebatir "
                  "el respaldo), mandala en vez de explicarlo o derivar. Los títulos son internos: no los copies en "
                  "el chat.")
    return "\n".join(lineas)


assert _FORMATO_VIEJO in DESCRIPCION_BASE and _SOLICITUDES_VIEJO in SOLICITUDES_BASE
DESCRIPCION_ENVIAR_MULTIMEDIA = (DESCRIPCION_BASE.replace(_FORMATO_VIEJO, _FORMATO_NUEVO)
                                 + "\n" + material_que_existe(cargar_catalogo()) + "\n")
DESCRIPCION_SOLICITUDES = SOLICITUDES_BASE.replace(_SOLICITUDES_VIEJO, _SOLICITUDES_NUEVO)
