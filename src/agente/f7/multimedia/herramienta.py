"""enviar_multimedia para la web de pruebas.

Recorre el mismo camino que el subflujo «F7 · Enviar multimedia · v1» en modo
enviar (referencia-f7/n8n/herramienta-multimedia-v1.json), con estos cambios
porque acá no hay Postgres, Drive ni Chatwoot:
- Postgres (bloqueo, huella y reserva por pieza) → contexto.sesion.registro("multimedia"),
  con la misma lógica: lo aceptado antes en la misma solicitud sale «omitido», la
  misma solicitud con otra huella se rechaza y un turno nuevo trae otra solicitud.
- Drive (descarga e integridad) → no se baja nada: la pieza se toma como válida.
- GET de la conversación → «humano» se mira en contexto.sesion.etiquetas.
- POST del adjunto → contexto.sesion.mandar("multimedia", ...), una pieza por globo,
  sin texto y sin las esperas de 2 s. El título va solo para que la web lo muestre.

Devuelve el mismo objeto que hoy recibe el modelo. Nunca levanta excepciones.
"""

from __future__ import annotations

import json
import re
import time

from agente.f7.local import ContextoTurno
from agente.f7.multimedia.descripcion import DESCRIPCION_ENVIAR_MULTIMEDIA, DESCRIPCION_SOLICITUDES
from agente.f7.multimedia.seleccion import (
    cargar_catalogo,
    es_entero_seguro,
    js_trim,
    planificar_seleccion,
    resumir_resultados,
)

NOMBRE = "enviar_multimedia"
ARGUMENTO = "solicitudes"
DESCRIPCION = DESCRIPCION_ENVIAR_MULTIMEDIA
DESCRIPCION_ARGUMENTO = DESCRIPCION_SOLICITUDES

SUFIJO_SOLICITUD = "multimedia-v1"
# Topes de n8n: 210 s para llamar a la herramienta (lo controla el principal)
# y 390 s desde que se planificó para empezar cada pieza y antes del POST.
TOPE_INICIO_SEGUNDOS = 210
TOPE_PIEZA_SEGUNDOS = 390
# «Leer Estado» trae hasta 60 piezas.
TOPE_MULTIMEDIA_REGISTRADA = 60

_RE_ID_MENSAJE = re.compile(r"[1-9][0-9]{0,31}")


def _huella(plan: dict) -> str:
    """La huella que n8n guarda en f7_multimedia_solicitudes (comparada como jsonb)."""
    return json.dumps(
        {"solicitudes": plan["solicitudes"], "plan": plan["plan"], "catalogo_version": plan["catalogo_version"]},
        ensure_ascii=False,
        sort_keys=True,
    )


def _clave_pieza(pieza: dict) -> str:
    return json.dumps([pieza["asset_id"], pieza["version"]], ensure_ascii=False)


def _registrar_resultado(fila: dict, estado: str, chatwoot_message_id, motivo) -> bool:
    """recordResult de sql.mjs: solo las transiciones permitidas."""
    if estado not in ("aceptado", "fallo_previo", "fallido", "desconocido"):
        return False
    if estado == "aceptado" and not (isinstance(chatwoot_message_id, int) and chatwoot_message_id > 0):
        return False
    permitido = (
        (fila["estado"] == "reservado" and estado == "fallo_previo")
        or (fila["estado"] == "enviando" and estado in ("aceptado", "fallido", "desconocido"))
        or (fila["estado"] == estado and fila["chatwoot_message_id"] == chatwoot_message_id)
    )
    if not permitido:
        return False
    fila["estado"] = estado
    fila["chatwoot_message_id"] = chatwoot_message_id
    fila["motivo"] = motivo[:160] if isinstance(motivo, str) else None
    return True


