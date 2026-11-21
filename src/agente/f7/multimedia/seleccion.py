"""Selección de fotos y videos de F7: port de referencia-f7/logica/multimedia/seleccion.mjs.

Es el mismo código que corre hoy en el nodo «Planificar contenido» del
subflujo «F7 · Enviar multimedia · v1» (y en los nodos que resumen). No hace
I/O ni interpreta al cliente: recibe pedidos ya armados por el modelo.

Se porta tal cual, con la semántica de JavaScript donde importa:
- «undefined» (clave ausente) no es lo mismo que null (None).
- true no es 1: los booleanos no cuentan como números.
- Las regex se comparan enteras (fullmatch), como ^...$ de JS.
- trim y \\s usan los espacios de JS.
"""

from __future__ import annotations

import functools
import json
import math
import re
import unicodedata
from pathlib import Path

PRODUCTOS = ["fundas", "tipo tapizado", "alfombra", "cubrevolante"]
CONTENIDOS = ["presentacion", "disenos", "colores", "calidad", "comparacion"]
FORMATOS = ["auto", "foto", "video"]
ESTADOS_RESULTADO = ["aceptado", "fallido", "desconocido", "omitido", "control_humano", "simulado"]
MAX_SOLICITUDES = 16
MAX_PIEZAS = 20

RUTA_CATALOGO = Path(__file__).with_name("catalogo.json")

# Clave ausente (el «undefined» de JS).
_FALTA = object()

# Los espacios que JS considera en trim() y en \s.
_ESPACIOS_JS = "\t\n\x0b\x0c\r \xa0  -     　﻿"
_RE_BORDES = re.compile(f"^[{_ESPACIOS_JS}]+|[{_ESPACIOS_JS}]+\\Z")
_RE_ESPACIOS = re.compile(f"[{_ESPACIOS_JS}]+")
_RE_TILDES = re.compile("[̀-ͯ]")
_RE_IDENTIFICADOR = re.compile(r"[A-Za-z0-9:_-]+")
_RE_DISENO = re.compile(r"[a-z0-9][a-z0-9 -]*")
_RE_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,159}")
_RE_NOMBRE_PROHIBIDO = re.compile(r"[/\\\r\n]")
_RE_SHA256 = re.compile(r"[a-f0-9]{64}")
_RE_MOTIVO = re.compile(r"[a-z0-9_:-]{1,120}")
_MAX_SEGURO = 2**53 - 1


def js_trim(texto: str) -> str:
    """String.prototype.trim() de JS."""
    return _RE_BORDES.sub("", texto)


