"""Buscador de vehículos de buscar_precio, tolerante a cómo escribe la gente por WhatsApp.

Cambio pedido por Mateo el 16/11/2026. El buscador que venía de n8n solo
encontraba el vehículo si el cliente escribía las palabras juntas y en el
mismo orden que en la planilla. Por eso «Corolla XLI» no encontraba la fila
«COROLLA RESPALDO T.DIVIDIDOS-  XLI 2017».

Cómo decide, en tres pasos:

1. Limpia igual el texto del cliente y cada rótulo de la planilla: minúsculas,
   sin tildes ni signos, letras dobles colapsadas (CAMRRY = camry), letras
   separadas de números (rav4 = RAV 4), sin años, sin fechas (8-2026+) y sin
   cilindradas (1.6). Aparta el relleno de WhatsApp, las notas de la planilla
   (respaldo, cabezal, cabina…) y las versiones (XEI, GNC…), que no definen el
   modelo pero sirven para desempatar.
2. Compara palabra por palabra. Acepta errores de tipeo en palabras largas,
   palabras pegadas o separadas (ecosport = ECO SPORT) y otro orden. Los
   números se comparan exactos: 208 no es 2008.
3. Decide:
   - candidatas: el modelo está claro. Puede haber varias filas del mismo
     modelo; el resto del motor pregunta cuál o filtra por año.
   - opciones: hay dos o más posibilidades reales (gol saveiro, una variante
     que la planilla no trae). Se le ofrecen al cliente.
   - confusion: la marca no cierra con el modelo (Toyota Raptor), está muy mal
     escrito (delta por Celta) o no es un vehículo (asdasd). Se le pide de nuevo.
   - no_encontrado: es un vehículo (nombró la marca o un modelo con números)
     que no está en la lista. Se lo invita al taller a tomar las medidas.

Regla de oro: nunca elegir otro vehículo. Ante la duda, se pregunta.

Corrección del 20/11/2026 (campaña de pruebas). Cabina simple y doble cabina son
vehículos distintos:
- si el cliente nombró una cabina, la fila de la otra no sirve (Saveiro cabina
  simple no es Saveiro DOBLE CABINA). Si el modelo está pero no con esa cabina,
  es no_encontrado;
- si no nombró ninguna, una fila que es de una sola cabina no se elige sola: va
  como opciones, junto con las demás variantes del modelo (Saveiro cross).
"""

from __future__ import annotations

import math
import re
import unicodedata
from functools import lru_cache

from .motor import MARCAS, palabras, separar_marca

# Lo que le dice el agente al cliente (textos de Mateo, 16/11/2026; van tal cual).
# confusion: la marca no cierra con el modelo, está muy mal escrito o no es un vehículo.
TEXTO_CONFUSION = ("Creo que tuviste una confusion, repetime tu modelo de vehiculo asi veo si contamos "
                   "con las medidas")
# no_encontrado: un vehículo de verdad que no está en la lista (fundas y tipo tapizado).
TEXTO_SIN_MEDIDAS = ("No contamos con las medidas de tu vehiculo, te invito a pasar por nuestro taller en "
                     "CABA para tomarlas y asi poder confeccionar las fundas")

# -- Vocabulario ---------------------------------------------------------------

# Palabras de WhatsApp que no nombran el vehículo.
RELLENO = {
    "tengo", "tiene", "es", "un", "una", "el", "la", "los", "las", "lo", "mi", "mis", "su", "de", "del",
    "para", "por", "auto", "autos", "coche", "carro", "camioneta", "camionetas", "vehiculo", "vehiculos",
    "modelo", "mod", "version", "ano", "anio", "anos", "fundas", "funda", "precio", "precios", "cuanto",
    "sale", "salen", "quiero", "queria", "necesito", "seria", "que", "q", "con", "y", "a", "al", "en",
    "hola", "buenas", "buen", "dia", "tardes", "porfa", "gracias", "marca", "tipo", "soy", "tenemos",
    "nuestro", "nuestra", "usado", "the", "o", "me", "te", "se", "si", "no", "era",
}

# Notas de configuración que la planilla agrega al nombre del vehículo.
NOTAS = {
    "respaldo", "respaldos", "entero", "enteros", "divididos", "dividido", "dividida", "divididas",
    "cabezal", "cabezales", "incorp", "incorporado", "incorporados", "con", "sin", "apoya", "apoyabrazos",
    "brazos", "brazo", "delantero", "delanteros", "delantera", "delanteras", "trasero", "traseros", "como",
    "butaca", "butacas", "butacon", "plazas", "plaza", "asientos", "asiento", "hasta", "y", "demas", "de",
    "la", "el", "los", "las", "del", "camion", "cabina", "doble", "simple", "nuevo", "nueva", "viejo", "vieja",
    "gen", "generacion", "truck", "van", "puertas", "puerta", "prtas", "ptas", "filas", "fila", "4x4", "4x2",
    "alternativa", "alternativas", "alternat", "otros", "otras", "todos", "todas", "nuevas", "solo",
    "habitaculo", "combo", "generation", "th", "desde", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
    "agosto", "septiembre", "setiembre", "octubre", "noviembre", "diciembre",
}