def _evaluar_conversacion(etiquetas) -> dict:
    """evaluarConversacion de entrega.mjs, con la conversación local (id y cuenta siempre coinciden)."""
    if not isinstance(etiquetas, list) or any(not isinstance(e, str) for e in etiquetas):
        return {"permitido": False, "estado": "fallido", "motivo": "control_humano_no_verificable"}
    if any(js_trim(e).lower() == "humano" for e in etiquetas):
        return {"permitido": False, "estado": "control_humano", "motivo": "conversacion_con_humano"}
    return {"permitido": True, "estado": "habilitado", "motivo": None}


def _vigente(contexto_plan: dict, epoca: int) -> bool:
    """«Vigencia antes de Enviar adjunto»: el pedido es posterior al último «borrar»."""
    partes = contexto_plan["solicitud_id"].split(":") if isinstance(contexto_plan.get("solicitud_id"), str) else []
    conversacion = contexto_plan.get("conversation_id")
    if (
        contexto_plan.get("account_id") != 1
        or not es_entero_seguro(conversacion)
        or conversacion <= 0
        or len(partes) != 5
        or partes[0] != "cw"
        or partes[1] != "1"
        or partes[2] != str(conversacion)
        or not _RE_ID_MENSAJE.fullmatch(partes[3])
        or not partes[4]
    ):
        # En n8n la consulta tira error y va por el camino de reinicio.
        return False
    return int(partes[3]) > int(epoca or 0)


def _anotar_para_el_prompt(sesion, pieza: dict, lote: int | None = None) -> None:
    """Lo que «Leer Estado» devolvería el turno siguiente: una fila por pieza y
    versión, la más reciente primero, hasta 60.

    `lote` es el mensaje del cliente que originó el envío: las piezas que salieron juntas lo
    comparten (sirve para saber cuál fue el último material mandado).
    """
    filas = sesion.multimedia_registrada
    previa = next(
        (f for f in filas if f.get("asset_id") == pieza["asset_id"] and f.get("version") == pieza["version"]),
        None,
    )
    incierto = bool(previa and previa.get("hay_envio_incierto"))
    if previa is not None:
        filas.remove(previa)
    filas.insert(0, {
        "asset_id": pieza["asset_id"],
        "version": pieza["version"],
        "aceptado": True,
        "hay_envio_incierto": incierto,
        "lote": lote,
    })
    del filas[TOPE_MULTIMEDIA_REGISTRADA:]


def _resultado_reinicio(confirmado: bool) -> dict:
    """«Detener herramienta por reinicio» + «Resultado de reinicio»."""
    resultado = {
        "estado": "control_humano",
        "motivo": "conversacion_reiniciada",
        "pausa_tecnica": True,
        "bot_pausado": None,
        "asignacion_confirmada": False,
        "destino": None,
        "envio": {"estado": "control_humano", "motivo": "conversacion_reiniciada", "chatwoot_message_id": None},
        "continuacion_obligatoria": "",
        "registro_confirmado": confirmado,
        "requiere_revision": not confirmado,
    }
    if not confirmado:
        resultado["advertencia"] = "cierre_de_registro_no_confirmado_no_reintentar"
    return resultado


def _resumir_interrupcion(plan: dict, resultados: list[dict], actual: dict) -> dict:
    """«Resumir interrupcion»: lo que quedó sin intentar sale control_humano o fallido."""
    todos = [*resultados, actual]
    for pieza in plan["plan"][actual["indice"] + 1:]:
        todos.append({
            "asset_id": pieza["asset_id"],
            "version": pieza["version"],
            "estado": "control_humano" if actual["estado"] == "control_humano" else "fallido",
            "motivo": "lote_detenido_sin_intentar_envio",
        })
    resumen = resumir_resultados(plan, todos)
    resumen["lote_detenido"] = True
    resumen["advertencias"] = [
        {"asset_id": r["asset_id"], "motivo": r["advertencia"]} for r in todos if r.get("advertencia")
    ]
    return resumen


