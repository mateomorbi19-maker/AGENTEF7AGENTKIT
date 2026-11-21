"""Motor de precios de F7: port exacto de referencia-f7/logica/precios/motor.mjs.

Es el mismo código que corre hoy embebido en los nodos «Validar pedido» y
«Resolver cotizacion» del subflujo de n8n. No usa red, credenciales, modelo
ni reloj. Los importes salen solo de celdas numéricas de la planilla.

Mismas reglas, mismas regex y mismos textos que el original. Lo que hace
falta para que Python se porte como JavaScript está al principio (espacios,
`trim`, `String()`, `$`, orden de claves).

Corrección del 20/11/2026 (campaña de pruebas). n8n ya no se usa y el motor dejó
de seguirlo en estos puntos, marcados en el código con «Corrección del 20/11»:
- el año decide entre generaciones (ONIX GEN 1 / GEN 2) y entre las opciones
  del buscador; el año que dio el cliente vale más que el escrito en el modelo;
- una fila de una cabina que el cliente no nombró no se elige por descarte;
- la variante que el cliente eligió entre las ya ofrecidas se cotiza sin volver
  a preguntar (`ofrecidas`);
- año no cubierto, configuración que no coincide con nada y fila sin precio
  numérico se marcan con `requiere_derivacion`: pasan a una persona;
- techo, paneles, relleno o volante pedidos como «tapiceria» van por «Otros»;
- en alfombra, «habitáculo» o «completa» no eligen fila;
- el nombre que ve el cliente va sin la nota interna de la planilla.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal

# ---------------------------------------------------------------------------
# Lo mínimo para que Python se comporte como JavaScript.
# ---------------------------------------------------------------------------

# `\s` y `trim()` de JavaScript: estos espacios, ni uno más ni uno menos.
_JS_ESPACIOS = (
    "\t\n\x0b\x0c\r \xa0 " + "".join(chr(c) for c in range(0x2000, 0x200B))
    + "    　﻿"
)
_CLASE_ESPACIOS = (
    r"\t\n\x0b\x0c\r \xa0  -     　﻿"
)
MAX_SAFE = 2**53 - 1


def _rx(patron: str) -> re.Pattern:
    """Compila una regex escrita como en JS: `\\s` de JS, `$` = fin del texto, `\\b` y `\\d` ASCII."""
    salida: list[str] = []
    i = 0
    en_clase = False
    while i < len(patron):
        c = patron[i]
        if c == "\\":
            sig = patron[i + 1]
            if sig == "s":
                salida.append(_CLASE_ESPACIOS if en_clase else "[" + _CLASE_ESPACIOS + "]")
            else:
                salida.append(c + sig)
            i += 2
            continue
        if en_clase:
            if c == "]":
                en_clase = False
        elif c == "[":
            en_clase = True
        elif c == "$":
            salida.append(r"\Z")
            i += 1
            continue
        salida.append(c)
        i += 1
    return re.compile("".join(salida), re.ASCII)


def js_trim(texto: str) -> str:
    """`String.prototype.trim()`."""
    return texto.strip(_JS_ESPACIOS)


def js_numero(valor: float) -> str:
    """`String(numero)` de JavaScript."""
    if isinstance(valor, int) and not isinstance(valor, bool) and abs(valor) < 10**21:
        return str(valor)
    valor = float(valor)
    if math.isnan(valor):
        return "NaN"
    if math.isinf(valor):
        return "Infinity" if valor > 0 else "-Infinity"
    if valor == 0:
        return "0"
    signo = "-" if valor < 0 else ""
    _, digitos_t, exp = Decimal(repr(abs(valor))).as_tuple()
    digitos = "".join(map(str, digitos_t)).rstrip("0") or "0"
    exp += len("".join(map(str, digitos_t))) - len(digitos)
    k = len(digitos)
    n = exp + k
    if k <= n <= 21:
        return signo + digitos + "0" * (n - k)
    if 0 < n <= 21:
        return signo + digitos[:n] + "." + digitos[n:]
    if -6 < n <= 0:
        return signo + "0." + "0" * (-n) + digitos
    e = n - 1
    exp_txt = ("+" if e > 0 else "-") + str(abs(e))
    if k == 1:
        return signo + digitos + "e" + exp_txt
    return signo + digitos[0] + "." + digitos[1:] + "e" + exp_txt


def js_str(valor) -> str:
    """`String(valor)` de JavaScript (None hace de null)."""
    if valor is None:
        return "null"
    if valor is True:
        return "true"
    if valor is False:
        return "false"
    if isinstance(valor, (int, float)):
        return js_numero(valor)
    if isinstance(valor, str):
        return valor
    if isinstance(valor, (list, tuple)):
        return ",".join("" if v is None else js_str(v) for v in valor)
    return "[object Object]"


def es_numero(valor) -> bool:
    """`typeof valor === 'number'`."""
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def es_entero(valor) -> bool:
    """`Number.isInteger(valor)`."""
    if isinstance(valor, bool) or not es_numero(valor):
        return False
    if isinstance(valor, float):
        return math.isfinite(valor) and valor.is_integer()
    return True


def es_entero_seguro(valor) -> bool:
    """`Number.isSafeInteger(valor)`."""
    return es_entero(valor) and abs(valor) <= MAX_SAFE


def numero_json(valor):
    """Un número como lo deja JSON en JS: los enteros sin «.0»."""
    if isinstance(valor, float) and math.isfinite(valor) and valor.is_integer() and abs(valor) <= MAX_SAFE:
        return int(valor)
    return valor


def js_largo(texto: str) -> int:
    """`.length` de JS: cuenta unidades UTF-16."""
    return len(texto.encode("utf-16-le")) // 2


def _clave_indice(clave: str) -> bool:
    return bool(re.fullmatch(r"0|[1-9][0-9]*", clave)) and int(clave) < 2**32 - 1


def js_claves(objeto: dict) -> list[str]:
    """`Object.keys()`: primero las claves que son índices, en orden numérico; después el resto."""
    indices = sorted((k for k in objeto if _clave_indice(k)), key=int)
    return indices + [k for k in objeto if not _clave_indice(k)]


def _js_round(x: float) -> int:
    """`Math.round()`: el medio redondea hacia arriba."""
    piso = math.floor(x)
    return piso + 1 if x - piso >= 0.5 else piso


def _sin_undefined(v):
    return "" if v is None else v


# ---------------------------------------------------------------------------
# Motor (motor.mjs)
# ---------------------------------------------------------------------------

PRODUCTOS = {
    "fundas": "Fundas a medida",
    "tipo tapizado": "TIPO TAPIZADO",
    "tapiceria": "TAPICERIA",
    "alfombra": "Termoformadas",
    "funda baul": "Funda Baúl - Antiderrame",
    "cobertor caja": "Cobertores de caja ",
    "espuma": "ESPUMAS",
    "otros": "Otros",
    "cubrevolante": "Otros",
}

ROTULOS = {
    "fundas": "Fundas a medida", "tipo tapizado": "Fundas tipo tapizado",
    "tapiceria": "Tapicería", "alfombra": "Alfombra termoformada",
    "funda baul": "Funda de baúl antiderrame", "cobertor caja": "Cobertor de caja",
    "espuma": "Espuma", "otros": "Producto o servicio", "cubrevolante": "Cubrevolante",
}
ASIENTOS = {"fundas", "tipo tapizado", "tapiceria"}
MEDIOS = ["efectivo", "transferencia", "cuotas"]
REGLA_CUOTAS = "Autorización expresa de Mateo: cuotas = importe de transferencia. No se usa la columna POSNET."

_RX_CONTROL = re.compile("[\u0000-\u001f\u007f]")
_RX_ESPACIOS = _rx(r"\s+")
_RX_DIACRITICOS = re.compile("[̀-ͯ]")
_RX_NO_PALABRA = _rx(r"[^a-z0-9]+")
_RX_TEXTO_PLANO = _rx(r"[*_`#\[\]<>]")


def limpiar(valor) -> str:
    texto = js_str(_sin_undefined(valor))
    return js_trim(_RX_ESPACIOS.sub(" ", _RX_CONTROL.sub(" ", texto)))


def normal(valor) -> str:
    return _RX_DIACRITICOS.sub("", unicodedata.normalize("NFD", limpiar(valor))).lower()


def palabras(valor) -> str:
    return js_trim(_RX_NO_PALABRA.sub(" ", normal(valor)))


def objeto(valor) -> bool:
    return isinstance(valor, dict)


def texto_plano(valor) -> str:
    return _RX_TEXTO_PLANO.sub("", limpiar(valor))


_FALTA = object()
_RX_ANIO_TEXTO = _rx(r"^\d{4}$")

# Corrección del 20/11 (campaña de pruebas): la tapicería es de butacas. Un trabajo que no es de
# butacas y llega como «tapiceria» (techo, paneles de puerta, relleno, volante) se consulta en
# «Otros» con el nombre de ese trabajo.
_TRABAJOS_SIN_BUTACAS = (
    (_rx(r"\btechos?\b"), "tapizado de techo"),
    (_rx(r"\bpanel(?:es)?\b|\bpuertas?\b"), "paneles de puerta"),
    (_rx(r"\brellenos?\b"), "relleno"),
    (_rx(r"\bvolantes?\b"), "tapizado de volante"),
)
# Lo que describe al vehículo y no es un trabajo: «5 puertas», «techo panorámico».
_RX_DATO_DEL_VEHICULO = _rx(r"\b\d+\s*(?:puertas?|ptas|prtas)\b|\btechos?\s+(?:panoramico|solar|corredizo)\b")


def trabajo_sin_butacas(consulta) -> str | None:
    """El trabajo que pide una consulta de «tapiceria» cuando no es de butacas; si no, None."""
    if not objeto(consulta) or normal(consulta.get("producto")) != "tapiceria":
        return None
    texto = palabras(f"{consulta.get('configuracion') or ''} {consulta.get('modelo') or ''}")
    texto = _RX_DATO_DEL_VEHICULO.sub(" ", texto)
    return next((trabajo for rx, trabajo in _TRABAJOS_SIN_BUTACAS if rx.search(texto)), None)


def normalizar_entrada(entrada) -> dict:
    errores: list[str] = []
    if not objeto(entrada):
        return {"ok": False, "entrada": None, "errores": ["La solicitud debe ser un objeto."], "hojas": []}
    extras = [k for k in entrada if k not in ("consultas", "modalidad", "tipo_solicitud", "metodo_pago")]
    if extras:
        errores.append("La solicitud contiene campos no admitidos.")
    modalidad = normal(entrada.get("modalidad"))
    tipo = normal(entrada.get("tipo_solicitud"))
    metodo_pago = "transferencia" if "metodo_pago" not in entrada else normal(entrada["metodo_pago"])
    if metodo_pago not in ("transferencia", "efectivo", "cuotas", "debito", "otro"):
        errores.append("metodo_pago debe ser transferencia, efectivo, cuotas, debito u otro.")
    if modalidad not in ("caba", "envio"):
        errores.append("modalidad debe ser caba o envio.")
    if tipo not in ("consulta", "comparacion", "combo"):
        errores.append("tipo_solicitud debe ser consulta, comparacion o combo.")
    lista = entrada.get("consultas")
    if not isinstance(lista, list) or len(lista) < 1 or len(lista) > 10:
        errores.append("Se necesitan entre 1 y 10 consultas.")
    consultas = []
    for index, consulta in enumerate(lista[:10] if isinstance(lista, list) else []):
        if not objeto(consulta):
            errores.append(f"Consulta {index + 1}: debe ser un objeto.")
            consultas.append(None)
            continue
        if any(k not in ("producto", "modelo", "anio", "configuracion", "cantidad") for k in consulta):
            errores.append(f"Consulta {index + 1}: contiene campos no admitidos.")
        producto = normal(consulta.get("producto"))
        if producto not in PRODUCTOS:
            errores.append(f"Consulta {index + 1}: producto no admitido.")
        cantidad = consulta.get("cantidad", _FALTA)
        cantidad = 1 if cantidad is _FALTA else cantidad
        if not es_entero(cantidad) or cantidad < 1 or cantidad > 10:
            errores.append(f"Consulta {index + 1}: cantidad debe ser un entero entre 1 y 10.")
        result = {"producto": producto, "cantidad": numero_json(cantidad)}
        for campo in ("modelo", "configuracion"):
            valor = consulta.get(campo)
            if valor is None or valor == "":
                continue
            if not isinstance(valor, str) or js_largo(limpiar(valor)) > 160:
                errores.append(f"Consulta {index + 1}: {campo} debe ser texto de hasta 160 caracteres.")
            elif limpiar(valor):
                result[campo] = limpiar(valor)
        anio = consulta.get("anio")
        if anio is not None and anio != "":
            if isinstance(anio, str) and _RX_ANIO_TEXTO.search(js_trim(anio)):
                anio = int(js_trim(anio))
            if not es_entero(anio) or anio < 1900 or anio > 2100:
                errores.append(f"Consulta {index + 1}: anio debe ser un año de cuatro dígitos entre 1900 y 2100.")
            else:
                result["anio"] = numero_json(anio)
        trabajo = trabajo_sin_butacas(result)
        if trabajo:
            # Corrección del 20/11: sigue el camino de «otros», sin configuración ni año.
            result = {"producto": "otros", "cantidad": result["cantidad"], "modelo": trabajo}
        consultas.append(result)
    if errores:
        return {"ok": False, "entrada": None, "errores": errores, "hojas": []}
    hojas = list(dict.fromkeys(PRODUCTOS[c["producto"]] for c in consultas))
    return {"ok": True, "entrada": {"consultas": consultas, "modalidad": modalidad, "tipo_solicitud": tipo,
                                    "metodo_pago": metodo_pago}, "errores": [], "hojas": hojas}


def centavos(valor):
    if not es_numero(valor) or not math.isfinite(valor) or valor <= 0:
        return None
    x = valor * 100
    n = _js_round(x)
    if abs(n) > MAX_SAFE or abs(x - n) > 0.000001:
        return None
    return n


_RX_MEDIO_NO = _rx(r"posnet|cuotas")
_RX_EFECTIVO = _rx(r"\befectivo\b")
_RX_TRANSF = _rx(r"\btran(?:sf|f)")


def medio(valor):
    v = normal(valor)
    if _RX_MEDIO_NO.search(v):
        return None
    if _RX_EFECTIVO.search(v):
        return "efectivo"
    if _RX_TRANSF.search(v):
        return "transferencia"
    return None


_RX_RESPALDO = _rx(r"^respaldo$")
_RX_ASIENTO = _rx(r"^asiento$")
_RX_PLAZAS = _rx(r"\b(\d+)\s+(?:plazas|asientos|butacas)\b")
_RX_JUEGO = _rx(r"juego completo")
_RX_BUTACON = _rx(r"\bbutacon|\bbutacones|3 cuerpos|butaca entera")


def configuracion(valor) -> str:
    v = palabras(valor)
    if _RX_RESPALDO.search(v):
        return "respaldo"
    if _RX_ASIENTO.search(v):
        return "asiento"
    n = _RX_PLAZAS.search(v)
    if n:
        return f"{js_numero(float(int(n.group(1))))} plazas"
    if _RX_JUEGO.search(v):
        return "5 plazas"
    if _RX_BUTACON.search(v):
        return "butaca y butacón"
    if v in ("delanteras", "dos asientos", "dos plazas"):
        return "2 plazas"
    return v


MARCAS = {
    "volkswagen": "volkswagen", "vw": "volkswagen", "renault": "renault",
    "peugeot": "peugeot", "citroen": "citroen", "fiat": "fiat", "ford": "ford",
    "chevrolet": "chevrolet", "audi": "audi", "bmw": "bmw", "nissan": "nissan",
    "jeep": "jeep", "honda": "honda", "toyota": "toyota", "hyundai": "hyundai", "hyunday": "hyundai",
    "mitsubishi": "mitsubishi", "chery": "chery", "cherry": "chery",
    "mercedes benz": "mercedes", "mercedez benz": "mercedes", "mercedes": "mercedes", "mercedez": "mercedes",
    "suzuki": "suzuki", "kia": "kia", "chrysler": "chrysler", "land rover": "land rover",
    "dodge": "dodge", "alfa romeo": "alfa romeo", "subaru": "subaru", "iveco": "iveco", "ivecco": "iveco",
    "scania": "scania", "mini": "mini", "ram": "ram", "ssangyong": "ssangyong",
}
CLAVES_MARCAS = sorted(MARCAS, key=lambda m: -len(m))


def separar_marca(valor) -> dict:
    v = normal(valor)
    for marca in CLAVES_MARCAS:
        if v == marca or v.startswith(f"{marca} "):
            return {"marca": MARCAS[marca], "texto": js_trim(v[len(marca):])}
    return {"marca": None, "texto": v}


def letra_columna(index: int) -> str:
    result = ""
    n = index + 1
    while n > 0:
        result = chr(65 + (n - 1) % 26) + result
        n = (n - 1) // 26
    return result


_RX_CIERRA_SECCION = _rx(r"lista de.*alternativas|^proximos articulos$")
_RX_MARCA_Y_MODELO = _rx(r"marca y modelo")


def _celda(fila, col):
    return fila[col] if 0 <= col < len(fila) else None


def leer_hoja(sheet):
    if not objeto(sheet) or not isinstance(sheet.get("values"), list) or any(
            not isinstance(row, list) for row in sheet["values"]):
        return None
    valores = sheet["values"]
    filas = []
    esquema = None
    marca = None
    tiene_encabezado = False
    for index, row in enumerate(valores):
        primera = palabras(_celda(row, 0))
        if _RX_CIERRA_SECCION.search(primera):
            esquema = None
            continue
        # Algunas secciones incluyen marca y modelo en su título (SsangYong Musso).
        # El encabezado siguiente establece que este texto es un separador, no tarifa.
        siguiente = valores[index + 1] if index + 1 < len(valores) else None
        marca_seccion = separar_marca(_celda(row, 0))["marca"]
        if (marca_seccion and _RX_MARCA_Y_MODELO.search(palabras(_celda(siguiente, 0) if siguiente is not None else None))
                and not any(es_numero(v) for v in row[1:])):
            marca = marca_seccion
            esquema = None
            continue
        es_grupos = bool(_RX_MARCA_Y_MODELO.search(primera)) or (
            primera == "vehiculos" and any(palabras(c) == "respaldo" for c in row))
        es_plana = palabras(_celda(row, 1)) == "vehiculo modelo" or primera == "producto servicio"
        if es_grupos or es_plana:
            esquema = {"modelo": 1 if es_plana and primera != "producto servicio" else 0,
                       "agrupado": es_grupos, "grupos": {}, "columnas": {}}
            grupo = "unidad"
            for col in range(1, len(row)):
                if es_grupos and limpiar(row[col]):
                    grupo = configuracion(row[col])
                esquema["grupos"][col] = {"clave": grupo, "rotulo": limpiar(row[col]) if es_grupos else "Unidad"}
                if es_grupos and not limpiar(row[col]):
                    previo = esquema["grupos"].get(col - 1)
                    esquema["grupos"][col]["rotulo"] = (previo["rotulo"] if previo else None) or grupo
                m = medio(row[col])
                if es_plana and m:
                    esquema["columnas"][col] = m
            if esquema["columnas"]:
                tiene_encabezado = True
            continue
        # Una marca es separador; nunca se toma como un vehículo sin precio.
        if (esquema["modelo"] if esquema else None) != 1 and primera in MARCAS:
            marca = MARCAS[primera]
            continue
        if not esquema:
            continue
        for col in range(1, len(row)):
            m = medio(row[col])
            if m and esquema["agrupado"] and col not in esquema["grupos"] and (col - 1) in esquema["grupos"]:
                esquema["grupos"][col] = dict(esquema["grupos"][col - 1])
            if m and col in esquema["grupos"]:
                esquema["columnas"][col] = m
                tiene_encabezado = True
        modelo = limpiar(_celda(row, esquema["modelo"]))
        if not modelo or medio(modelo):
            continue
        grupos: dict = {}
        for col in sorted(esquema["grupos"]):
            grupo = esquema["grupos"][col]
            if col <= esquema["modelo"]:
                continue
            if grupos.get(grupo["clave"]) is None:
                grupos[grupo["clave"]] = {"rotulo": grupo["rotulo"], "precios": {}, "columnas": {}}
            m = esquema["columnas"].get(col)
            if not m:
                continue
            valor = _celda(row, col)
            if centavos(valor) is not None:
                grupos[grupo["clave"]]["precios"][m] = valor
            grupos[grupo["clave"]]["columnas"][m] = {
                "columna": letra_columna(col), "celda": f"{letra_columna(col)}{index + 1}", "valor": valor}
        fuente = {}
        if "sheetId" in sheet:
            fuente["sheetId"] = sheet["sheetId"]
        fuente.update({"hoja": sheet.get("title"), "fila": index + 1, "modelo": modelo})
        filas.append({"modelo": modelo,
                      "marca": separar_marca(_celda(row, 0))["marca"] if esquema["modelo"] == 1 else marca,
                      "grupos": grupos, "fuente": fuente})
    return filas if tiene_encabezado else None


def ano_corto(valor: str) -> int:
    n = int(valor)
    return (2000 + n if n < 40 else 1900 + n) if len(valor) == 2 else n


_MESES = "enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre"
_RX_CLAUSULAS = _rx(r"\s*\/\s*")
_RX_TIENE_ANOS = _rx(r"\b(?:19|20)\d{2}\b|\b\d{2}\s*\+")
_RX_ALTERNATIVAS = _rx(r"\balternativas?\b")
_RX_LETRA = _rx(r"[a-z]")
_RX_HASTA_MES = _rx(r"\bhasta\s+(\d{1,2})\/(\d{2}|(?:19|20)\d{2})\b")
_RX_MES_NOMBRE = _rx(r"\b(hasta|desde)?\s*(" + _MESES + r")\s+((?:19|20)\d{2})\s*(\+|en adelante)?")
_RX_MES_GUION = _rx(r"\b(\d{1,2})\s*-\s*((?:19|20)\d{2})\s*\+")
_RX_LISTA_ANOS = _rx(r"\b(?:19|20)\d{2}(?:\s*\/\s*(?:19|20)\d{2})+\b")
_RX_ANO = _rx(r"(?:19|20)\d{2}")
_RX_ANO_BARRA_DIGITO = _rx(r"\b(?:19|20)\d{2}\s*\/\s*\d\b")
_RX_RANGO = _rx(r"\b((?:19|20)\d{2}|\d{2})\s*(?:-|hasta|al|a)\s*((?:19|20)\d{2}|\d{2})\b")
_RX_PREVIO_ENUM = _rx(r"\d\s*[-/]\s*$")
_RX_POSTERIOR_ENUM = _rx(r"^\s*[-/]\s*\d")
_RX_ACTUAL = _rx(r"\b((?:19|20)\d{2})\s*-\s*actual\b")
_RX_HASTA_ANO = _rx(r"\bhasta\s+((?:19|20)\d{2})\b")
_RX_DESDE_ANO = _rx(r"\bdesde\s+((?:19|20)\d{2})\b")
_RX_ANO_MAS = _rx(r"\b((?:19|20)\d{2}|\d{2})\s*(?:\+|en adelante)")
_RX_MAS_ANO = _rx(r"\+\s*((?:19|20)\d{2}|\d{2})\b")
_RX_ANO_ABIERTO = _rx(r"\b(?:19|20)\d{2}\s*-\s*(?=$|\))")
_RX_ANO_SUELTO = _rx(r"\b(?:19|20)\d{2}\b")
_RX_GENERACION = _rx(r"\bgen(?:eracion)?\s*\d+\b")


def describir_modelo(valor) -> dict:
    separado = separar_marca(valor)
    texto = separado["texto"]
    rangos: list[dict] = []
    # Una alternativa o una segunda cláusula de modelo puede tener sus propios
    # años. No se une ese alcance por OR con el rango del modelo solicitado.
    clausulas = _RX_CLAUSULAS.split(texto)
    tiene_anos = bool(_RX_TIENE_ANOS.search(texto))
    estado = {"ambiguo": bool(_RX_ALTERNATIVAS.search(texto)) or (
        tiene_anos and len([c for c in clausulas if _RX_LETRA.search(c)]) > 1)}
    fronteras: list[int] = []

    # La API recibe año, no mes: en el año de una frontera mensual se pide confirmar.
    def hasta_mes(m):
        mes, anio = m.group(1), m.group(2)
        if int(mes) < 1 or int(mes) > 12:
            estado["ambiguo"] = True
        y = ano_corto(anio)
        rangos.append({"min": 1900, "max": y})
        fronteras.append(y)
        return " "
    texto = _RX_HASTA_MES.sub(hasta_mes, texto)

    def mes_nombre(m):
        direccion, anio, abierto = m.group(1), m.group(3), m.group(4)
        y = int(anio)
        if direccion == "hasta":
            rangos.append({"min": 1900, "max": y})
        elif direccion == "desde" or abierto:
            rangos.append({"min": y, "max": 2100})
        else:
            rangos.append({"min": y, "max": y})
            estado["ambiguo"] = True
        fronteras.append(y)
        return " "
    texto = _RX_MES_NOMBRE.sub(mes_nombre, texto)

    def mes_guion(m):
        y = int(m.group(2))
        if int(m.group(1)) < 1 or int(m.group(1)) > 12:
            estado["ambiguo"] = True
        rangos.append({"min": y, "max": 2100})
        fronteras.append(y)
        return " "
    texto = _RX_MES_GUION.sub(mes_guion, texto)

    # Las listas con barras son años puntuales, nunca intervalos interpolados.
    def lista_anos(m):
        for y in (int(a) for a in _RX_ANO.findall(m.group(0))):
            rangos.append({"min": y, "max": y})
        return " "
    texto = _RX_LISTA_ANOS.sub(lista_anos, texto)

    def ano_barra(m):
        estado["ambiguo"] = True
        return " "
    texto = _RX_ANO_BARRA_DIGITO.sub(ano_barra, texto)

    # Solo formatos de año presentes explícitamente; no se inventan generaciones.
    def rango(m):
        original, offset = m.string, m.start()
        # Renaul 9-11-12-18-19-21 enumera modelos; no años.
        if _RX_PREVIO_ENUM.search(original[:offset]) or _RX_POSTERIOR_ENUM.search(original[m.end():]):
            return m.group(0)
        minimo, maximo = ano_corto(m.group(1)), ano_corto(m.group(2))
        if minimo > maximo:
            estado["ambiguo"] = True
            return " "
        rangos.append({"min": minimo, "max": maximo})
        return " "
    texto = _RX_RANGO.sub(rango, texto)

    def actual(m):
        rangos.append({"min": int(m.group(1)), "max": 2100})
        return " "
    texto = _RX_ACTUAL.sub(actual, texto)

    def hasta_ano(m):
        rangos.append({"min": 1900, "max": int(m.group(1))})
        return " "
    texto = _RX_HASTA_ANO.sub(hasta_ano, texto)

    def desde_ano(m):
        rangos.append({"min": int(m.group(1)), "max": 2100})
        return " "
    texto = _RX_DESDE_ANO.sub(desde_ano, texto)

    def ano_abierto(m):
        rangos.append({"min": ano_corto(m.group(1)), "max": 2100})
        return " "
    texto = _RX_ANO_MAS.sub(ano_abierto, texto)
    texto = _RX_MAS_ANO.sub(ano_abierto, texto)

    def ano_incompleto(m):
        estado["ambiguo"] = True
        return " "
    texto = _RX_ANO_ABIERTO.sub(ano_incompleto, texto)

    # Un número que por sí solo nombra el modelo (Peugeot 2008) no es un año.
    def ano_suelto(m):
        if not palabras(m.string[:m.start()]):
            return m.group(0)
        rangos.append({"min": int(m.group(0)), "max": int(m.group(0))})
        return " "
    texto = _RX_ANO_SUELTO.sub(ano_suelto, texto)
    return {"marca": separado["marca"], "base": palabras(texto), "rangos": rangos,
            "ambiguo": estado["ambiguo"], "fronterasMensuales": fronteras}


def contiene(texto: str, consulta: str) -> bool:
    return bool(consulta) and f" {consulta} " in f" {texto} "


def distancia(a: str, b: str) -> int:
    previa = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        actual = [i]
        for j in range(1, len(b) + 1):
            actual.append(min(actual[j - 1] + 1, previa[j] + 1, previa[j - 1] + (0 if a[i - 1] == b[j - 1] else 1)))
        previa = actual
    return previa[len(b)]


def evidencia(row: dict, grupo: str) -> dict:
    g = row["grupos"].get(grupo)
    return {**row["fuente"], "configuracion": (g["rotulo"] if g else None) or grupo,
            "columnas": (g["columnas"] if g else None) or {}, "regla_cuotas": REGLA_CUOTAS}


def opciones(filas: list[dict]) -> list[dict]:
    mapa: dict = {}
    for row in filas:
        mapa[normal(row["modelo"])] = {"modelo": row["modelo"]}
    return list(mapa.values())[:12]


# Prueba del 21/11: paneles y espuma también son trabajos de taller (guion: «Tapicería, paneles,
# relleno y techo: CABA, no envío»).
_RX_SERVICIO = _rx(r"\b(?:relleno|limpieza|techo|tapizado|tapiceria|panel|paneles|espuma|espumas)\b")


def solo_taller(consulta) -> bool:
    """¿El trabajo se hace solo en el taller de CABA? Tapicería, espuma y los servicios de «Otros»."""
    if not objeto(consulta):
        return False
    producto = normal(consulta.get("producto"))
    if producto in ("tapiceria", "espuma"):
        return True
    return producto == "otros" and bool(
        _RX_SERVICIO.search(palabras(f"{consulta.get('modelo') or ''} {consulta.get('configuracion') or ''}")))
# Corrección del 20/11 (campaña de pruebas): configuraciones que en alfombra solo repiten el producto.
_ALFOMBRA_ENTERA = {"habitaculo", "completa", "completo", "juego", "todas", "de", "del", "el", "la", "las", "los"}


NO_ESTA_EN_LA_LISTA = "No encontré ese modelo o producto en la lista consultada."
# Prueba del 21/11 (R26): antes era «Confirmá el año del vehículo para esta variante publicada.
# Opción publicada: …».
PREGUNTA_ANIO = "De qué año es tu vehículo?"
# Prueba del 21/11 (R06): «Unidad» es el nombre interno de la configuración de lo que no es un
# asiento. Si el modelo la copia de una cotización anterior, no dice nada.
_SIN_CONFIGURACION = {"unidad", "unidades", "un", "una", "1"}


def resolver(consulta: dict, filas: list[dict], modalidad: str, ofrecidas=(), cabina_cliente=None) -> dict:
    # `ofrecidas` (corrección del 20/11): las opciones que la herramienta ya le ofreció al cliente
    # en turnos anteriores de la conversación, como las devuelve clave_opcion.
    item = {"producto": consulta["producto"], "modelo": consulta.get("modelo") or None,
            "estado": "requiere_aclaracion", "precios": {}, "cantidad": consulta["cantidad"], "fuentes": []}

    def aclarar(motivo, posibles=(), derivar=False):
        r = {**item, "motivo": motivo}
        if posibles:
            r["opciones"] = list(posibles)
        if derivar:
            # Corrección del 20/11 (campaña de pruebas): esto no lo puede resolver el cliente.
            # El motivo no se le manda: el resumen para el modelo pide pasarlo a una persona.
            r["requiere_derivacion"] = "revision_especial"
        return r

    if modalidad == "envio" and (consulta["producto"] in ("tapiceria", "espuma") or (
            consulta["producto"] == "otros" and _RX_SERVICIO.search(palabras(consulta.get("modelo"))))):
        return {**item, "estado": "sin_precio",
                "motivo": "Este servicio se realiza de forma presencial en CABA y no está disponible para envío."}
    if consulta["producto"] != "cubrevolante" and not consulta.get("modelo"):
        return aclarar("Confirmá el nombre del producto o servicio que querés consultar." if consulta["producto"] == "otros"
                       else "Confirmá la marca y el modelo del vehículo.")
    if consulta["producto"] == "espuma" and configuracion(consulta.get("configuracion")) not in ("asiento", "respaldo"):
        return aclarar("Confirmá si necesitás espuma de asiento o de respaldo.",
                       [{"configuracion": "asiento"}, {"configuracion": "respaldo"}])
    busqueda = describir_modelo("CUBRE VOLANTE" if consulta["producto"] == "cubrevolante" else consulta.get("modelo"))
    ano_modelo = (busqueda["rangos"][0]["min"] if len(busqueda["rangos"]) == 1
                  and busqueda["rangos"][0]["min"] == busqueda["rangos"][0]["max"] else None)
    # Corrección del 20/11 (campaña de pruebas): si el año que dio el cliente no es el escrito en
    # el modelo (llegó «HILUX 2017», la variante de otra hoja, con anio 2020), vale el del
    # cliente. Antes se le pedía confirmar «el año escrito en el modelo», que él nunca escribió.
    anio = consulta.get("anio") or ano_modelo

    # Cambio pedido por Mateo el 16/11/2026. El buscador de n8n (coincide / cercana)
    # solo encontraba el vehículo escrito casi igual que en la planilla. Ahora elige
    # las filas vehiculos.buscar, que tolera cómo escribe la gente por WhatsApp. Desde
    # acá (años, configuración, variantes, precio) sigue el motor de n8n tal cual.
    from .vehiculos import (TEXTO_CONFUSION, TEXTO_SIN_MEDIDAS, cabina_dicha, cabina_sin_nombrar, misma_cabina,
                            solo_cabina)
    from .vehiculos import buscar as buscar_vehiculo

    # Prueba del 21/11 (R06, R40): la cabina que escribió el cliente, si la consulta no trae una.
    detalle_cabina = consulta.get("configuracion")
    if (cabina_cliente in ("simple", "doble") and consulta["producto"] not in ("otros", "cubrevolante")
            and not cabina_dicha(f"{consulta.get('modelo') or ''} cabina")
            and not cabina_dicha(consulta.get("configuracion"))):
        detalle_cabina = f"{consulta.get('configuracion') or ''} cabina {cabina_cliente}"

    def otra_cabina(row) -> bool:
        """Corrección del 20/11: la fila es de una cabina (simple o doble) que el cliente no nombró."""
        return cabina_sin_nombrar(row["modelo"], consulta.get("modelo"), detalle_cabina)

    # Corrección del 20/11 (campaña de pruebas): la configuración va aparte, por si nombra la cabina.
    hallado = buscar_vehiculo("CUBRE VOLANTE" if consulta["producto"] == "cubrevolante" else consulta.get("modelo"),
                              filas, detalle_cabina)
    # Corrección del 20/11 (campaña de pruebas): con opciones y el año dado, primero decide el año.
    en_duda = hallado["estado"] == "opciones" and bool(hallado["indices"])
    if not en_duda and (hallado["estado"] != "candidatas" or not hallado["indices"]):
        # Textos de Mateo (16/11): si se confundió, que repita el vehículo; si el vehículo
        # no está, que pase por el taller a tomar las medidas (fundas y tipo tapizado).
        # Prueba del 21/11 (R46): en tipo tapizado la lista es corta. Un vehículo que no se
        # parece a ninguna fila casi siempre es un auto de verdad sin esa tarifa (Sandero Stepway),
        # no una confusión del cliente: va el texto de «no contamos con las medidas».
        # Lo mismo vale para las otras listas cortas (alfombras, funda de baúl, cobertores, espuma):
        # ahí pasa a una persona. En fundas a medida y tapicería, que tienen casi todos los autos,
        # algo que no se parece a nada sí se le pide de nuevo.
        sin_parecidos = hallado["estado"] == "confusion" and not hallado["indices"]
        lista_corta = consulta["producto"] not in ("fundas", "tapiceria")
        if consulta["producto"] in ("otros", "cubrevolante"):
            motivo = NO_ESTA_EN_LA_LISTA
        elif hallado["estado"] == "confusion" and not (lista_corta and sin_parecidos):
            motivo = TEXTO_CONFUSION
        elif consulta["producto"] in ("fundas", "tipo tapizado"):
            motivo = TEXTO_SIN_MEDIDAS
        else:
            motivo = NO_ESTA_EN_LA_LISTA
        if motivo == NO_ESTA_EN_LA_LISTA:
            # Prueba del 21/11 (R32): ese texto de sistema ya no se le manda al cliente. Lo que no
            # está en la lista (un techo, una funda de baúl para ese auto) pasa a una persona.
            return {**item, "estado": "no_encontrado", "motivo": motivo, "requiere_derivacion": "revision_especial"}
        return {**item, "estado": "no_encontrado", "motivo": motivo}
    candidatas = [filas[i] for i in hallado["indices"]]
    todas_por_modelo = candidatas
    if anio:
        candidatas = [row for row in candidatas if not describir_modelo(row["modelo"])["rangos"] or any(
            r["min"] <= anio <= r["max"] for r in describir_modelo(row["modelo"])["rangos"])]
        # Corrección del 20/11 (campaña de pruebas): una fila sin años pero de una cabina que el
        # cliente no nombró (HILUX CABINA SIMPLE) no es «la de siempre». No absorbe un año que
        # las demás no cubren, ni compite con la fila general de ese año (HILUX 2026).
        con_anos = [row for row in candidatas if describir_modelo(row["modelo"])["rangos"]]
        if any(not otra_cabina(row) for row in con_anos) or (
                not con_anos and len(candidatas) < len(todas_por_modelo)):
            candidatas = [row for row in candidatas if describir_modelo(row["modelo"])["rangos"]
                          or not otra_cabina(row)]
        if not candidatas:
            return aclarar("El año indicado no está cubierto por las variantes publicadas.",
                           opciones(todas_por_modelo), derivar=True)
        # Una fila con años que cubre el del cliente es más específica que la fila del
        # mismo nombre sin años (DUSTER frente a DUSTER 2017+). Otros nombres no se descartan.
        # Corrección del 20/11 (campaña de pruebas): otra generación del mismo modelo es el mismo
        # nombre. Con ONIX GEN 2 (2020+) cubriendo el año, ONIX GEN 1 queda descartada.
        def sin_generacion(row):
            return palabras(_RX_GENERACION.sub(" ", describir_modelo(row["modelo"])["base"]))

        especificas = {sin_generacion(row) for row in candidatas if describir_modelo(row["modelo"])["rangos"]}
        if especificas:
            candidatas = [row for row in candidatas if describir_modelo(row["modelo"])["rangos"]
                          or sin_generacion(row) not in especificas]
    # Corrección del 20/11 (campaña de pruebas): si ya se le ofrecieron estas opciones y ahora llega
    # el nombre exacto de una (208 frente a 208 GT, DUSTER frente a DUSTER 2017+), es esa. No se
    # vuelve a preguntar ni, más abajo, se le pide confirmar el año de la variante que eligió.
    pedida = clave_opcion(consulta.get("modelo"))
    elegida = [row for row in candidatas if clave_opcion(row["modelo"]) == pedida] if pedida in ofrecidas else []
    if elegida:
        candidatas = elegida
    elif en_duda and not (len(candidatas) == 1 and len(todas_por_modelo) > 1):
        # Ninguna era segura: se ofrecen las que el año no descartó. Si quedó una sola, es esa.
        return aclarar("No encontré una coincidencia exacta. Confirmá cuál de estas opciones corresponde.",
                       opciones(candidatas))
    es_asiento = consulta["producto"] in ASIENTOS
    if es_asiento:
        grupo = configuracion(consulta.get("configuracion") or "5 plazas")
    elif consulta["producto"] == "espuma":
        grupo = configuracion(consulta.get("configuracion"))
    else:
        grupo = "unidad"
    if not es_asiento and consulta["producto"] != "espuma" and consulta.get("configuracion"):
        detalle = palabras(consulta["configuracion"])
        # Corrección del 20/11 (campaña de pruebas): la cabina coincide aunque la planilla la
        # escriba en otro orden («cabina doble» = DOBLE CABINA).
        # Prueba del 21/11 (R06): la fila que no dice cabina es la de doble cabina (la planilla
        # solo aclara «Cabina Simple»). La fila de la otra cabina ya la descartó el buscador.
        filtradas = [row for row in candidatas if contiene(palabras(row["modelo"]), detalle)
                     or misma_cabina(row["modelo"], consulta["configuracion"])
                     or (cabina_dicha(consulta["configuracion"]) == "doble" and solo_cabina(consulta["configuracion"])
                         and not cabina_dicha(row["modelo"]))]
        if not filtradas and all(p in _SIN_CONFIGURACION for p in detalle.split()):
            filtradas = candidatas
        # Corrección del 20/11 (campaña de pruebas): la alfombra termoformada ya es de habitáculo.
        # «habitáculo», «completa» o «juego» repiten el producto y no eligen una fila: se ignoran.
        if not filtradas and consulta["producto"] == "alfombra" and all(
                p in _ALFOMBRA_ENTERA for p in detalle.split()):
            filtradas = candidatas
        if not filtradas:
            return aclarar("La configuración indicada necesita confirmación para este producto.",
                           opciones(candidatas), derivar=True)
        candidatas = filtradas
    if not any(grupo in row["grupos"] for row in candidatas):
        disponibles = list(dict.fromkeys(
            g for row in candidatas for g in js_claves(row["grupos"]) if row["grupos"][g]["precios"]))
        return aclarar("Confirmá la configuración entre las opciones disponibles para este modelo.",
                       [{"configuracion": c} for c in disponibles])
    grupos: dict[str, dict] = {}
    for row in candidatas:
        g = row["grupos"].get(grupo)
        precios = dict((g["precios"] if g else None) or {})
        if modalidad == "envio":
            precios.pop("efectivo", None)
        # Excepción comercial explícita: cuotas usa la celda de transferencia,
        # incluso en Otros, donde POSNET tiene un importe diferente.
        if "transferencia" in precios:
            precios["cuotas"] = precios["transferencia"]
        clave = json.dumps([normal(row["modelo"]), grupo, precios], ensure_ascii=False, separators=(",", ":"))
        if clave not in grupos:
            grupos[clave] = {"row": row, "precios": precios, "fuentes": []}
        grupos[clave]["fuentes"].append(evidencia(row, grupo))
    item["fuentes"] = [f for g in grupos.values() for f in g["fuentes"]]
    if len(grupos) != 1:
        conflicto = len({normal(row["modelo"]) for row in candidatas}) == 1
        return aclarar("Hay importes distintos publicados para el mismo producto. Hay que confirmar el precio." if conflicto
                       else "Encontré más de una variante. Confirmá cuál corresponde a tu vehículo.", opciones(candidatas))
    elegido = next(iter(grupos.values()))
    if otra_cabina(elegido["row"]):
        # Corrección del 20/11 (campaña de pruebas): quedó una sola fila, pero es de una cabina
        # que el cliente no nombró. No se cotiza por descarte: se le confirma.
        return aclarar("No encontré una coincidencia exacta. Confirmá cuál de estas opciones corresponde.",
                       opciones(candidatas))
    descripcion = describir_modelo(elegido["row"]["modelo"])
    if descripcion["ambiguo"]:
        return aclarar("La descripción de años está incompleta o es ambigua. Hay que confirmar la variante.",
                       opciones(candidatas))
    if anio is not None and anio in descripcion["fronterasMensuales"] and not elegida:
        return aclarar("Hay más de una variante para ese año. Confirmá el mes o la versión del vehículo.",
                       opciones(candidatas))
    if not anio and descripcion["rangos"] and not elegida:
        return aclarar(PREGUNTA_ANIO, opciones(candidatas))
    plazas_fila = _RX_PLAZAS.search(palabras(elegido["row"]["modelo"]))
    if es_asiento and grupo == "5 plazas" and plazas_fila and int(plazas_fila.group(1)) != 5:
        return aclarar("La cantidad de plazas del modelo no coincide con la configuración de la tarifa. "
                       "Hay que confirmarla antes de cotizar.", opciones(candidatas))
    g = elegido["row"]["grupos"].get(grupo)
    rotulo = (g["rotulo"] if g else None) or grupo
    result = {**item, "modelo": elegido["row"]["modelo"], "configuracion": rotulo, "precios": elegido["precios"],
              "fuentes": elegido["fuentes"], "estado": "cotizado" if elegido["precios"] else "sin_precio"}
    if result["estado"] == "sin_precio":
        result["motivo"] = "La lista no tiene un precio numérico disponible para esta configuración y modalidad."
        result["requiere_derivacion"] = "revision_especial"  # Corrección del 20/11: pasa a una persona
    return result


def dinero(valor) -> str:
    """`'$' + valor.toLocaleString('es-AR', ...)`: punto de miles; decimales solo si no es entero."""
    if es_entero(valor):
        return "$" + f"{int(valor):,}".replace(",", ".")
    d = Decimal(repr(float(valor))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    signo = "-" if d < 0 else ""
    entero, decimales = f"{abs(d):f}".split(".")
    return "$" + signo + f"{int(entero):,}".replace(",", ".") + "," + decimales


# Cambios que pidió Mateo el 16/11/2026. El resto del motor es el port de n8n.
# - Ninguna cotización termina con una pregunta: se da la información y el
#   cliente sigue la conversación.
# - Con envío, el juego completo de fundas a medida sale con este texto fijo.
#   El importe sale de la planilla (columna de transferencia del juego
#   completo). El 10% no se calcula acá.
COTIZACION_FUNDAS_ENVIO = (
    "El juego completo de fundas en cuero automotor y a medida tiene un valor de {importe} "
    "en el diseño y color que elijas.\n\n"
    "Abonando en transferencia tenes un 10% de descuento realizando una seña en el encargo "
    "y el restante previo a su envio.(abonas en dos partes)\n\n"
    "También podes abonar en 3 cuotas sin interés los días miércoles y sábado en el precio indicado"
)


def es_juego_completo_de_fundas_con_envio(items: list[dict], pedido: dict) -> bool:
    """Un solo juego completo de fundas a medida, cotizado, con envío y sin medio raro."""
    if pedido.get("modalidad") != "envio" or pedido.get("metodo_pago") not in ("transferencia", "cuotas"):
        return False
    if len(items) != 1:
        return False
    item = items[0]
    return (item["producto"] == "fundas" and item["estado"] == "cotizado" and item["cantidad"] == 1
            and configuracion(item.get("configuracion")) == "5 plazas"
            and centavos(item["precios"].get("transferencia")) is not None)

_SIGLAS = {"VW", "BMW", "BAIC", "BYD", "JAC", "JMC", "GWM", "DFSK", "MG", "DS", "RAM", "GTI", "GLI", "GLX", "GTS",
           "GT", "HDI", "TDI", "TSI", "SUV", "SW", "HRV", "CRV", "AMG"}
_ENLACES = {"de", "del", "con", "sin", "y", "a", "al", "desde", "hasta", "en", "para"}


def _letra_o_numero(c: str) -> bool:
    return unicodedata.category(c)[0] in ("L", "N")


def _capitalizar_palabra(palabra: str, posicion: int) -> str:
    if any(c in "0123456789" for c in palabra) or palabra.upper() in _SIGLAS:
        return palabra
    if palabra != palabra.upper() and palabra != palabra.lower():
        return palabra
    baja = palabra.lower()
    if posicion > 0 and baja in _ENLACES:
        return baja
    if ord(baja[0]) > 0xFFFF:
        # charAt(0) en JS toma medio par sustituto y lo deja igual.
        return baja
    return baja[0].upper() + baja[1:]


# Corrección del 20/11 (campaña de pruebas): una nota interna de la planilla dentro del nombre
# («KANGOO Viejo y Nuevo ( Que años? ») no se le muestra al cliente. Es nota interna un
# paréntesis con «?» o un paréntesis sin cerrar; «(2020+)» y «(Todos)» quedan como están.
_RX_NOTA_INTERNA = _rx(r"\([^()]*\?[^()]*\)|\([^()]*$")


def nombre_limpio(valor) -> str:
    """El nombre de una fila sin la nota interna de la planilla."""
    return limpiar(_RX_NOTA_INTERNA.sub(" ", limpiar(valor)))


def clave_opcion(valor) -> str:
    """Un nombre de fila como se compara con el que eligió el cliente.

    Sin la marca adelante (el cliente la agrega o la saca), sin nota interna, signos ni mayúsculas.
    """
    return palabras(texto_plano(separar_marca(nombre_limpio(valor))["texto"]))


def modelo_legible(valor) -> str:
    """Solo presentación: conserva intactos modelo, fuente, rango y precios del resultado."""
    texto = texto_plano(nombre_limpio(valor))
    partes: list[str] = []
    i = 0
    while i < len(texto):
        if _letra_o_numero(texto[i]):
            j = i
            while j < len(texto) and _letra_o_numero(texto[j]):
                j += 1
            partes.append(_capitalizar_palabra(texto[i:j], i))
            i = j
        else:
            partes.append(texto[i])
            i += 1
    return "".join(partes)


_RX_N_PLAZAS = _rx(r"^\d+ plazas$")


def descripcion_natural(item: dict) -> str:
    modelo = modelo_legible(item.get("modelo"))
    para = " para " + modelo if modelo else ""
    cantidad = item["cantidad"]
    cant = js_str(cantidad)
    if item["producto"] in ("fundas", "tipo tapizado"):
        grupo = configuracion(item.get("configuracion"))
        completo = grupo == "5 plazas"
        cobertura = grupo if _RX_N_PLAZAS.search(grupo) else modelo_legible(item.get("configuracion")).lower()
        juegos = ("El juego" + (" completo" if completo else "") if cantidad == 1
                  else "Los " + cant + " juegos" + (" completos" if completo else ""))
        return (juegos + " de " + ROTULOS[item["producto"]].lower() + para
                + (" (" + cobertura + (" cada uno" if cantidad > 1 else "") + ")" if cobertura else ""))
    if item["producto"] == "tapiceria":
        return (("El trabajo de tapicería" if cantidad == 1 else "Los " + cant + " trabajos de tapicería") + para
                + (" (" + modelo_legible(item["configuracion"]).lower() + ")" if item.get("configuracion") else ""))
    nombres = {
        "alfombra": ["La alfombra termoformada", "Las " + cant + " alfombras termoformadas"],
        "funda baul": ["La funda de baúl antiderrame", "Las " + cant + " fundas de baúl antiderrame"],
        "cobertor caja": ["El cobertor de caja", "Los " + cant + " cobertores de caja"],
        "cubrevolante": ["El cubrevolante", "Los " + cant + " cubrevolantes"],
        "espuma": ["La espuma", "Las " + cant + " espumas"],
    }
    if item["producto"] == "otros":
        return modelo if cantidad == 1 else "Las " + cant + " unidades de " + modelo
    nombre = (nombres.get(item["producto"]) or [None, None])[0 if cantidad == 1 else 1] or ROTULOS[item["producto"]]
    pieza = (" de " + modelo_legible(item["configuracion"]).lower()
             if item["producto"] == "espuma" and item.get("configuracion") else "")
    return nombre + pieza + ("" if item["producto"] == "cubrevolante" else para)


_RX_ARTICULO = _rx(r"^(El|La|Los|Las) ")


def mensaje(items: list[dict], totales, aclaraciones: list[str], pedido: dict):
    if not aclaraciones and es_juego_completo_de_fundas_con_envio(items, pedido):
        return COTIZACION_FUNDAS_ENVIO.format(importe=dinero(items[0]["precios"]["transferencia"]))
    metodo = pedido["metodo_pago"]
    rotulo = (" en efectivo" if metodo == "efectivo" else " en total, en 3 cuotas sin interés" if metodo == "cuotas"
              else " por transferencia")
    hay_cotizados = any(item["estado"] == "cotizado" for item in items)
    completa = (len(items) > 0 and all(i["estado"] == "cotizado" and centavos(i["precios"].get(metodo)) is not None
                                       for i in items)
                and (pedido["tipo_solicitud"] != "combo" or centavos((totales or {}).get(metodo)) is not None))
    frases = []
    for item in items:
        titulo = ROTULOS[item["producto"]] + (" para " + modelo_legible(item["modelo"])
                                              if item.get("modelo") and item["producto"] != "cubrevolante" else "")
        if item["estado"] != "cotizado":
            if hay_cotizados:
                # Prueba del 21/11 (R32): un servicio de «Otros» se nombra solo, sin «Producto o servicio para».
                propio = modelo_legible(item["modelo"]) if item["producto"] == "otros" and item.get("modelo") else titulo
                frases.append(propio + ": pendiente de confirmación.")
                continue
            detalle = [t for t in (texto_plano(o.get("modelo") or o.get("configuracion"))
                                   for o in (item.get("opciones") or [])) if t]
            motivo = item["motivo"] if "motivo" in item else "undefined"
            frases.append(titulo + "\n" + js_str(motivo) + ("\nOpciones: " + "; ".join(detalle) + "." if detalle else ""))
            continue
        unitario = item["precios"].get(metodo)
        subtotal = (item.get("subtotales") or {}).get(metodo)
        importe = subtotal if subtotal is not None else unitario
        unidad = ("juego" if item["producto"] in ("fundas", "tipo tapizado")
                  else "trabajo" if item["producto"] == "tapiceria" else "unidad")
        detalle = ((" (" if metodo == "cuotas" else " en total (") + dinero(unitario) + " por " + unidad + ")"
                   if item["cantidad"] > 1 else "")
        frases.append(descripcion_natural(item) + (" salen " if item["cantidad"] > 1 else " sale ")
                      + dinero(importe) + rotulo + detalle + ".")
    bloques = frases
    if completa and pedido["tipo_solicitud"] == "combo":
        productos = []
        for indice, item in enumerate(items):
            descripcion = descripcion_natural(item)
            productos.append(_RX_ARTICULO.sub(lambda m: m.group(0).lower(), descripcion, count=1)
                             if indice else descripcion)
        juntos = ", ".join(productos[:-1]) + " y " + productos[-1] if len(productos) > 1 else productos[0]
        plural = len(items) > 1 or items[0]["cantidad"] > 1
        bloques = [juntos + (" salen " if plural else " sale ") + dinero(totales[metodo]) + rotulo + "."]
    elif pedido["tipo_solicitud"] == "comparacion":
        bloques = [" ".join(frases)]
    notas = [a for a in aclaraciones if not any(i.get("motivo") == a for i in items)]
    if notas:
        bloques.append("\n".join(notas))
    return "\n\n".join(bloques) or None


def cotizar(entrada, sheets, consultado_en=None, ofrecidas=(), cabina_cliente=None) -> dict:
    salida = {"estado": "entrada_invalida", "items": [], "totales": None, "mensaje_cotizacion": None,
              "aclaraciones": [], "consultado_en": consultado_en, "pregunta_comercial_incluida": False}
    validada = normalizar_entrada(entrada)
    if not validada["ok"]:
        return {**salida, "aclaraciones": validada["errores"]}
    pedido = validada["entrada"]
    salida["metodo_pago"] = pedido["metodo_pago"]
    if pedido["metodo_pago"] == "efectivo" and pedido["modalidad"] == "envio":
        return {**salida, "estado": "metodo_no_disponible",
                "aclaraciones": ["El efectivo es solo para el taller de CABA. ¿Preferís venir al taller o mantener el envío?"]}
    if pedido["metodo_pago"] in ("debito", "otro"):
        return {**salida, "estado": "metodo_no_confirmado",
                "aclaraciones": ["Ese medio de pago necesita confirmación de Candela."]}
    if not isinstance(sheets, list):
        return {**salida, "estado": "error_consulta", "aclaraciones": ["No se pudo consultar la lista de precios."]}
    datos: dict[str, list] = {}
    for titulo in validada["hojas"]:
        coincidencias = [s for s in sheets if objeto(s) and normal(s.get("title")) == normal(titulo)]
        if len(coincidencias) != 1:
            return {**salida, "estado": "error_consulta", "aclaraciones": [
                "No se pudo identificar una única hoja de precios para todos los productos solicitados."]}
        filas = leer_hoja(coincidencias[0])
        if filas is None:
            return {**salida, "estado": "error_consulta", "aclaraciones": ["No se pudo interpretar la lista de precios."]}
        datos[titulo] = filas
    items = [resolver(c, datos[PRODUCTOS[c["producto"]]], pedido["modalidad"], ofrecidas, cabina_cliente)
             for c in pedido["consultas"]]
    for item in items:
        if item["estado"] == "cotizado" and centavos(item["precios"].get(pedido["metodo_pago"])) is None:
            item["estado"] = "sin_precio"
            item["motivo"] = ("No encontré un valor " + {"transferencia": "por transferencia", "efectivo": "en efectivo",
                                                          "cuotas": "en cuotas"}[pedido["metodo_pago"]]
                              + " confirmado para este producto.")
        if item["estado"] != "cotizado" or item["cantidad"] == 1:
            continue
        importes = [(m, centavos(valor) * item["cantidad"]) for m, valor in item["precios"].items()]
        if any(abs(total) > MAX_SAFE for _, total in importes):
            return {**salida, "estado": "error_consulta", "aclaraciones": ["El importe no se puede calcular de forma segura."]}
        item["subtotales"] = {m: numero_json(total / 100) for m, total in importes}
    cotizados = sum(1 for i in items if i["estado"] == "cotizado")
    estado = ("cotizado" if cotizados == len(items) else "parcial" if cotizados > 0
              else "requiere_aclaracion" if any(i["estado"] == "requiere_aclaracion" for i in items) else "no_disponible")
    totales = None
    if pedido["tipo_solicitud"] == "combo" and cotizados == len(items):
        comunes = [m for m in MEDIOS if all(centavos(item["precios"].get(m)) is not None for item in items)]
        sumas = [(m, sum(centavos(item["precios"][m]) * item["cantidad"] for item in items)) for m in comunes]
        if any(abs(total) > MAX_SAFE for _, total in sumas):
            return {**salida, "estado": "error_consulta", "aclaraciones": ["El importe no se puede calcular de forma segura."]}
        if sumas:
            totales = {m: numero_json(total / 100) for m, total in sumas}
    aclaraciones = list(dict.fromkeys(i["motivo"] for i in items if i.get("motivo")))
    return {**salida, "estado": estado, "items": items, "totales": totales, "aclaraciones": aclaraciones,
            # Desde el 16/11 ninguna cotización lleva pregunta final (pedido de Mateo).
            "pregunta_comercial_incluida": False,
            "mensaje_cotizacion": mensaje(items, totales, aclaraciones, pedido)}