# Versiones, motor y equipamiento: el cliente las agrega y la planilla casi nunca las trae.
VERSIONES = {
    "xli", "xei", "seg", "gli", "glx", "gl", "gls", "gti", "gt", "gts", "se", "le", "lx", "ex", "exl", "lt",
    "ltz", "ls", "xl", "xls", "xlt", "srv", "srx", "limited", "highline", "comfortline", "confortline",
    "trendline", "titanium", "sel", "full", "pack", "plus", "active", "zetec", "feel", "tendance", "allure",
    "griffe", "intens", "dynamique", "privilege", "expression", "authentique", "confort", "life", "pure",
    "style", "drive", "precision", "attractive", "atractive", "essence", "sporting", "trekking", "freedom",
    "volcano", "ranch", "endurance", "working", "dx", "sx", "base", "premier", "platinum", "diesel", "nafta",
    "gnc", "turbo", "tdi", "tsi", "hdi", "cvt", "automatico", "automatica", "aut", "manual", "awd", "16v",
    "8v", "v6", "v8", "mt", "at", "cd", "cs", "lts", "sedan", "hatch", "hatchback", "rs", "ss", "zen",
    "intense", "iconic", "evolution", "outsider", "techno", "luxury", "comfort", "premium", "elite", "fire",
}

# Marcas y formas de escribirlas que no están en motor.MARCAS (que no se toca:
# también la usa la lectura de la planilla).
MARCAS_EXTRA = {
    "chevy": "chevrolet", "chev": "chevrolet", "volks": "volkswagen", "wolkswagen": "volkswagen",
    "volkswagem": "volkswagen", "wv": "volkswagen", "mb": "mercedes", "merce": "mercedes", "benz": "mercedes",
    "mercedesbenz": "mercedes", "reno": "renault", "renol": "renault", "renaul": "renault",
    "peugot": "peugeot", "pegeot": "peugeot", "citroem": "citroen", "hiundai": "hyundai",
    "hundai": "hyundai", "nisan": "nissan", "toyta": "toyota", "mitsubichi": "mitsubishi", "susuki": "suzuki",
    "jepp": "jeep", "jep": "jeep", "landrover": "land rover", "alfa": "alfa romeo", "alfaromeo": "alfa romeo",
    "ssang yong": "ssangyong", "byd": "byd", "gwm": "gwm", "great wall": "gwm", "haval": "haval",
    "jac": "jac", "jmc": "jmc", "baic": "baic", "dfsk": "dfsk", "mg": "mg", "ds": "ds", "geely": "geely",
    "foton": "foton", "lifan": "lifan", "changan": "changan", "dongfeng": "dongfeng", "jetour": "jetour",
    "omoda": "omoda", "volvo": "volvo", "porsche": "porsche", "lexus": "lexus", "mazda": "mazda",
    "isuzu": "isuzu", "seat": "seat", "skoda": "skoda", "opel": "opel", "smart": "smart", "tesla": "tesla",
    "ferrari": "ferrari", "lamborghini": "lamborghini", "maserati": "maserati", "jaguar": "jaguar",
    "infiniti": "infiniti", "acura": "acura", "cadillac": "cadillac", "lincoln": "lincoln", "gmc": "gmc",
    "hummer": "hummer", "saab": "saab", "daihatsu": "daihatsu", "daewoo": "daewoo", "chrysler": "chrysler",
    "scania": "scania", "agrale": "agrale", "jaecoo": "jaecoo", "kaiyi": "kaiyi", "lancia": "lancia",
    "rover": "rover", "pontiac": "pontiac", "plymouth": "plymouth", "proton": "proton", "tata": "tata",
    "mahindra": "mahindra", "ssangyong": "ssangyong", "kia": "kia", "audi": "audi", "bmw": "bmw",
}

_PRIMER_ANO, _ULTIMO_ANO = 1950, 2035
_MINIMO = 0.78  # parecido mínimo para considerar que dos palabras son la misma
_RX_NUMERO = re.compile(r"\d")
_RX_PARTES = re.compile(r"[a-z]+|\d+")
_RX_MILES = re.compile(r"\b(\d{1,3})\.(\d{3})\b")                              # 1.500 = 1500
_RX_T_PUNTO = re.compile(r"\bt\s*\.\s*(?=entero|dividid)")                     # T.ENTERO, T.DIVIDIDOS
# Mes y año pegados (8-2026, 10/2025). Con espacios no: «RAV 4 - 2015» es el RAV 4.
_RX_FECHA = re.compile(r"\b\d{1,2}[-/](?:19|20)\d{2}\b")
_RX_CILINDRADA = re.compile(r"\b\d[.,]\d{1,2}[a-z]*\b")                        # 1.6, 2,0, 1.5x, 2.0tsi
_RX_TRACCION = re.compile(r"\b(\d)\s*x\s*(\d)\b")                              # 4 x 4 = 4x4
_RX_CANTIDADES = re.compile(r"\b\d+\s*(?:puertas|prtas|ptas|plazas|asientos|butacas|filas)\b")
_ESTILO_PRODUCTO = {"de", "del", "la", "el", "los", "las", "para", "y", "con", "a", "en"}


