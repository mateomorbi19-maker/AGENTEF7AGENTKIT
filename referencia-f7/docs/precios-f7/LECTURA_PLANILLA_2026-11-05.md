# Lectura de la planilla oficial — 2026-11-05

Fuente: [PRECIOS 2026 - CABA (EFECTIVO Y TRANSFERENCIA)](https://docs.google.com/spreadsheets/d/1dl7hNofQp8v57h1Veodd3XqFctJxAvgAA2qXVtnE1ZU/edit).
Consulta: 2026-11-05T15:11:45.530Z. Lectura nativa mediante conector, sin modificar celdas ni permisos.

Fixture: `tests/fixtures/precios-oficiales-2026-11-05.json`. Conserva valores efectivos `UNFORMATTED_VALUE`, filas vacías intermedias, celdas nulas y textos originales. Es una captura para pruebas; la herramienta debe consultar la fuente vigente al cotizar. No incluye secretos.

## Cobertura y estructura

| Hoja exacta | gid | Rango leído | Última fila devuelta | Filas con algún número |
|---|---:|---|---:|---:|
| Fundas a medida | 877828453 | A1:X1110 | 414 | 280 |
| TIPO TAPIZADO | 613213257 | A1:Z1091 | 162 | 46 |
| TAPICERIA | 972378170 | A1:Z1030 | 308 | 190 |
| Termoformadas | 0 | A1:X1056 | 245 | 146 |
| Funda Baúl - Antiderrame | 941782890 | A1:AA1000 | 27 | 25 |
| Cobertores de caja [espacio final] | 2002506112 | A1:Y997 | 7 | 5 |
| ESPUMAS | 1953604758 | A1:AB1001 | 107 | 104 |
| Otros | 59879218 | A1:U999 | 18 | 12 |

Los rangos se calcularon con metadata real. El API omite filas vacías finales; no se eliminaron filas vacías intermedias. “Filas con algún número” no equivale a registros cotizables: algunas carecen de modelo.

Para la hoja con espacio final fue necesario usar `sheet_name:null` y rango completo `'Cobertores de caja '!A1:Y997`; pasar el título como argumento separado pierde ese espacio en el conector.

### Fundas a medida

Modelo en A. Encabezados de configuración por sección de marca; pares de precios B/C, D/E, F/G, H/I y en un caso J/K. B/C suele ser juego completo de 5 plazas, D/E dos asientos, H/I siete asientos. F/G cambia entre butaca delantera, butaca y butacón y tres cuerpos. No reducir estas etiquetas a una sola categoría sin preservar el título original.

Encabezados de configuración en filas 2, 32, 62, 95, 130, 169, 189, 201, 222, 231, 241, 261, 275, 293, 302, 312, 324, 333, 343, 355, 366, 375, 387, 397, 407. La fila siguiente contiene modalidad de pago, con algunas celdas faltantes.

Fila 261 agrega J/K = 12 asientos; H1 en fila 263 tiene valores en ese par. Fila 243 tiene texto “efectivo / tranferencia” en F/G dentro de una fila de Corolla: no es un importe. Hay notas comerciales fuera de A:K, por ejemplo extra de logo en L/M y notas de butacas en S. No son modelos ni precios de la fila.

### TIPO TAPIZADO

Modelo en A y pares B/C, D/E, F/G, H/I, ocasionalmente J/K. Encabezados en filas 3, 16, 32, 45, 63, 78, 92, 108, 121, 132, 147, 160; modalidad de pago en la fila siguiente.

Atención: fila 160 cambia las configuraciones a F/G = 6 asientos, H/I = 9 asientos y J/K = 12 asientos. H1 fila 162 tiene respectivamente 950000/1149500, 1300000/1573000 y 1650000/1996500. No se puede etiquetar esos pares como tres cuerpos y siete plazas.

### TAPICERIA

Modelo en A, pares B/C cinco plazas, D/E dos plazas, F/G una butaca y butacón, H/I siete plazas. Encabezados repetidos por marca. Es un producto distinto de “tipo tapizado”; no mezclarlos por coincidencia de palabras.

### Termoformadas, baúl y cobertores

Marca en A, modelo en B, efectivo D y transferencia E. Termoformadas tiene lista de precios en filas 2:149. Desde fila 154 empieza “LISTA DE ALFOMBRAS TERMOFOMADAS ( ALTERNATIVAS )”; filas 158:244 son códigos y modelos sin precios. Fila 245 dice “SIN STOCK” y no identifica un producto: no es una condición aplicable a todo el catálogo.

Baúl: modelos en filas 3:27. Cobertores: filas 3:7, pero la última carece de modelo. No confundir alfombra, funda de baúl y cobertor de caja.

### ESPUMAS y Otros

ESPUMAS: modelo A; B/C respaldo; D/E asiento. Encabezados en filas 2:3. Muchos modelos llevan sufijos S/R no explicados en la hoja; conservarlos hasta tener una equivalencia autorizada.

Otros: encabezado fila 2; B efectivo, C transferencia, D POSNET o cuotas. Registros filas 4:15. Cubre volante en fila 4: 60000 / 72600 / 79134. “PRÓXIMOS ARTÍCULOS” fila 18 es una sección, no un producto.

## Datos que requieren tratamiento conservador

- Sin identidad de modelo y con importes: Tipo tapizado filas 38 y 112; Tapicería filas 147 y 190; Cobertores fila 7. Excluir de resultados cotizables, sin heredar modelo de la fila anterior.
- Filas sin importes incluyen Tipo tapizado PUNTO 2014 fila 9, RENAULT KANGO fila 114; Fundas Fortuner fila 258; Termoformadas HONDA CRV 7SET 2017+ fila 69 y TOYOTA SW4 05-15 fila 105. “Existe en catálogo” no significa “tiene precio”.
- Precios parciales: Tipo tapizado Accelo fila 134 tiene F=590000 y G vacío; no completar transferencia por porcentaje. Otros LIMPIEZA INTERIOR fila 14 carece de D, MANOPLA fila 15 tiene solo efectivo.
- Duplicado conflictivo: Fundas “Elantra” fila 205 (sección NISSAN) 353000/427350 frente a fila 266 (HYUNDAY) 385000/466092, en B/C; D/E también difieren. No elegir la primera fila.
- Duplicados con mismos importes: Tapicería A3 filas 153/156 y Elantra 169/231; Termoformadas Vento MK7 2018+ filas 132/138. Conservar trazabilidad aunque se deduplique la opción presentada.
- Marcas contradictorias en fuente: Termoformadas BMW X3/X5 filas 12/13 figura bajo MERCEDEZ BENZ; baúl Golf 7, T-Cross, Taos y Tiguan figuran bajo TOYOTA (filas 22:26). No usar la marca errónea para corregir el modelo solicitado ni presentarla como verificada.
- Suran no tiene un único precio universal: Fundas fila 137 “SURAN 2017-2019” B/C 385000/466092; fila 138 “SURAN 2009” 353000/427350. El año solo se necesita cuando esas opciones afectan la resolución; un año no cubierto no puede asignarse automáticamente.
- Variantes reales: Ranger en Termoformadas distingue generación, cabina simple, Over mat y Raptor (filas 32:36); no juntar resultados solo por contener “Ranger”.
- Hay ortografía no estándar y espacios: STEPWEEY, CAPTURE, GOL COUNTRI, CAMRRY, HYUNDAY, MERCEDEZ, IVECCO, Argos. Normalizar mayúsculas, acentos y espacios es seguro; convertir esos nombres en otro modelo requiere alias explícito y evidencia, no distancia difusa.
- Blancos, null, guiones y textos no son cero. Las celdas numéricas son valores efectivos; no hay errores de fórmula visibles en la captura.
- Los porcentajes de encabezado no sustituyen los valores. Ejemplos: Fundas B4=353000 y C4=427350, no exactamente B4×1,21; Otros ESPUMA DE ASIENTOS C10=169400; RELLENO D12=118701. Se debe devolver lo escrito y no recalcular para “corregirlo”.
- “POSNET o CUOTAS 21% + 9%” está explícito en Otros, no autoriza extrapolar esa modalidad a las demás hojas. La política de envío/tarjeta se confirma por separado.

## Verificación acotada de fórmulas

Se leyeron CellData (`userEnteredValue,effectiveValue`) en Fundas B4:I7, Tipo B5:I9, Termoformadas D30:E36, Otros B4:D15 y Espumas B4:E7. En esas celdas, los importes son constantes numéricas, no fórmulas, y coinciden con el fixture. La revisión no asegura que ninguna otra celda del libro tenga fórmulas; el fixture usa el valor efectivo calculado si las hubiera.

## Límite de esta lectura

Esta captura no autoriza cambiar precios, interpretar cantidades de cuotas, aplicar descuentos, confirmar stock ni convertir la lista CABA en tarifas de otra sede. Tampoco transforma productos extra de la planilla en productos habilitados en el guion. Es evidencia para implementar búsqueda precisa y detectar las consultas que necesitan aclaración.

