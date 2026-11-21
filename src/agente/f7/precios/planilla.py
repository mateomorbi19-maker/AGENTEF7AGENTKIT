"""Lectura en vivo de la planilla oficial de precios de F7.

En n8n son dos GET a la API de Google Sheets (metadata y values:batchGet con
UNFORMATTED_VALUE) con una credencial que acá no tenemos. La planilla está
compartida por enlace, así que la bajamos entera como XLSX y la convertimos a
lo mismo que devuelve batchGet: filas de valores, celdas vacías como "", sin
vacías al final de cada fila ni filas vacías al final, números como número y
el valor calculado de las fórmulas.

Sin caché: cada consulta baja la planilla de nuevo, como hoy.

Diferencias con n8n (el XLSX no trae todo lo de la API):
- No trae los gid: se valida el título exacto de cada hoja y el gid se toma
  de la tabla fija (es el mismo que exige n8n).
- No trae el tamaño de la grilla: los topes (60 columnas, 100.000 celdas) se
  controlan sobre lo que tiene datos.
"""

from __future__ import annotations

import datetime as dt
import io
import time

import httpx

from .motor import numero_json

SHEET_ID = "1dl7hNofQp8v57h1Veodd3XqFctJxAvgAA2qXVtnE1ZU"
URL_XLSX = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx"
# Título exacto → gid, como en transporte.mjs.
HOJAS = {
    "Fundas a medida": 877828453, "TIPO TAPIZADO": 613213257, "TAPICERIA": 972378170,
    "Termoformadas": 0, "Funda Baúl - Antiderrame": 941782890,
    "Cobertores de caja ": 2002506112, "ESPUMAS": 1953604758, "Otros": 59879218,
}
TIMEOUT = 30.0
INTENTOS = 2
ESPERA = 1.0
MAX_COLUMNAS = 60
MAX_CELDAS = 100_000
_MAX_REDIRECCIONES = 5
_EPOCA_SHEETS = dt.datetime(1899, 12, 30)


class ErrorPlanilla(Exception):
    """No se pudo bajar, validar o leer la planilla."""


def _host_permitido(url: httpx.URL) -> bool:
    host = (url.host or "").lower()
    return url.scheme == "https" and (host == "docs.google.com" or host.endswith(".googleusercontent.com"))


def _bajar_una_vez(cliente: httpx.Client) -> bytes:
    url = httpx.URL(URL_XLSX)
    for _ in range(_MAX_REDIRECCIONES + 1):
        respuesta = cliente.get(url)
        if respuesta.is_redirect:
            destino = url.join(respuesta.headers.get("location", ""))
            if not _host_permitido(destino):
                raise ErrorPlanilla("redireccion_no_permitida")
            url = destino
            continue
        if respuesta.status_code != 200:
            raise ErrorPlanilla(f"http_{respuesta.status_code}")
        return respuesta.content
    raise ErrorPlanilla("demasiadas_redirecciones")


def bajar_xlsx() -> bytes:
    """Baja la planilla como XLSX: 30 s por intento, 2 intentos con 1 s entre medio."""
    ultimo: Exception | None = None
    for intento in range(INTENTOS):
        if intento:
            time.sleep(ESPERA)
        try:
            with httpx.Client(follow_redirects=False, timeout=TIMEOUT) as cliente:
                return _bajar_una_vez(cliente)
        except (httpx.HTTPError, ErrorPlanilla) as error:
            ultimo = error
    raise ErrorPlanilla("no_se_pudo_bajar") from ultimo


def _valor(celda):
    """El valor como lo da UNFORMATTED_VALUE: fechas como número de serie, enteros sin «.0»."""
    if celda is None:
        return ""
    if isinstance(celda, bool) or isinstance(celda, str):
        return celda
    if isinstance(celda, dt.datetime):
        return numero_json((celda - _EPOCA_SHEETS).total_seconds() / 86400)
    if isinstance(celda, dt.date):
        return numero_json(float((celda - _EPOCA_SHEETS.date()).days))
    if isinstance(celda, dt.time):
        segundos = celda.hour * 3600 + celda.minute * 60 + celda.second + celda.microsecond / 1e6
        return numero_json(segundos / 86400)
    if isinstance(celda, dt.timedelta):
        return numero_json(celda.total_seconds() / 86400)
    if isinstance(celda, (int, float)):
        return numero_json(celda)
    return str(celda)


def filas_de_hoja(hoja) -> list[list]:
    """Una hoja de openpyxl → las filas como las devuelve batchGet (majorDimension=ROWS)."""
    filas: list[list] = []
    for fila in hoja.iter_rows(values_only=True):
        valores = [_valor(c) for c in fila]
        while valores and valores[-1] == "":
            valores.pop()
        filas.append(valores)
    while filas and not filas[-1]:
        filas.pop()
    return filas


def _letra(n: int) -> str:
    col = ""
    while n:
        n -= 1
        col = chr(65 + n % 26) + col
        n //= 26
    return col


def hojas_desde_xlsx(contenido: bytes, titulos: list[str]) -> list[dict]:
    """Las hojas pedidas, con los mismos controles que prepararRangos y leerValores.

    Devuelve [{title, sheetId, range, values}], en el orden pedido y sin repetidas.
    """
    from openpyxl import load_workbook

    if not isinstance(titulos, list) or not titulos or len(titulos) > 8:
        raise ErrorPlanilla("hojas_invalidas")
    try:
        libro = load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
    except Exception as error:  # un XLSX roto es una planilla que no se pudo leer
        raise ErrorPlanilla("xlsx_invalido") from error
    try:
        resultado = []
        for titulo in dict.fromkeys(titulos):
            if titulo not in HOJAS:
                raise ErrorPlanilla("hoja_no_permitida")
            if libro.sheetnames.count(titulo) != 1:
                raise ErrorPlanilla("estructura_de_hojas_cambio")
            valores = filas_de_hoja(libro[titulo])
            filas = max(len(valores), 1)
            columnas = max((len(f) for f in valores), default=1) or 1
            if columnas > MAX_COLUMNAS or filas * columnas > MAX_CELDAS:
                raise ErrorPlanilla("dimensiones_fuera_de_limite")
            rango = "'" + titulo.replace("'", "''") + f"'!A1:{_letra(columnas)}{filas}"
            resultado.append({"title": titulo, "sheetId": HOJAS[titulo], "range": rango, "values": valores})
        return resultado
    finally:
        libro.close()


def leer_hojas(titulos: list[str]) -> list[dict]:
    """Baja la planilla oficial ahora mismo y devuelve las hojas pedidas. Lanza ErrorPlanilla si falla."""
    return hojas_desde_xlsx(bajar_xlsx(), titulos)