# -- Palabras ------------------------------------------------------------------


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn").lower()


def _partir(palabra: str) -> list[str]:
    """Separa letras de números, salvo las siglas cortas pegadas a un número.

    bj40, hb20, sw4, rav4, i10 y 500x quedan juntas (son el nombre). corolla2018 y
    gol2010 se separan (es el año). 4x4 queda igual.
    """
    if re.fullmatch(r"\dx\d", palabra):
        return [palabra]
    partes = _RX_PARTES.findall(palabra)
    if len(partes) == 2:
        a, b = partes
        if a.isalpha() and b.isdigit() and len(a) <= 3 and not _es_ano(b):
            return [palabra]
        if a.isdigit() and b.isalpha() and len(b) == 1:
            return [palabra]
    return partes


def tokens(texto) -> list[str]:
    """Las palabras de un texto, limpias y comparables.

    Sin tildes ni signos; sin fechas (8-2026), cilindradas (1.6) ni cantidades
    de puertas o plazas; «4 x 4» queda «4x4»; letras separadas de números
    (rav4 = rav 4) salvo una letra sola seguida de número, que queda junta
    (c3, s10, i10, l200), así «C-3», «c 3» y «C3» son lo mismo.
    """
    t = _sin_tildes(str(texto or ""))
    t = _RX_MILES.sub(r"\1\2", t)
    t = _RX_T_PUNTO.sub(" ", t)
    t = _RX_FECHA.sub(" ", t)
    t = _RX_CILINDRADA.sub(" ", t)
    t = _RX_TRACCION.sub(r"\1x\2", t)
    t = _RX_CANTIDADES.sub(" ", t)
    t = palabras(t)
    partes: list[str] = []
    for palabra in t.split():
        partes.extend(_partir(palabra))
    juntas: list[str] = []
    for parte in partes:
        if juntas and len(juntas[-1]) == 1 and juntas[-1].isalpha() and parte.isdigit():
            juntas[-1] += parte
        else:
            juntas.append(parte)
    return juntas


def _colapsar(token: str) -> str:
    """Letras repetidas seguidas cuentan una vez: camrry = camry, corolla = corola."""
    return re.sub(r"([a-z])\1+", r"\1", token)


def _fonetica(token: str) -> str:
    """Cómo suena en castellano rioplatense: b/v, s/z/c, ll/y, k/c/q, h muda."""
    t = _colapsar(token)
    t = t.replace("ph", "f").replace("qu", "k").replace("ch", "#")
    t = re.sub(r"c(?=[ei])", "s", t)
    t = t.replace("c", "k").replace("z", "s").replace("v", "b").replace("w", "b").replace("y", "i")
    t = t.replace("x", "ks").replace("h", "").replace("#", "ch")
    return _colapsar(t)


def _distancia(a: str, b: str, tope: int) -> int:
    """Damerau-Levenshtein (con letras dadas vuelta). Devuelve tope + 1 si se pasa."""
    if abs(len(a) - len(b)) > tope:
        return tope + 1
    previa2: list[int] | None = None
    previa = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        actual = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            costo = 0 if a[i - 1] == b[j - 1] else 1
            actual[j] = min(previa[j] + 1, actual[j - 1] + 1, previa[j - 1] + costo)
            if previa2 is not None and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                actual[j] = min(actual[j], previa2[j - 2] + 1)
        if min(actual) > tope:
            return tope + 1
        previa2, previa = previa, actual
    return min(previa[len(b)], tope + 1)


@lru_cache(maxsize=200_000)
def parecido(a: str, b: str) -> float:
    """Qué tan parecidas son dos palabras (0 = nada, 1 = iguales)."""
    if a == b:
        return 1.0
    if _RX_NUMERO.search(a) or _RX_NUMERO.search(b):
        # Los números nombran el modelo: exactos. Las letras pegadas pueden sonar
        # igual (rav4 = RAB 4 de la planilla).
        pa, pb = _RX_PARTES.findall(a), _RX_PARTES.findall(b)
        if len(pa) == len(pb) and all(
                x == y if x.isdigit() or y.isdigit() else _fonetica(x) == _fonetica(y) for x, y in zip(pa, pb)):
            return 0.93
        return 0.0
    ca, cb = _colapsar(a), _colapsar(b)
    corto = min(len(ca), len(cb))
    if corto <= 2:
        return 0.0  # ka, up, gt: solo iguales
    if ca == cb:
        return 0.97
    for x, y in ((ca, cb), (cb, ca)):
        if x.startswith("es") and len(x) >= 5 and x[1:] == y:
            return 0.95  # esprinter = sprinter, estrada = strada
    fa, fb = _fonetica(a), _fonetica(b)
    if fa == fb:
        return 0.93
    if corto >= 4 and (ca + "s" == cb or cb + "s" == ca):
        return 0.9  # plural: argo = argos
    if corto <= 4:
        # Palabras cortas: dos letras dadas vuelta (hvr = hrv) valen. Una letra cambiada
        # (clia / clio) solo para ofrecerla como opción. gol no es golf: no se agregan letras.
        if len(ca) == len(cb) and _distancia(ca, cb, 1) == 1:
            return 0.85 if sorted(ca) == sorted(cb) else (0.79 if corto == 4 else 0.0)
        return 0.0
    tope = 2 if corto >= 7 else 1
    d = _distancia(ca, cb, tope)
    if d <= tope:
        return 0.88 if d == 1 else 0.78
    # Dos errores en una palabra mediana, si suena casi igual (hylus = hilux).
    if min(len(fa), len(fb)) >= 4 and _distancia(fa, fb, 1) <= 1:
        return 0.8
    return 0.0