def _enviar(plan: dict, contexto: ContextoTurno, inicio: float, reenviar: bool = True) -> dict:
    """El lote de «Corresponde enviar» en adelante."""
    sesion = contexto.sesion
    # Re-prueba del 21/11: sin pedido de reenvío, la pieza que el cliente ya tiene no sale otra
    # vez aunque venga mezclada con material nuevo.
    ya_las_tiene = set() if reenviar else {
        (r.get("asset_id"), r.get("version")) for r in sesion.multimedia_registrada if r.get("aceptado")}
    datos = plan["contexto"]
    registro = sesion.registro("multimedia")
    # «Registrar solicitud»: la misma solicitud_id con otra huella se rechaza entera.
    huella = _huella(plan)
    solicitud = registro.setdefault(datos["solicitud_id"], {"huella": huella, "piezas": {}})
    if solicitud["huella"] != huella:
        return resumir_resultados(plan, [
            {"asset_id": p["asset_id"], "version": p["version"], "estado": "fallido",
             "motivo": "conversacion_ocupada_o_solicitud_incompatible"}
            for p in plan["plan"]
        ])
    piezas = solicitud["piezas"]
    resultados: list[dict] = []
    for indice, pieza in enumerate(plan["plan"]):
        ident = {"asset_id": pieza["asset_id"], "version": pieza["version"], "indice": indice}
        if time.monotonic() - inicio >= TOPE_PIEZA_SEGUNDOS:
            actual = {**ident, "estado": "fallido", "motivo": "presupuesto_de_tiempo_agotado", "detener_lote": True}
            return _resumir_interrupcion(plan, resultados, actual)
        if (pieza["asset_id"], pieza["version"]) in ya_las_tiene:
            resultados.append({**ident, "estado": "omitido", "motivo": "ya_enviado_en_la_conversacion",
                               "chatwoot_message_id": None})
            continue
        # «Reservar pieza»: solo se reserva lo nuevo o lo que falló antes de enviarse.
        clave = _clave_pieza(pieza)
        fila = piezas.get(clave)
        if fila is None:
            fila = piezas[clave] = {"estado": "reservado", "chatwoot_message_id": None, "motivo": None, "intentos": 1}
        elif fila["estado"] == "fallo_previo":
            fila.update(estado="reservado", chatwoot_message_id=None, motivo=None, intentos=fila["intentos"] + 1)
        else:
            # «Resolver repeticion».
            estado = {"aceptado": "omitido", "fallido": "fallido"}.get(fila["estado"], "desconocido")
            crudo = fila["chatwoot_message_id"]
            actual = {
                **ident,
                "estado": estado,
                "chatwoot_message_id": crudo if isinstance(crudo, int) and crudo > 0 else None,
                "motivo": {
                    "omitido": "ya_aceptado_en_esta_solicitud",
                    "fallido": "rechazo_anterior_no_reintentar",
                }.get(estado, "intento_anterior_sin_conciliar"),
                "detener_lote": estado == "desconocido",
            }
            if actual["detener_lote"]:
                return _resumir_interrupcion(plan, resultados, actual)
            resultados.append(actual)
            continue
        # «Evaluar control humano».
        gate = _evaluar_conversacion(sesion.etiquetas)
        if gate["permitido"] and time.monotonic() - inicio >= TOPE_PIEZA_SEGUNDOS:
            gate = {"permitido": False, "estado": "fallido", "motivo": "presupuesto_de_tiempo_agotado"}
        if not gate["permitido"]:
            actual = {
                **ident,
                "estado": "control_humano" if gate["estado"] == "control_humano" else "fallido",
                "motivo": gate["motivo"] or "control_no_verificable",
                "estado_db": "fallo_previo",
                "detener_lote": True,
            }
            confirmado = _registrar_resultado(fila, "fallo_previo", None, actual["motivo"])
            actual.update(registro_confirmado=confirmado, advertencia=None if confirmado else "no_se_pudo_confirmar_registro_no_reintentar")
            return _resumir_interrupcion(plan, resultados, actual)
        # «Marcar inicio envio».
        fila["estado"] = "enviando"
        if time.monotonic() - inicio >= TOPE_PIEZA_SEGUNDOS:
            actual = {**ident, "estado": "fallido", "motivo": "presupuesto_de_tiempo_agotado_sin_post",
                      "estado_db": "fallido", "detener_lote": True}
            confirmado = _registrar_resultado(fila, "fallido", None, actual["motivo"])
            actual.update(registro_confirmado=confirmado, advertencia=None if confirmado else "no_se_pudo_confirmar_registro_no_reintentar")
            return _resumir_interrupcion(plan, resultados, actual)
        # Corte por «borrar» antes del POST: devuelve el objeto de reinicio.
        if not _vigente(datos, sesion.epoca):
            confirmado = _registrar_resultado(fila, "fallido", None, "conversacion_reiniciada")
            return _resultado_reinicio(confirmado)
        # El POST: un globo por pieza, sin texto.
        globo = sesion.mandar(
            "multimedia",
            "",
            asset_id=pieza["asset_id"],
            version=pieza["version"],
            formato=pieza["formato"],
            mime=pieza["mime"],
            nombre_archivo=pieza["nombre_archivo"],
            titulo=pieza["titulo"],
        )
        actual = {**ident, "estado": "aceptado", "chatwoot_message_id": globo.chatwoot_message_id,
                  "motivo": None, "estado_db": "aceptado", "detener_lote": False}
        confirmado = _registrar_resultado(fila, "aceptado", globo.chatwoot_message_id, None)
        if confirmado:
            _anotar_para_el_prompt(sesion, pieza, contexto.ultimo_message_id)
        actual.update(
            registro_confirmado=confirmado,
            detener_lote=not confirmado,
            advertencia=None if confirmado else "no_se_pudo_confirmar_registro_no_reintentar",
        )
        if actual["detener_lote"]:
            return _resumir_interrupcion(plan, resultados, actual)
        resultados.append(actual)
    return resumir_resultados(plan, resultados)


