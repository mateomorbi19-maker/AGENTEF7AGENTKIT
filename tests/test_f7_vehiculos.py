"""F7: el buscador de vehículos de buscar_precio (pedido de Mateo del 16/11/2026).

Tiene que encontrar el vehículo como lo escribe la gente por WhatsApp y nunca
elegir otro: ante la duda, ofrece opciones; si no hay nada, pide el modelo de
nuevo. Sin red y sin precios reales (los importes son inventados).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agente.f7.precios.motor import cotizar, normalizar_entrada  # noqa: E402
from agente.f7.precios.vehiculos import (  # noqa: E402
    TEXTO_CONFUSION,
    TEXTO_SIN_MEDIDAS,
    buscar,
    parecido,
    tokens,
)

# Nombres como los de la planilla real, con sus errores (CAMRRY, HVR, Compast, CRUCE).
CATALOGO = [
    ("toyota", "COROLLA RESPALDO T.ENTERO  - 2004"), ("toyota", "COROLLA 2025"),
    ("toyota", "COROLLA RESPALDO T.DIVIDIDOS-  XLI 2017"), ("toyota", "COROLLA CROSS"),
    ("toyota", "HILUX CABINA DOBLE - 2005/2015"), ("toyota", "HILUX CABINA SIMPLE"),
    ("toyota", "CAMRRY"), ("toyota", "RAV 4 - 2015"), ("toyota", "SW4 2010"),
    ("honda", "HVR"), ("honda", "CRV"),
    ("ford", "ECO SPORT"), ("ford", "ECO KINECTIC"), ("ford", "RAPTOR"), ("ford", "KA"),
    ("volkswagen", "GOL"), ("volkswagen", "GOL TREND"), ("volkswagen", "Saveiro DOBLE CABINA"),
    ("volkswagen", "T-CROSS"),
    ("peugeot", "208 GT"), ("peugeot", "208"), ("peugeot", "2008"), ("peugeot", "3008"),
    ("fiat", "500x / 600"), ("fiat", "CRONOS"),
    ("mercedes", "CLASE A"), ("chery", "TIGGO 3"),
    ("chevrolet", "S-10 ( CABINA SIMPLE )"), ("chevrolet", "S-10 ( CABINA DOBLE )"), ("chevrolet", "CRUCE"),
    ("jeep", "Compast"),
]
FILAS = [{"modelo": m, "marca": marca} for marca, m in CATALOGO]
COROLLAS = {"COROLLA RESPALDO T.ENTERO  - 2004", "COROLLA 2025", "COROLLA RESPALDO T.DIVIDIDOS-  XLI 2017"}


def nombres(resultado: dict) -> set[str]:
    return {FILAS[i]["modelo"] for i in resultado["indices"]}


@pytest.mark.parametrize("texto, esperado", [
    # Lo que no encontraba el buscador de n8n.
    ("Corolla XLI", {"COROLLA RESPALDO T.DIVIDIDOS-  XLI 2017"}),
    ("corola xli 2017", {"COROLLA RESPALDO T.DIVIDIDOS-  XLI 2017"}),
    # Incompleto, con versión de más, con año, con relleno, diminutivo, mal escrito.
    ("Corolla", COROLLAS),
    ("tengo un corolla xei 2016", COROLLAS),
    ("corolla 18", COROLLAS),
    ("corolita", COROLLAS),
    ("toyota corolla cross", {"COROLLA CROSS"}),
    ("hylux doble cabina", {"HILUX CABINA DOBLE - 2005/2015"}),
    ("cabina doble hilux", {"HILUX CABINA DOBLE - 2005/2015"}),
    ("chevrolet s10 doble cabina", {"S-10 ( CABINA DOBLE )"}),
    ("gol trend 1.6 pack", {"GOL TREND"}),
    ("golcito", {"GOL"}),
    ("fiat cronos drive 1.3", {"CRONOS"}),
    # Pegado o separado.
    ("tcross", {"T-CROSS"}),
    ("rav4", {"RAV 4 - 2015"}),
    ("cr v", {"CRV"}),
    # Errores de la propia planilla: el cliente escribe bien.
    ("camry", {"CAMRRY"}),
    ("honda hr-v", {"HVR"}),
    ("jeep compass", {"Compast"}),
    ("cruze", {"CRUCE"}),
    # Números exactos.
    ("peugeot 2008", {"2008"}),
    ("peugeot 2008 allure 2019", {"2008"}),
    ("3008", {"3008"}),
    ("peugeot 208", {"208 GT", "208"}),
    ("208 gt", {"208 GT"}),
    ("fiat 600", {"500x / 600"}),
    ("ka", {"KA"}),
])
def test_encuentra_el_vehiculo(texto, esperado):
    r = buscar(texto, FILAS)
    assert r["estado"] == "candidatas", r
    assert nombres(r) == esperado


@pytest.mark.parametrize("texto", [
    # No es un vehículo, o solo dijo la marca o una nota: que lo repita.
    "asdasd", "no se", "auto rojo", "toyota", "4x4", "doble cabina",
])
def test_si_no_es_un_vehiculo_pide_que_lo_repita(texto):
    assert buscar(texto, FILAS) == {"estado": "confusion", "indices": []}


@pytest.mark.parametrize("texto", [
    # Un vehículo de verdad (con marca o número) que no está en la lista: al taller.
    "fiat 500",          # el 500 no es el 500x
    "mercedes clase c",  # Clase C no es Clase A
    "tiggo 7",           # Tiggo 7 no es Tiggo 3
    "lancia delta",      # marca que no está
    "toyota supra",
    "hb20",
])
def test_si_el_vehiculo_no_esta_es_no_encontrado(texto):
    assert buscar(texto, FILAS) == {"estado": "no_encontrado", "indices": []}


def test_si_la_marca_no_cierra_pide_que_lo_repita():
    # Toyota Raptor: el Raptor es Ford. Nunca cotiza.
    r = buscar("toyota raptor", FILAS)
    assert r["estado"] == "confusion"
    assert nombres(r) == {"RAPTOR"}


def test_la_variante_que_nombro_el_cliente_se_elige_sola():
    # Prueba del 21/11 (R09): antes ofrecía «ECO SPORT o ECO KINECTIC» a quien había dicho kinetic.
    r = buscar("ecosport kinetic", FILAS)
    assert r["estado"] == "candidatas" and nombres(r) == {"ECO KINECTIC"}
    assert nombres(buscar("ecosport", FILAS)) == {"ECO SPORT"}


@pytest.mark.parametrize("texto, incluye", [
    # Dos modelos nombrados.
    ("gol saveiro", {"GOL", "Saveiro DOBLE CABINA"}),
])
def test_ante_la_duda_ofrece_opciones(texto, incluye):
    r = buscar(texto, FILAS)
    assert r["estado"] == "opciones", r
    assert incluye <= nombres(r)


def test_muy_mal_escrito_pide_que_lo_repita():
    filas = [{"modelo": "CELTA", "marca": "chevrolet"}, {"modelo": "CLIO", "marca": "renault"},
             {"modelo": "GOLF", "marca": "volkswagen"}]
    assert buscar("delta", filas)["estado"] == "confusion"  # cambia la primera letra
    assert buscar("clia", filas) == {"estado": "confusion", "indices": [1]}  # una letra en palabra corta
    assert buscar("gol", filas)["estado"] == "confusion"  # gol no es golf


def test_filas_sin_marca_sirven_para_cualquier_marca():
    filas = [{"modelo": "FIAT UNO S R", "marca": None}, {"modelo": "128 S", "marca": None},
             {"modelo": "Taos", "marca": None}]
    assert nombres_de(buscar("fiat 128", filas), filas) == {"128 S"}
    assert nombres_de(buscar("volkswagen taos", filas), filas) == {"Taos"}


def nombres_de(resultado: dict, filas: list[dict]) -> set[str]:
    return {filas[i]["modelo"] for i in resultado["indices"]}


def test_limpieza_de_palabras():
    assert tokens("RAV 4 - 2015") == ["rav", "4", "2015"]
    assert tokens("rav4") == ["rav4"]
    assert tokens("C-3") == tokens("c 3") == tokens("C3") == ["c3"]
    assert tokens("Chery Tiggo 8 10-2025+ (3 Filas)") == ["chery", "tiggo", "8"]
    assert tokens("Hilux 2.8 4 x 4") == ["hilux", "4x4"]
    assert tokens("RAM 1.500") == ["ram", "1500"]
    assert tokens("500x / 600") == ["500x", "600"]
    assert tokens("corolla2018") == ["corolla", "2018"]


def test_parecido():
    assert parecido("camry", "camrry") >= 0.93
    assert parecido("korola", "corolla") >= 0.93
    assert parecido("hrv", "hvr") > 0.8
    assert parecido("esprinter", "sprinter") > 0.9
    assert parecido("208", "2008") == 0
    assert parecido("gol", "golf") == 0
    assert parecido("rav4", "rab4") > 0.9


# -- Dentro del motor: el resto de resolver sigue igual ------------------------

HOJA = {"title": "Fundas a medida", "sheetId": 877828453, "values": [
    ["TOYOTA"],
    ["Marca y Modelo de vehículo", "Juego completo (5 plazas)", ""],
    ["", "EFECTIVO", "TRANF"],
    ["COROLLA RESPALDO T.ENTERO  - 2004", 1000, 1100],
    ["COROLLA RESPALDO T.DIVIDIDOS-  XLI", 2000, 2200],
    ["FORD"],
    ["RAPTOR", 3000, 3300],
]}


def item(modelo: str) -> dict:
    n = normalizar_entrada({"consultas": [{"producto": "fundas", "modelo": modelo}], "modalidad": "caba",
                            "tipo_solicitud": "consulta"})
    assert n["ok"], n
    return cotizar(n["entrada"], [HOJA], None)["items"][0]


def test_motor_cotiza_lo_que_antes_no_encontraba():
    r = item("corola xli")
    assert r["estado"] == "cotizado"
    assert r["modelo"] == "COROLLA RESPALDO T.DIVIDIDOS- XLI"  # la planilla se lee con espacios simples


@pytest.mark.parametrize("modelo", ["Toyota Raptor", "asdasd", "clia"])
def test_motor_si_se_confundio_pide_que_lo_repita(modelo):
    r = item(modelo)
    assert r["estado"] == "no_encontrado"
    assert r["motivo"] == TEXTO_CONFUSION == (
        "Creo que tuviste una confusion, repetime tu modelo de vehiculo asi veo si contamos con las medidas")


def test_motor_si_no_tenemos_el_vehiculo_invita_al_taller():
    r = item("Toyota Supra")
    assert r["estado"] == "no_encontrado"
    assert r["motivo"] == TEXTO_SIN_MEDIDAS == (
        "No contamos con las medidas de tu vehiculo, te invito a pasar por nuestro taller en CABA para "
        "tomarlas y asi poder confeccionar las fundas")


# =============================================================================
# Corrección del 20/11 (campaña de pruebas)
# =============================================================================
# Filas con los nombres de la planilla oficial que dieron problemas en la campaña.

CAMPANA = [
    ("volkswagen", "Saveiro DOBLE CABINA"), ("volkswagen", "Saveiro cross"),
    ("toyota", "HILUX CABINA DOBLE - 2005/2015"), ("toyota", "HILUX 2026"), ("toyota", "HILUX CABINA SIMPLE "),
    ("toyota", "SW4 2010"), ("renault", "DUSTER "), ("renault", "DUSTER 2017+"),
    ("peugeot", "208 GT "), ("peugeot", "208"),
    ("chevrolet", "ONIX GEN 1 "), ("chevrolet", "ONIX GEN 2 (2020+)"), ("ford", "RANGER"),
]
FILAS_CAMPANA = [{"modelo": m, "marca": marca} for marca, m in CAMPANA]


def campana(texto, **kw):
    """El estado y los nombres de las filas que devuelve el buscador, en el orden de la planilla."""
    r = buscar(texto, FILAS_CAMPANA, **kw)
    return r["estado"], [FILAS_CAMPANA[i]["modelo"] for i in r["indices"]]


# --- Punto 3: cabina simple y doble cabina se contradicen --------------------------------------

@pytest.mark.parametrize("texto", ["Saveiro CABINA SIMPLE", "saveiro simple cabina", "saveiro cab simple",
                                   "saveiro simple"])
def test_no_elige_la_cabina_contraria_a_la_que_dijo_el_cliente(texto):
    # La doble cabina contradice lo que dijo y la Cross tampoco es lo que pidió: esa variante
    # no está en la lista (no es que el cliente se haya confundido).
    assert campana(texto) == ("no_encontrado", [])


def test_sin_nombrar_la_cabina_no_elige_sola_una_cabina():
    assert campana("Saveiro") == ("opciones", ["Saveiro DOBLE CABINA", "Saveiro cross"])


@pytest.mark.parametrize("texto, fila", [
    ("Saveiro doble cabina", "Saveiro DOBLE CABINA"),
    ("saveiro cabina doble", "Saveiro DOBLE CABINA"),
    ("Saveiro cross", "Saveiro cross"),
    ("Hilux cabina simple", "HILUX CABINA SIMPLE "),
    ("hilux doble cabina", "HILUX CABINA DOBLE - 2005/2015"),
    # Junto al vehículo alcanza con «simple» o «doble», como antes.
    ("hilux simple", "HILUX CABINA SIMPLE "),
    ("hylux doble", "HILUX CABINA DOBLE - 2005/2015"),
    ("saveiro doble", "Saveiro DOBLE CABINA"),
])
def test_si_el_cliente_nombra_la_variante_es_esa(texto, fila):
    assert campana(texto) == ("candidatas", [fila])


def test_doble_traccion_no_es_doble_cabina():
    # No se da por nombrada la cabina: se ofrecen las tres.
    assert campana("hilux doble traccion") == ("opciones", ["HILUX CABINA DOBLE - 2005/2015", "HILUX 2026",
                                                           "HILUX CABINA SIMPLE "])


def test_si_la_variante_que_falta_era_de_un_modelo_que_nombro_no_se_cotiza_el_otro():
    # «gol saveiro cabina simple»: la Saveiro cabina simple no está en la lista. No se cotiza el Gol.
    filas = FILAS_CAMPANA + [{"modelo": "GOL", "marca": "volkswagen"}]
    assert buscar("gol", filas) == {"estado": "candidatas", "indices": [len(filas) - 1]}
    assert buscar("gol saveiro cabina simple", filas) == {"estado": "no_encontrado", "indices": []}


def test_con_una_fila_general_las_de_cabina_siguen_siendo_candidatas():
    # HILUX 2026 no dice cabina: el resto del motor decide con el año o pregunta.
    assert campana("Hilux") == ("candidatas", ["HILUX CABINA DOBLE - 2005/2015", "HILUX 2026",
                                               "HILUX CABINA SIMPLE "])


def test_una_fila_que_no_dice_cabina_sirve_aunque_el_cliente_la_nombre():
    assert campana("Ranger cabina simple") == ("candidatas", ["RANGER"])


def test_si_el_modelo_no_distingue_cabinas_nombrar_una_no_descarta_sus_filas():
    # «Saveiro cross» deja de servir porque la planilla tiene otra Saveiro con la cabina contraria.
    # Una fila que nombra varios modelos y ninguna cabina sigue sirviendo.
    filas = [{"modelo": "Fiat Argo - Cronos - Pulse (Todos) ", "marca": "fiat"},
             {"modelo": "Saveiro cross", "marca": "volkswagen"}]
    assert buscar("Cronos", filas, detalle="cabina simple") == {"estado": "candidatas", "indices": [0]}
    assert buscar("Cronos cabina doble", filas) == {"estado": "candidatas", "indices": [0]}
    assert buscar("Saveiro cabina simple", filas) == {"estado": "candidatas", "indices": [1]}


def test_la_cabina_tambien_puede_venir_aparte_del_modelo():
    # En alfombra el modelo manda la cabina en la configuración.
    assert campana("Hilux", detalle="cabina simple") == ("candidatas", ["HILUX CABINA SIMPLE "])
    assert campana("Saveiro", detalle="cabina simple") == ("no_encontrado", [])
    assert campana("Saveiro", detalle="2 plazas") == ("opciones", ["Saveiro DOBLE CABINA", "Saveiro cross"])