def _seguro(a: str, b: str, p: float) -> bool:
    """Un parecido es seguro si es casi igual, o si no cambia cómo empieza la palabra.

    «delta» y «celta» se parecen, pero son otro auto: eso se pregunta.
    """
    if p >= 0.93:
        return True
    if p < 0.8:
        return False  # dos errores, o una letra cambiada en una palabra corta: se pregunta
    return _colapsar(a)[:1] == _colapsar(b)[:1] or _fonetica(a)[:1] == _fonetica(b)[:1]


# -- Marcas --------------------------------------------------------------------

_ALIAS_MARCAS = {**{palabras(k): v for k, v in MARCAS.items()}, **MARCAS_EXTRA}
_UNA_PALABRA = {k: v for k, v in _ALIAS_MARCAS.items() if " " not in k}
_VARIAS = {k: v for k, v in _ALIAS_MARCAS.items() if " " in k}


def _marca_de(token: str, siguiente: str | None = None) -> str | None:
    """Si la palabra es una marca (también mal escrita). Las cortas (ds, mg, ram) solo
    si no van pegadas a un número: «ds3» es un modelo."""
    if token in _UNA_PALABRA:
        if len(token) <= 3 and siguiente is not None and siguiente.isdigit():
            return None
        return _UNA_PALABRA[token]
    if len(token) >= 5 and not _RX_NUMERO.search(token):
        for alias, marca in _UNA_PALABRA.items():
            if len(alias) >= 5 and _distancia(token, alias, 1) <= 1:
                return marca
    return None


def _marca_al_principio(lista: list[str]) -> tuple[str | None, list[str]]:
    """La marca escrita al principio de un rótulo de la planilla (BYD Shark, PEUGUEOT 2008)."""
    if len(lista) >= 2:
        doble = f"{lista[0]} {lista[1]}"
        for alias, marca in _VARIAS.items():
            if doble == alias or _distancia(doble, alias, 1) <= 1:
                return marca, lista[2:]
    if lista:
        marca = _marca_de(lista[0], lista[1] if len(lista) > 1 else None)
        if marca and len(lista) > 1:
            return marca, lista[1:]
    return None, lista


def separar_marca_consulta(lista: list[str]) -> tuple[str | None, list[str]]:
    """Encuentra la marca en cualquier lugar del texto del cliente (también mal escrita o partida)."""
    for i in range(len(lista) - 1):
        doble = f"{lista[i]} {lista[i + 1]}"
        for alias, marca in _VARIAS.items():
            if doble == alias or _distancia(doble, alias, 1) <= 1:
                return marca, lista[:i] + lista[i + 2:]
        junta = lista[i] + lista[i + 1]
        if junta in _UNA_PALABRA and len(junta) >= 5:
            return _UNA_PALABRA[junta], lista[:i] + lista[i + 2:]
    for i, token in enumerate(lista):
        marca = _marca_de(token, lista[i + 1] if i + 1 < len(lista) else None)
        if marca:
            return marca, lista[:i] + lista[i + 1:]
    return None, lista


# -- La planilla ----------------------------------------------------------------


def _es_ano(token: str) -> bool:
    return token.isdigit() and len(token) == 4 and _PRIMER_ANO <= int(token) <= _ULTIMO_ANO


# Corrección del 20/11 (campaña de pruebas). Cabina simple y doble cabina son vehículos
# distintos: la fila de una no sirve para la otra. Y si el cliente no nombró la cabina, una
# fila que es de una sola cabina no es «la de siempre»: no se elige sola.


_CABINA = {"cabina", "cabinas", "cab"}


def _cabinas(lista: list[str]) -> frozenset[str]:
    """Las cabinas que nombra un texto ya separado en palabras: simple, doble, las dos o ninguna."""
    if not any(t in _CABINA for t in lista):
        return frozenset()
    return frozenset(t for t in ("simple", "doble") if t in lista)