def _todo_ya_mandado(plan: list[dict], sesion) -> bool:
    """¿Todas las piezas del plan ya salieron aceptadas en esta conversación?"""
    mandadas = {(r.get("asset_id"), r.get("version")) for r in sesion.multimedia_registrada if r.get("aceptado")}
    return all((p["asset_id"], p["version"]) in mandadas for p in plan)


# Decisión de Mateo del 21/11 (campaña de multimedia): «Si pide fotos del producto se envía el
# video directamente, no se dice "No tengo fotos"». De presentación y de calidad hay solo videos.
# - Pide fotos y todavía no tiene el video: sale el video.
# - Ya lo tiene, o avisó que no puede ver videos: si el producto tiene fotos de diseños (fundas a
#   medida y tipo tapizado) salen esas; si no, no sale nada y el agente pasa el link del catálogo.
INDICACION_VIDEO = ("El cliente pidió fotos y se le mandó el video del producto, que es el material que hay. "
                    "No lo anuncies, no digas que son fotos y no digas que no hay fotos.")
INDICACION_DISENOS = ("El cliente pidió fotos y se le mandaron las fotos de diseños, que son las que hay de ese "
                      "producto. No lo anuncies y no digas que no hay otras fotos.")
INDICACION_CATALOGO = ("El cliente pidió fotos y de ese producto no hay otro material para mandarle. No digas que "
                       "no hay fotos ni reenvíes el video: pasale el link del catálogo.")
_CON_FOTOS_DE_DISENOS = ("fundas", "tipo tapizado")
_CONTENIDOS_CON_VIDEO = ("presentacion", "calidad")