def _es_numero(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def _es_finito(valor) -> bool:
    """Number.isFinite de JS."""
    return _es_numero(valor) and math.isfinite(valor)


def es_entero_seguro(valor) -> bool:
    """Number.isSafeInteger de JS (5.0 cuenta como entero, true no)."""
    return _es_finito(valor) and valor == int(valor) and abs(valor) <= _MAX_SEGURO


def _objeto(valor) -> bool:
    return isinstance(valor, dict)


def _esta(lista, valor) -> bool:
    """Array.prototype.includes con ===: true no es 1."""
    return any(type(x) is type(valor) and x == valor for x in lista)


def _json_js(valor) -> str:
    """JSON.stringify: sin espacios y sin escapar acentos."""
    return json.dumps(valor, ensure_ascii=False, separators=(",", ":"))


def etiqueta(valor):
    """Recorta, pasa a minúscula, saca tildes y deja espacios simples."""
    if not isinstance(valor, str):
        return None
    texto = unicodedata.normalize("NFD", js_trim(valor).lower())
    return _RE_ESPACIOS.sub(" ", _RE_TILDES.sub("", texto))


def identificador(valor, maximo: int = 160) -> bool:
    return (
        isinstance(valor, str)
        and 0 < len(valor.encode("utf-16-le")) // 2 <= maximo
        and _RE_IDENTIFICADOR.fullmatch(valor) is not None
    )


def _campos_validos(valor, permitidos, ruta, errores) -> bool:
    if not _objeto(valor):
        errores.append({"campo": ruta, "motivo": "objeto_requerido"})
        return False
    if any(not isinstance(clave, str) or clave not in permitidos for clave in valor):
        # No devolver el nombre recibido: podría traer instrucciones o datos privados.
        errores.append({"campo": ruta, "motivo": "campo_no_permitido"})
        return False
    return True


def _largo_js(texto: str) -> int:
    """.length de JS (unidades UTF-16)."""
    return len(texto.encode("utf-16-le")) // 2


def normalizar_entrada(entrada, _catalogo=None) -> dict:
    """normalizarEntrada: todo o nada. Devuelve {ok, entrada, errores}."""
    errores: list[dict] = []
    if not _campos_validos(entrada, ["account_id", "conversation_id", "solicitud_id", "modo", "solicitudes"], "entrada", errores):
        return {"ok": False, "entrada": None, "errores": errores}
    modo = entrada.get("modo", _FALTA)
    modo = "simular" if modo is _FALTA else modo
    account_id = entrada.get("account_id", _FALTA)
    account_id = 1 if account_id is _FALTA else account_id
    conversation_id = entrada.get("conversation_id")
    solicitud_id = entrada.get("solicitud_id")
    if not _esta(["simular", "enviar"], modo):
        errores.append({"campo": "modo", "motivo": "valor_no_permitido"})
    if not (_es_numero(account_id) and account_id == 1):
        errores.append({"campo": "account_id", "motivo": "cuenta_no_permitida"})
    if (conversation_id is not None or modo == "enviar") and (not es_entero_seguro(conversation_id) or conversation_id <= 0):
        errores.append({"campo": "conversation_id", "motivo": "entero_positivo_requerido"})
    if (solicitud_id is not None or modo == "enviar") and not identificador(solicitud_id):
        errores.append({"campo": "solicitud_id", "motivo": "identificador_requerido"})
    lista = entrada.get("solicitudes")
    if not isinstance(lista, list) or len(lista) < 1 or len(lista) > MAX_SOLICITUDES:
        errores.append({"campo": "solicitudes", "motivo": "cantidad_fuera_de_limite"})
        return {"ok": False, "entrada": None, "errores": errores}
    solicitudes: list[dict] = []
    for indice, solicitud in enumerate(lista):
        campo = f"solicitudes[{indice}]"
        if not _campos_validos(solicitud, ["producto", "contenido", "disenos", "formato", "reenvio_solicitado"], campo, errores):
            continue
        producto = etiqueta(solicitud.get("producto"))
        contenido = etiqueta(solicitud.get("contenido"))
        formato = solicitud.get("formato", _FALTA)
        formato = "auto" if formato is _FALTA else etiqueta(formato)
        reenvio = solicitud.get("reenvio_solicitado", _FALTA)
        reenvio = False if reenvio is _FALTA else reenvio
        if not _esta(PRODUCTOS, producto):
            errores.append({"campo": f"{campo}.producto", "motivo": "producto_no_permitido"})
        if not _esta(CONTENIDOS, contenido):
            errores.append({"campo": f"{campo}.contenido", "motivo": "contenido_no_permitido"})
        if not _esta(FORMATOS, formato):
            errores.append({"campo": f"{campo}.formato", "motivo": "formato_no_permitido"})
        if not isinstance(reenvio, bool):
            errores.append({"campo": f"{campo}.reenvio_solicitado", "motivo": "booleano_requerido"})
        disenos = _FALTA
        if "disenos" in solicitud:
            crudos = solicitud["disenos"]
            if contenido != "disenos" or not isinstance(crudos, list) or len(crudos) < 1 or len(crudos) > 10:
                errores.append({"campo": f"{campo}.disenos", "motivo": "filtro_de_disenos_invalido"})
            else:
                disenos = [etiqueta(d) for d in crudos]
                if any(
                    d is None or _largo_js(d) < 1 or _largo_js(d) > 60 or _RE_DISENO.fullmatch(d) is None
                    for d in disenos
                ):
                    errores.append({"campo": f"{campo}.disenos", "motivo": "nombre_de_diseno_invalido"})
                else:
                    disenos = list(dict.fromkeys(disenos))
        normalizada = {"producto": producto, "contenido": contenido}
        if disenos is not _FALTA:
            normalizada["disenos"] = disenos
        normalizada["formato"] = formato
        normalizada["reenvio_solicitado"] = reenvio
        solicitudes.append(normalizada)
    comparaciones = [s for s in solicitudes if s["contenido"] == "comparacion"]
    if comparaciones and (
        any(s["producto"] not in ("fundas", "tipo tapizado") for s in comparaciones)
        or not all(any(s["producto"] == p for s in comparaciones) for p in ("fundas", "tipo tapizado"))
    ):
        errores.append({"campo": "solicitudes", "motivo": "comparacion_requiere_ambas_fundas"})
    if errores:
        return {"ok": False, "entrada": None, "errores": errores}
    return {
        "ok": True,
        "entrada": {
            "account_id": account_id,
            "conversation_id": conversation_id,
            "solicitud_id": solicitud_id,
            "modo": modo,
            "solicitudes": solicitudes,
        },
        "errores": [],
    }


def _validar_catalogo(catalogo) -> list[dict]:
    errores: list[dict] = []
    if (
        not _objeto(catalogo)
        or not isinstance(catalogo.get("version"), str)
        or not catalogo["version"]
        or not isinstance(catalogo.get("assets"), list)
        or not isinstance(catalogo.get("rutas"), list)
        or len(catalogo["assets"]) > 200
        or len(catalogo["rutas"]) > 200
    ):
        return [{"campo": "catalogo", "motivo": "estructura_invalida"}]
    ids: set[str] = set()
    for asset in catalogo["assets"]:
        if (
            not _objeto(asset)
            or not identificador(asset.get("id"))
            or not isinstance(asset.get("version"), str)
            or not _RE_VERSION.fullmatch(asset["version"])
            or asset["id"] in ids
            or not isinstance(asset.get("habilitado"), bool)
            or not isinstance(asset.get("productos_visibles"), list)
            or any(not _esta(PRODUCTOS, p) for p in asset["productos_visibles"])
            or not _esta(["foto", "video"], asset.get("formato"))
            or not _es_finito(asset.get("orden"))
            or asset["orden"] < 0
        ):
            errores.append({"campo": "catalogo.assets", "motivo": "asset_invalido"})
            continue
        ids.add(asset["id"])
        # Una pieza deshabilitada puede no tener fuente: es una falta conocida.
        if asset["habilitado"]:
            fuente = asset.get("fuente")
            titulo = asset.get("titulo")
            nombre = asset.get("nombre_archivo")
            mime = asset.get("mime")
            sha = asset.get("sha256")
            if (
                not _objeto(fuente)
                or fuente.get("tipo") != "drive"
                or not identificador(fuente.get("id"))
                or not isinstance(titulo, str)
                or _largo_js(titulo) > 180
                or not isinstance(nombre, str)
                or not nombre
                or _largo_js(nombre) > 180
                or _RE_NOMBRE_PROHIBIDO.search(nombre)
                or not isinstance(mime, str)
                or not re.match(r"image/" if asset["formato"] == "foto" else r"video/", mime)
                or not isinstance(sha, str)
                or not _RE_SHA256.fullmatch(sha)
                or not es_entero_seguro(asset.get("bytes"))
                or asset["bytes"] <= 0
            ):
                errores.append({"campo": "catalogo.assets", "motivo": "fuente_o_metadata_invalida"})
    rutas: set[tuple] = set()
    for ruta in catalogo["rutas"]:
        diseno = ruta.get("diseno", _FALTA) if _objeto(ruta) else _FALTA
        if (
            not _objeto(ruta)
            or not _esta(PRODUCTOS, ruta.get("producto"))
            or not _esta(CONTENIDOS, ruta.get("contenido"))
            or (
                ruta["contenido"] == "disenos"
                and (not isinstance(diseno, str) or etiqueta(diseno) != diseno or not diseno)
            )
            or (ruta["contenido"] != "disenos" and diseno is not _FALTA and diseno is not None)
            or not isinstance(ruta.get("opciones"), list)
            or len(ruta["opciones"]) > 20
        ):
            errores.append({"campo": "catalogo.rutas", "motivo": "ruta_invalida"})
            continue
        clave = (ruta["producto"], ruta["contenido"], None if diseno is _FALTA else diseno)
        if clave in rutas:
            errores.append({"campo": "catalogo.rutas", "motivo": "ruta_duplicada"})
        rutas.add(clave)
        opciones: set[str] = set()
        for opcion in ruta["opciones"]:
            asset_ids = opcion.get("asset_ids") if _objeto(opcion) else None
            if (
                not _objeto(opcion)
                or not identificador(opcion.get("id"))
                or opcion["id"] in opciones
                or not _es_finito(opcion.get("prioridad"))
                or not isinstance(asset_ids, list)
                or not asset_ids
                or len(asset_ids) > MAX_PIEZAS
                or any(not isinstance(i, str) or i not in ids for i in asset_ids)
            ):
                errores.append({"campo": "catalogo.opciones", "motivo": "opcion_invalida"})
            else:
                opciones.add(opcion["id"])
    return errores


def _clave_locale(texto: str):
    """Imita String.localeCompare (ICU raíz) para ids [A-Za-z0-9:_-].

    Primero compara sin mayúsculas (puntuación < dígitos < letras) y, si
    empatan, la minúscula va antes que la mayúscula.
    """
    primaria, terciaria = [], []
    for ch in texto:
        if ch == "_":
            primaria.append(0)
        elif ch == "-":
            primaria.append(1)
        elif ch == ":":
            primaria.append(2)
        elif "0" <= ch <= "9":
            primaria.append(10 + ord(ch) - 48)
        elif "a" <= ch.lower() <= "z" and ch.isascii():
            primaria.append(100 + ord(ch.lower()) - 97)
        else:
            primaria.append(1000 + ord(ch))
        terciaria.append(1 if ch.isupper() else 0)
    return primaria, terciaria


def locale_compare(a: str, b: str) -> int:
    ka, kb = _clave_locale(a), _clave_locale(b)
    return (ka > kb) - (ka < kb)


def _signo(numero) -> int:
    return (numero > 0) - (numero < 0)


def _formato_admitido(asset, solicitud) -> bool:
    return solicitud["formato"] == "auto" or solicitud["formato"] == asset["formato"]


def _asset_admitido(asset, solicitud, solicitudes, diseno) -> bool:
    if not asset["habilitado"] or not _formato_admitido(asset, solicitud):
        return False
    # Nombrar dos productos en la llamada no habilita a mostrar todo de ambos:
    # cada producto visible necesita una solicitud del mismo uso.
    return all(
        any(
            otra["producto"] == producto
            and otra["contenido"] == solicitud["contenido"]
            and _formato_admitido(asset, otra)
            and (solicitud["contenido"] != "disenos" or not otra.get("disenos") or diseno in otra["disenos"])
            for otra in solicitudes
        )
        for producto in asset["productos_visibles"]
    )


def planificar_seleccion(entrada, catalogo) -> dict:
    """planificarSeleccion: valida, elige piezas y arma el plan ordenado."""
    normalizacion = normalizar_entrada(entrada, catalogo)
    version = catalogo.get("version") if _objeto(catalogo) else None
    salida = {
        "ok": False,
        "estado": "entrada_invalida",
        "contexto": None,
        "catalogo_version": version,
        "solicitudes": [],
        "plan": [],
        "faltantes": [],
        "errores": normalizacion["errores"],
    }
    if not normalizacion["ok"]:
        return salida
    datos = normalizacion["entrada"]
    solicitudes = datos["solicitudes"]
    salida["contexto"] = {k: datos[k] for k in ("account_id", "conversation_id", "solicitud_id", "modo")}
    salida["solicitudes"] = solicitudes
    errores = _validar_catalogo(catalogo)
    if errores:
        return {**salida, "estado": "catalogo_invalido", "errores": errores}
    assets = {asset["id"]: asset for asset in catalogo["assets"]}
    seleccionados: dict[str, dict] = {}
    for solicitud_indice, solicitud in enumerate(solicitudes):
        rutas = [
            r for r in catalogo["rutas"]
            if r["producto"] == solicitud["producto"] and r["contenido"] == solicitud["contenido"]
        ]
        if solicitud["contenido"] == "disenos":
            disenos = solicitud["disenos"] if solicitud.get("disenos") is not None else [r.get("diseno") for r in rutas]
        else:
            disenos = [None]
        objetivos = disenos if disenos else [None]
        for diseno in objetivos:
            ruta = next((r for r in rutas if r.get("diseno") == diseno), None)
            opciones = sorted(
                (ruta or {}).get("opciones") or [],
                key=functools.cmp_to_key(
                    lambda a, b: _signo(a["prioridad"] - b["prioridad"]) or locale_compare(a["id"], b["id"])
                ),
            )
            opcion = next(
                (
                    o for o in opciones
                    if all(_asset_admitido(assets[i], solicitud, solicitudes, diseno) for i in o["asset_ids"])
                ),
                None,
            )
            if opcion is None:
                salida["faltantes"].append({
                    "solicitud_indice": solicitud_indice,
                    "producto": solicitud["producto"],
                    "contenido": solicitud["contenido"],
                    "diseno": diseno,
                    "motivo": "sin_material_compatible" if ruta else "sin_material_especifico",
                })
                continue
            for asset_id in opcion["asset_ids"]:
                asset = assets[asset_id]
                anterior = seleccionados.get(asset_id)
                if anterior:
                    if solicitud_indice not in anterior["solicitud_indices"]:
                        anterior["solicitud_indices"].append(solicitud_indice)
                    anterior["reenvio_solicitado"] = anterior["reenvio_solicitado"] or solicitud["reenvio_solicitado"]
                else:
                    seleccionados[asset_id] = {
                        "asset_id": asset["id"],
                        "version": asset["version"],
                        "titulo": asset.get("titulo"),
                        "nombre_archivo": asset.get("nombre_archivo"),
                        "mime": asset.get("mime"),
                        "sha256": asset.get("sha256"),
                        "bytes": asset.get("bytes"),
                        "formato": asset["formato"],
                        "fuente": {"tipo": asset["fuente"]["tipo"], "id": asset["fuente"]["id"]},
                        "orden": asset["orden"],
                        "productos_visibles": list(asset["productos_visibles"]),
                        "solicitud_indices": [solicitud_indice],
                        "reenvio_solicitado": solicitud["reenvio_solicitado"],
                    }
    if len(seleccionados) > MAX_PIEZAS:
        return {
            **salida,
            "estado": "entrada_invalida",
            "plan": [],
            "faltantes": [],
            "errores": [{"campo": "solicitudes", "motivo": "demasiadas_piezas"}],
        }
    ordenados = sorted(
        seleccionados.values(),
        key=functools.cmp_to_key(
            lambda a, b: _signo(a["solicitud_indices"][0] - b["solicitud_indices"][0])
            or _signo(a["orden"] - b["orden"])
            or locale_compare(a["asset_id"], b["asset_id"])
        ),
    )
    salida["plan"] = [{**asset, "posicion": i + 1} for i, asset in enumerate(ordenados)]
    salida["ok"] = True
    salida["estado"] = ("parcial" if salida["plan"] else "sin_material") if salida["faltantes"] else "listo"
    return salida


def _resolver_estado(estados: list[str], faltantes: int) -> str:
    if not estados:
        return "sin_material" if faltantes else "sin_resultados"
    if faltantes:
        return "parcial"
    unicos = list(dict.fromkeys(estados))
    if len(unicos) == 1:
        return unicos[0]
    if all(e in ("aceptado", "omitido") for e in unicos):
        return "aceptado"
    return "parcial"


def _id_mensaje(resultado):
    """r.chatwoot_message_id ?? r.message_id ?? null."""
    valor = resultado.get("chatwoot_message_id")
    if valor is None:
        valor = resultado.get("message_id")
    return valor


def resumir_resultados(plan, resultados) -> dict:
    """resumirResultados: el objeto que recibe el modelo (MU8)."""
    plan = plan if _objeto(plan) else None
    contexto = plan.get("contexto") if plan else None
    contexto = contexto if _objeto(contexto) else None
    estado_plan = plan.get("estado") if plan else None
    modo = contexto.get("modo") if contexto else None
    faltantes_plan = plan.get("faltantes") if plan else None
    errores_plan = plan.get("errores") if plan else None
    salida = {
        "ok": False,
        "estado": estado_plan if estado_plan is not None else "entrada_invalida",
        "solicitud_id": contexto.get("solicitud_id") if contexto else None,
        "modo": modo if modo is not None else "simular",
        "entrega_confirmada": False,
        "aceptados": [],
        "omitidos": [],
        "fallidos": [],
        "desconocidos": [],
        "control_humano": [],
        "simulados": [],
        "faltantes": faltantes_plan if faltantes_plan is not None else [],
        "errores": errores_plan if errores_plan is not None else [],
        "solicitudes": [],
    }
    if not plan or not plan.get("ok") or not isinstance(plan.get("plan"), list):
        return salida
    cubos = {
        "aceptado": "aceptados",
        "omitido": "omitidos",
        "fallido": "fallidos",
        "desconocido": "desconocidos",
        "control_humano": "control_humano",
        "simulado": "simulados",
    }
    todos = resultados if isinstance(resultados, list) else []
    items: list[dict] = []
    for asset in plan["plan"]:
        coincidencias = [
            r for r in todos
            if _objeto(r) and r.get("asset_id") == asset["asset_id"] and r.get("version") == asset["version"]
        ]
        estado = "desconocido"
        motivo = "resultado_ausente"
        chatwoot_message_id = None
        if coincidencias:
            firmas = {_json_js([r.get("estado"), _id_mensaje(r)]) for r in coincidencias}
            primero = coincidencias[0]
            msg = _id_mensaje(primero)
            if len(firmas) > 1:
                motivo = "resultados_contradictorios"
            elif not _esta(ESTADOS_RESULTADO, primero.get("estado")):
                motivo = "estado_no_reconocido"
            elif salida["modo"] == "simular" and primero.get("estado") != "simulado":
                motivo = "resultado_incompatible_con_simulacion"
            elif salida["modo"] == "enviar" and primero.get("estado") == "simulado":
                motivo = "simulacion_en_modo_enviar"
            elif primero.get("estado") == "aceptado" and (not es_entero_seguro(msg) or msg <= 0):
                motivo = "aceptacion_sin_identificador"
            else:
                estado = primero["estado"]
                crudo = primero.get("motivo")
                motivo = crudo if isinstance(crudo, str) and _RE_MOTIVO.fullmatch(crudo) else None
                chatwoot_message_id = msg if es_entero_seguro(msg) and msg > 0 else None
        item = {
            "asset_id": asset["asset_id"],
            "version": asset["version"],
            "estado": estado,
            "motivo": motivo,
            "chatwoot_message_id": chatwoot_message_id,
            "solicitud_indices": list(asset["solicitud_indices"]),
        }
        salida[cubos[estado]].append(item)
        items.append(item)
    salida["estado"] = _resolver_estado([i["estado"] for i in items], len(salida["faltantes"]))
    salida["ok"] = salida["estado"] in ("aceptado", "omitido", "simulado")
    resumen_solicitudes = []
    for solicitud_indice, solicitud in enumerate(plan.get("solicitudes") or []):
        propios = [i for i in items if solicitud_indice in i["solicitud_indices"]]
        faltantes = [f for f in salida["faltantes"] if f.get("solicitud_indice") == solicitud_indice]
        resumen_solicitudes.append({
            "solicitud_indice": solicitud_indice,
            "producto": solicitud["producto"],
            "contenido": solicitud["contenido"],
            "estado": _resolver_estado([i["estado"] for i in propios], len(faltantes)),
            "asset_ids": [i["asset_id"] for i in propios],
            "faltantes": faltantes,
        })
    salida["solicitudes"] = resumen_solicitudes
    return salida


@functools.cache
def _catalogo_json() -> str:
    return RUTA_CATALOGO.read_text(encoding="utf-8")


def cargar_catalogo() -> dict:
    """El catálogo de F7 (copia del embebido en el export). Una copia nueva por llamada."""
    return json.loads(_catalogo_json())