def misma_cabina(rotulo, detalle) -> bool:
    """¿El detalle solo nombra una cabina y la fila es de esa cabina?

    Sirve para la configuración de alfombra: «cabina doble» coincide con una fila que dice
    «DOBLE CABINA», aunque no esté escrita en el mismo orden.
    """
    dicho = tokens(detalle)
    return bool(_cabinas(dicho)) and all(t in _CABINA or t in ("simple", "doble") for t in dicho) and (
        _cabinas(dicho) <= _cabinas(tokens(rotulo)))


def _cabinas_del_cliente(modelo, detalle=None) -> frozenset[str]:
    """La cabina que nombró el cliente junto al vehículo o en la configuración.

    Junto al vehículo alcanza con «simple» o «doble» (hilux doble), salvo que hable de la
    tracción. En la configuración tiene que decir «cabina»: ahí «doble» puede ser otra cosa.
    """
    lista = tokens(modelo)
    sueltas = frozenset() if "traccion" in lista else frozenset(t for t in ("simple", "doble") if t in lista)
    return (_cabinas(lista) or sueltas) | _cabinas(tokens(detalle))


def solo_cabina(detalle) -> bool:
    """¿El detalle no dice otra cosa que la cabina? («cabina doble», «doble cabina»)."""
    dicho = tokens(detalle)
    return bool(_cabinas(dicho)) and all(t in _CABINA or t in ("simple", "doble") for t in dicho)


def cabina_dicha(texto) -> str | None:
    """«simple» o «doble» si el texto nombra una sola cabina; None si no nombra ninguna o nombra las dos."""
    dichas = _cabinas(tokens(texto))
    return next(iter(dichas)) if len(dichas) == 1 else None


def cabina_sin_nombrar(rotulo, modelo=None, detalle=None) -> bool:
    """¿La fila es de una sola cabina (simple o doble) y el cliente no la nombró?

    `modelo` y `detalle` son el vehículo y la configuración que llegaron en la consulta.
    """
    de_la_fila = _cabinas(tokens(rotulo))
    return len(de_la_fila) == 1 and not de_la_fila & _cabinas_del_cliente(modelo, detalle)


@lru_cache(maxsize=8192)
def _fila(rotulo: str, marca_seccion: str | None, con_marcas: bool) -> dict:
    """Lo que importa de una fila para buscar: marca, palabras del modelo y el resto."""
    todas = tokens(rotulo)
    marca = None
    if con_marcas:
        marca, todas = _marca_al_principio(todas)
        marca = marca or separar_marca(rotulo)["marca"] or marca_seccion
    modelo, extras = [], []
    for t in todas:
        if con_marcas and (t in NOTAS or t in VERSIONES):
            extras.append(t)
        elif not con_marcas and t in _ESTILO_PRODUCTO:
            continue
        else:
            modelo.append(t)
    # Los años no nombran el modelo, salvo un número al principio del nombre
    # («2008», «Peugeot 2008 (Hasta Junio 2024)», «2008/3008»): ese es el modelo.
    modelo = [t for i, t in enumerate(modelo) if not _es_ano(t) or (i == 0 and todas and todas[0] == t)]
    if not modelo:
        # Una fila que solo tiene palabras «de versión» (ADVENTURE, SR): esas la nombran.
        modelo = [t for t in extras if t not in NOTAS] or list(extras)
        extras = [t for t in extras if t not in modelo]
    return {"marca": marca, "modelo": modelo, "extras": extras, "cabinas": _cabinas(tokens(rotulo))}


def _unidades(lista: list[str]) -> list[tuple[str, tuple[int, ...]]]:
    """Cada palabra sola y las uniones de 2 y 3 seguidas (t cross = tcross, eco sport = ecosport).

    Una unión tiene que tener letras: «1 8» no es «18».
    """
    salida = [(t, (i,)) for i, t in enumerate(lista)]
    for largo in (2, 3):
        for i in range(len(lista) - largo + 1):
            partes = lista[i:i + largo]
            unida = "".join(partes)
            # «t cross», «x terra», «cr v» se unen; «clase c» no: esa letra final es la clase.
            letra_final = len(partes[-1]) == 1 and partes[-1].isalpha()
            if not unida.isdigit() and not (letra_final and len(partes[-2]) > 3):
                salida.append((unida, tuple(range(i, i + largo))))
    return salida


def _alinear(consulta: list[str], fila: list[str]) -> tuple[dict[int, tuple[float, bool]], set[int]]:
    """Empareja palabras de la consulta con palabras de la fila, sin repetir ninguna.

    Devuelve, por cada palabra de la consulta encontrada, (parecido, seguro), y qué
    palabras de la fila quedaron explicadas.
    """
    pares = []
    for uq, iq in _unidades(consulta):
        for uf, jf in _unidades(fila):
            if len(iq) > 1 and len(jf) > 1:
                continue
            p = parecido(uq, uf)
            if p >= _MINIMO:
                pares.append((p, len(iq) + len(jf), iq, jf, _seguro(uq, uf, p)))
    pares.sort(key=lambda x: (-x[0], -x[1]))
    usadas_q: dict[int, tuple[float, bool]] = {}
    usadas_f: set[int] = set()
    for p, _, iq, jf, seguro in pares:
        if any(i in usadas_q for i in iq) or any(j in usadas_f for j in jf):
            continue
        for i in iq:
            usadas_q[i] = (p, seguro)
        usadas_f.update(jf)
    return usadas_q, usadas_f