def piezas_de_producto(producto: str) -> frozenset:
    """Todas las piezas del catálogo que muestran ese producto, con cualquier contenido."""
    return frozenset(
        pieza
        for ruta in cargar_catalogo().get("rutas") or [] if ruta.get("producto") == producto
        for opcion in ruta.get("opciones") or []
        for pieza in opcion.get("asset_ids") or []
    )


def _videos_de(solicitud: dict, catalogo: dict) -> list[str]:
    """Las piezas que saldrían para esa solicitud sin exigir formato."""
    plan = planificar_seleccion(
        {"solicitudes": [{**solicitud, "formato": "auto"}], "modo": "simular", "account_id": 1,
         "conversation_id": 1, "solicitud_id": "cw:1:1:1:" + SUFIJO_SOLICITUD}, catalogo)
    return [p["asset_id"] for p in plan.get("plan") or []] if plan.get("ok") is True else []


def _fotos_que_faltan(producto, mandadas: set, catalogo: dict) -> dict | None:
    """La solicitud de fotos de ese producto que el cliente todavía no tiene: diseños y después colores."""
    if producto not in _CON_FOTOS_DE_DISENOS:
        return None
    for contenido in ("disenos", "colores"):
        solicitud = {"producto": producto, "contenido": contenido, "formato": "foto"}
        piezas = _videos_de(solicitud, catalogo)
        if piezas and not all(p in mandadas for p in piezas):
            return solicitud
    return None


def _reenvio_permitido(solicitudes, contexto: ContextoTurno) -> bool:
    """¿Se puede mandar de nuevo lo que el cliente ya tiene?"""
    if not contexto.pidio_multimedia:
        return False
    if not contexto.reenvio_solo_marcado:
        return True
    return isinstance(solicitudes, list) and any(
        isinstance(s, dict) and s.get("reenvio_solicitado") is True for s in solicitudes)


def _regla_de_fotos(solicitudes, contexto: ContextoTurno, catalogo: dict):
    """Aplica la decisión del 21/11. Devuelve las solicitudes, lo que se cambió y la indicación para el agente."""
    if not isinstance(solicitudes, list):
        return solicitudes, [], None
    mandadas = {r.get("asset_id") for r in contexto.sesion.multimedia_registrada if r.get("aceptado")}
    nuevas, cambios, indicaciones = [], [], []
    for i, s in enumerate(solicitudes):
        formato = s.get("formato") if isinstance(s, dict) else None
        if not (isinstance(s, dict) and s.get("contenido") in _CONTENIDOS_CON_VIDEO):
            nuevas.append(s)
            continue
        if contexto.producto_pendiente == "tipo tapizado" and s.get("producto") == "fundas":
            # Había pedido ver el tipo tapizado antes de la pregunta del paso 1 bis: es ese video.
            s = {**s, "producto": "tipo tapizado"}
            cambios.append({"solicitud_indice": i, "pedido": "fundas", "enviado": "tipo tapizado"})
        if formato not in (None, "auto", "foto"):
            nuevas.append(s)
            continue
        videos = _videos_de(s, catalogo)
        ya_los_tiene = bool(videos) and all(v in mandadas for v in videos)
        # «y fotos no tenés? solo video?»: nombra las dos cosas, pero el video ya lo tiene.
        pide_fotos = formato == "foto" or (contexto.pidio_fotos and (not contexto.pidio_video or ya_los_tiene))
        if not pide_fotos or not videos:
            nuevas.append(s)
            continue
        if not contexto.sin_video and not ya_los_tiene:
            nuevas.append({**s, "formato": "auto"})
            enviado, indicacion = "video", INDICACION_VIDEO
        elif (fotos := _fotos_que_faltan(s.get("producto"), mandadas, catalogo)) is not None:
            nuevas.append(fotos)
            enviado = "fotos de diseños" if fotos["contenido"] == "disenos" else "carta de colores"
            indicacion = INDICACION_DISENOS
        else:
            nuevas.append({**s, "formato": "foto"})  # no hay fotos: no sale nada
            enviado, indicacion = "nada", INDICACION_CATALOGO
        if formato == "foto" or enviado != "video":
            cambios.append({"solicitud_indice": i, "pedido": "foto", "enviado": enviado})
        if indicacion not in indicaciones:
            indicaciones.append(indicacion)
    return nuevas, cambios, " ".join(indicaciones) or None