# -- La búsqueda ----------------------------------------------------------------


def _limpiar_consulta(texto: str, con_marcas: bool) -> tuple[str | None, list[str], list[str]]:
    """Marca, palabras del modelo y palabras de versión o nota que escribió el cliente."""
    if not con_marcas:
        return None, [t for t in tokens(texto) if t not in _ESTILO_PRODUCTO], []
    lista = [t for t in tokens(texto) if t not in RELLENO]
    marca, lista = separar_marca_consulta(lista)
    # Palabras que nombran el modelo (no versiones ni notas): «2008 allure» sigue siendo el 2008.
    letras = [t for t in lista if not t.isdigit() and t not in VERSIONES and t not in NOTAS]
    modelo, extras = [], []
    for i, t in enumerate(lista):
        if _es_ano(t) and (letras or i > 0):
            continue  # «corolla 2018», «2008 del 2019»: el año lo usa el resto del motor
        if t in NOTAS or t in VERSIONES:
            extras.append(t)
        else:
            modelo.append(t)
    if not modelo:
        # «adventure», «sr»: palabras de versión que en la planilla son un modelo.
        modelo = [t for t in extras if t not in NOTAS]
        extras = [t for t in extras if t in NOTAS]
    return marca, modelo, extras


def _clase(token: str) -> str:
    """Para ver si dos palabras sueltas se contradicen: números y letras solas."""
    if _RX_NUMERO.search(token):
        return "numero"
    if len(token) == 1:
        return "letra"
    return "palabra"


def _puede_ser_ano(token: str, hay_otras: bool) -> bool:
    """Un número que probablemente es el año: 2018, o 18 si el cliente nombró el modelo."""
    return _es_ano(token) or (hay_otras and token.isdigit() and len(token) == 2)


def _sin_resultado(marca: str | None, consulta: list[str]) -> dict:
    """Nada sirve. Si nombró la marca o un modelo con números, es un vehículo de verdad
    que no está en la lista; si no (asdasd, auto rojo, solo «toyota»), que lo repita."""
    if consulta and (marca or any(_RX_NUMERO.search(t) for t in consulta)):
        return {"estado": "no_encontrado", "indices": []}
    return {"estado": "confusion", "indices": []}


def buscar(modelo: str, filas: list[dict], detalle: str | None = None) -> dict:
    """Elige las filas de una hoja que corresponden a lo que escribió el cliente.

    Devuelve {"estado": "candidatas" | "opciones" | "confusion" | "no_encontrado",
    "indices": [...]}.

    `detalle` es la configuración que llegó aparte del vehículo. Solo se mira si nombra la
    cabina (en alfombra llega «cabina simple»).
    """
    # Todas las hojas se leen igual: también las que no tienen secciones por marca
    # (ESPUMAS) traen la marca en el nombre («FIAT UNO S R»).
    con_marcas = True
    infos = [_fila(str(f.get("modelo") or ""), f.get("marca"), con_marcas) for f in filas]
    marca, consulta, extras = _limpiar_consulta(str(modelo or ""), con_marcas)
    # Corrección del 20/11 (campaña de pruebas): la cabina que nombró el cliente, junto al
    # vehículo o en la configuración.
    cabinas = _cabinas_del_cliente(modelo, detalle)
    if _cabinas(tokens(detalle)):
        extras = extras + [t for t in ("cabina", *sorted(cabinas)) if t not in extras]
    sin_esa_cabina = False
    perdidas: set[str] = set()  # palabras del cliente que explicaba una fila descartada por la cabina

    # El vocabulario de la hoja (con las palabras unidas) y cuánto distingue cada palabra.
    conteo: dict[str, int] = {}
    vocabulario: set[str] = set()
    for info in infos:
        for t in set(info["modelo"]):
            conteo[_colapsar(t)] = conteo.get(_colapsar(t), 0) + 1
        vocabulario.update(u for u, _ in _unidades(info["modelo"]))
        vocabulario.update(info["extras"])
    total_filas = max(len(infos), 1)

    def conocida(t: str) -> bool:
        return any(parecido(t, v) >= _MINIMO for v in vocabulario)

    separadas = []
    for t in consulta:
        if not conocida(t) and not _RX_NUMERO.search(t):
            # «golcito», «corsita», «fiestita»: el diminutivo de un modelo.
            for fin, agrega in (("cito", ""), ("cita", "a"), ("ito", "o"), ("ita", "a"), ("ito", ""), ("ita", "")):
                if t.endswith(fin) and len(t) - len(fin) >= 2 and conocida(t[:-len(fin)] + agrega):
                    t = t[:-len(fin)] + agrega
                    break
        if con_marcas and not conocida(t):
            # «minicooper», «vwgol»: la marca vino pegada al modelo.
            for corte in range(2, len(t) - 1):
                propia = _UNA_PALABRA.get(t[:corte])
                if propia and conocida(t[corte:]):
                    marca = marca or propia
                    t = t[corte:]
                    break
        separadas.append(t)
    consulta = separadas

    # Lo que no se parece a nada de la hoja (una versión que la planilla no trae, un
    # apodo) no cuenta. Si no queda nada conocido, no hay modelo: se pregunta.
    # Los números y las letras sueltas se quedan siempre: «Tiggo 7» no es «Tiggo 3»
    # y «Clase C» no es «Clase A», aunque el 7 o la C no estén en la planilla.
    conocidas = [t for t in consulta if _RX_NUMERO.search(t) or len(t) == 1 or conocida(t) or any(
        conocida(u) for u, idx in _unidades(consulta) if len(idx) > 1 and t in u)]
    hay_letras = any(not t.isdigit() for t in conocidas)
    # «corolla 18»: con el modelo nombrado, un número de dos cifras suelto es el año
    # (no si va después de una sigla: «bj 40», «hb 20»).
    conocidas = [t for i, t in enumerate(conocidas) if not (
        hay_letras and t.isdigit() and len(t) == 2
        and not (i > 0 and conocidas[i - 1].isalpha() and len(conocidas[i - 1]) <= 3))]
    if not conocidas:
        return _sin_resultado(marca, consulta)
    consulta = conocidas
    hay_otras = len(consulta) > 1

    def peso(t: str) -> float:
        valor = math.log(1 + total_filas / conteo.get(_colapsar(t), 1))
        # Las siglas de dos letras (SR, GT, XL) suelen ser versiones: pesan menos.
        return valor / 2 if t.isalpha() and len(t) <= 2 else valor

    total = sum(peso(t) for t in consulta)
    con_letras = any(not t.isdigit() for t in consulta)
    resultados = []
    for indice, info in enumerate(infos):
        encontradas, explicadas = _alinear(consulta, info["modelo"])
        if not encontradas:
            continue
        if con_letras and all(consulta[i].isdigit() for i in encontradas):
            continue  # «rav 4» no es «SW4» solo porque coincide el 4
        faltan = [consulta[i] for i in range(len(consulta)) if i not in encontradas]
        sobran = [info["modelo"][j] for j in range(len(info["modelo"])) if j not in explicadas]
        # Números o letras sueltas distintos de los dos lados: es otro modelo
        # (Tiggo 5 no es Tiggo 7; Clase C no es Clase A). Un año no cuenta.
        if any(_clase(f) != "palabra" and not _puede_ser_ano(f, hay_otras)
               and any(_clase(s) == _clase(f) for s in sobran) for f in faltan):
            continue
        # Corrección del 20/11 (campaña de pruebas): cabina simple y doble cabina se contradicen
        # (Saveiro cabina simple no es Saveiro DOBLE CABINA).
        if cabinas and info["cabinas"] and not cabinas & info["cabinas"]:
            sin_esa_cabina = True
            perdidas.update(consulta[i] for i in encontradas)
            continue
        de_mas = sum(1 for s in sobran if _clase(s) == "palabra" and len(s) >= 3)
        puntaje = sum(peso(consulta[i]) * p for i, (p, _) in encontradas.items())
        # Las versiones y notas que el cliente sí dijo (XLI, doble cabina) suman un poco.
        if extras and info["extras"]:
            puntaje += 0.6 * len(_alinear(extras, info["extras"])[1])
        resultados.append({
            "indice": indice,
            "puntaje": puntaje,
            "cubre": sum(peso(consulta[i]) for i in encontradas) / total,
            "faltan": faltan,
            # Lo que la fila tiene y el cliente no dijo (CROSS en COROLLA CROSS) le resta.
            "sobran": de_mas,
            "marca": info["marca"],
            "seguro": all(s for _, s in encontradas.values()),
            "explica": tuple(sorted(_colapsar(info["modelo"][j]) for j in explicadas)),
            # Corrección del 20/11: es de una sola cabina y el cliente no nombró ninguna.
            "otra_cabina": len(info["cabinas"]) == 1 and not cabinas,
            # El cliente nombró la cabina; la fila no dice cabina y agrega otra cosa al nombre
            # (Saveiro cross).
            "otra_variante": bool(cabinas) and not info["cabinas"] and de_mas > 0,
        })
    if sin_esa_cabina:
        # La planilla distingue cabinas para este modelo: una fila que no dice cabina y agrega
        # otra cosa al nombre es otra variante, no la que pidió el cliente.
        resultados = [r for r in resultados if not r["otra_variante"]]
    if not resultados:
        if sin_esa_cabina:
            # El modelo está en la lista, pero no con esa cabina: no es una confusión.
            return {"estado": "no_encontrado", "indices": []}
        return _sin_resultado(marca, consulta)

    def mejores(lista: list[dict]) -> list[dict]:
        """Las que más explican lo que dijo el cliente y, entre esas, las que menos agregan."""
        tope = max(r["puntaje"] for r in lista)
        primeras = [r for r in lista if r["puntaje"] >= tope - 1e-9]
        menos = min(r["sobran"] for r in primeras)
        return [r for r in primeras if r["sobran"] == menos]

    if marca:
        # Las filas sin marca (hojas sin secciones) sirven para cualquier marca.
        propias = [r for r in resultados if r["marca"] in (marca, None)]
        if not propias:
            # La marca no cierra con el modelo (Toyota Raptor): nunca se cotiza, se le
            # pide que lo repita. Si el modelo tampoco se parece a nada, no lo tenemos.
            fuertes = [r for r in mejores(resultados) if not r["faltan"] and r["seguro"]]
            if fuertes:
                return {"estado": "confusion", "indices": [r["indice"] for r in fuertes][:12]}
            return _sin_resultado(marca, consulta)
        resultados = propias

    elegidas = mejores(resultados)
    indices = [r["indice"] for r in elegidas]
    base = set(elegidas[0]["explica"])
    cabezas = {_colapsar(infos[r["indice"]]["modelo"][0]) for r in elegidas if infos[r["indice"]]["modelo"]}

    # Lo que el cliente dijo con letras y ninguna fila elegida explica.
    faltan = set(elegidas[0]["faltan"])
    for r in elegidas[1:]:
        faltan &= set(r["faltan"])
    faltan = {t for t in faltan if not t.isdigit()}
    if faltan & perdidas:
        # Corrección del 20/11 (campaña de pruebas): nombró un modelo cuya única fila se descartó
        # por la cabina (gol saveiro cabina simple). No se cotiza el otro: esa variante no está.
        return {"estado": "no_encontrado", "indices": []}
    if faltan:
        # Otra fila lo explica y es del mismo modelo (eco sport kinetic → ECO KINECTIC),
        # o lo que sobra es el nombre de otro modelo (gol saveiro): que elija.
        otras = [r for r in sorted(resultados, key=lambda r: -r["puntaje"])
                 if r["indice"] not in indices and any(t not in r["faltan"] for t in faltan)
                 and (set(r["explica"]) & base
                      or _colapsar(infos[r["indice"]]["modelo"][0]) in cabezas
                      or any(parecido(t, infos[r["indice"]]["modelo"][0]) >= 0.85 for t in faltan))]
        if otras:
            # Prueba del 21/11 (R09): dijo «ecosport kinetik» y se le preguntaba «ECO SPORT o ECO
            # KINECTIC?». Si una sola fila explica sin dudas lo que a la elegida le falta, y es del
            # mismo modelo (empieza igual), es esa.
            # «Sin dudas» acá es que cada palabra que faltaba se parece a una de esa fila y empieza
            # igual (kinetik / KINECTIC): al ser la única variante del mismo modelo, alcanza.
            if len(otras) == 1 and not faltan & set(otras[0]["faltan"]) and (
                    _colapsar(infos[otras[0]["indice"]]["modelo"][0]) in cabezas) and all(
                    any(parecido(t, m) >= _MINIMO and _colapsar(t)[:1] == _colapsar(m)[:1]
                        for m in infos[otras[0]["indice"]]["modelo"]) for t in faltan):
                return {"estado": "candidatas", "indices": [otras[0]["indice"]]}
            return {"estado": "opciones", "indices": (indices + [r["indice"] for r in otras])[:12]}
        # Dio un detalle que la planilla no tiene y el modelo tiene variantes
        # (Fiesta Kinetic → FIESTA, FIESTA KINECT, FIESTA MAX): que elija.
        familia = [r for r in resultados if r["indice"] not in indices and set(r["explica"]) >= base
                   and r["sobran"] > 0]
        if familia:
            return {"estado": "opciones", "indices": (indices + [r["indice"] for r in familia])[:12]}
    if elegidas[0]["cubre"] < 0.5:
        return {"estado": "opciones", "indices": indices[:12]}
    if not all(r["seguro"] for r in elegidas):
        # Muy mal escrito: un parecido que cambia cómo empieza la palabra (delta / celta),
        # dos errores, o una letra cambiada en una palabra corta (clia). Que lo repita.
        return {"estado": "confusion", "indices": indices[:12]}
    if len({r["explica"] for r in elegidas}) > 1 and not all(
            all(p >= 0.93 for p, _ in _alinear(consulta, infos[r["indice"]]["modelo"])[0].values())
            for r in elegidas):
        # Mal escrito y parecido a modelos distintos: que lo repita.
        return {"estado": "confusion", "indices": indices[:12]}
    if all(r["otra_cabina"] for r in elegidas):
        # Corrección del 20/11 (campaña de pruebas): una fila de una cabina que el cliente no
        # nombró (Saveiro DOBLE CABINA) no se elige sola. Se ofrece con las demás variantes
        # del modelo (Saveiro cross).
        variantes = [r["indice"] for r in resultados if r["indice"] not in indices and r["seguro"]
                     and set(r["explica"]) >= base]
        return {"estado": "opciones", "indices": (indices + variantes)[:12]}
    return {"estado": "candidatas", "indices": indices[:12]}