def ejecutar(solicitudes, contexto: ContextoTurno) -> dict:
    """enviar_multimedia con la decisión del 21/11 sobre los pedidos de fotos (ver `_regla_de_fotos`)."""
    try:
        solicitudes, cambios, indicacion = _regla_de_fotos(solicitudes, contexto, cargar_catalogo())
    except Exception:  # noqa: BLE001 - la regla no puede romper la herramienta
        cambios, indicacion = [], None
    resultado = _ejecutar(solicitudes, contexto)
    if isinstance(resultado, dict) and "error" not in resultado:
        if cambios:
            resultado = {**resultado, "sustituciones": cambios}
        if indicacion:
            resultado = {**resultado, "indicacion": indicacion}
    return resultado


def _ejecutar(solicitudes, contexto: ContextoTurno) -> dict:
    """Ejecuta enviar_multimedia con el argumento del modelo y el contexto del turno.

    Devuelve el objeto que hoy devuelve el subflujo al modelo. Si el principal
    de n8n no hubiera podido llamar (destino, id de mensaje o tiempo), devuelve
    {"error": <el mismo mensaje que tira n8n>}.
    """
    try:
        conversacion = contexto.conversation_id
        if contexto.account_id != 1 or not es_entero_seguro(conversacion) or conversacion <= 0:
            return {"error": "Destino de multimedia inválido"}
        ultimo = contexto.ultimo_message_id
        if not (isinstance(ultimo, int) and not isinstance(ultimo, bool) and _RE_ID_MENSAJE.fullmatch(str(ultimo))):
            return {"error": "Falta un ID de mensaje consumido válido para multimedia"}
        if contexto.segundos() > TOPE_INICIO_SEGUNDOS:
            return {"error": "Tiempo insuficiente para iniciar multimedia"}
        entrada = {
            "solicitudes": solicitudes,
            "account_id": contexto.account_id,
            "conversation_id": conversacion,
            "solicitud_id": contexto.solicitud_id(SUFIJO_SOLICITUD),
            "modo": contexto.modo,
        }
        inicio = time.monotonic()
        plan = planificar_seleccion(entrada, cargar_catalogo())
        contexto_plan = plan.get("contexto") or {}
        reenviar = _reenvio_permitido(solicitudes, contexto)
        if (plan["ok"] is True and contexto_plan.get("modo") == "enviar" and len(plan["plan"]) > 0
                and not reenviar and _todo_ya_mandado(plan["plan"], contexto.sesion)):
            # Pedido de Mateo (17/11): lo que ya se mandó en la conversación no se
            # reenvía si el cliente no lo pidió. Va como «omitido» (ya estaba enviado).
            return resumir_resultados(plan, [
                {"asset_id": p["asset_id"], "version": p["version"], "estado": "omitido",
                 "motivo": "ya_enviado_en_la_conversacion"} for p in plan["plan"]])
        if plan["ok"] is True and contexto_plan.get("modo") == "enviar" and len(plan["plan"]) > 0:
            return _enviar(plan, contexto, inicio, reenviar)
        # «Responder sin envio».
        simulados = (
            [{"asset_id": p["asset_id"], "version": p["version"], "estado": "simulado"} for p in plan["plan"]]
            if contexto_plan.get("modo") == "simular"
            else []
        )
        return resumir_resultados(plan, simulados)
    except Exception as error:  # noqa: BLE001 - la herramienta nunca rompe el turno
        return {"error": f"enviar_multimedia: {type(error).__name__}"}
