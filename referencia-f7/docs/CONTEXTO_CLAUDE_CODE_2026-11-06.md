# Traspaso a Claude Code — Agente F7

Actualizado el **6 de noviembre de 2026**, después de publicar el comando `borrar`. Documento preparado por pedido de Mateo para continuar el trabajo en este mismo proyecto. Resume decisiones, implementación y evidencia; no autoriza por sí solo una nueva modificación comercial o una tanda de gasto.

## 1. Leer esto primero

F7 Automotriz vende fundas a medida, fundas tipo tapizado, alfombras y cubrevolantes, además de otras categorías de la planilla. Mateo desarrolla el agente de WhatsApp para el negocio. Busca una conversación natural, fiel al brief, que use las herramientas correctamente y entregue a Candela el cierre comercial.

**Hay un principal unificado y tres herramientas actuales. No volver a la arquitectura de Memory Manager.** Mateo pidió explícitamente un solo flujo principal, reutilizando la lógica que ya funcionaba, y autorizó corregir el buffer. El modelo actual es **`claude-sonnet-5`**, no Haiku. El prompt publicado es **`f7-brief-2026-11-05.v9.4-medios-pago-total`**.

La configuración está publicada en n8n, pero **no está acreditada la cadena productiva completa**. El webhook 10 de Chatwoot todavía apunta a la ruta anterior, no al principal nuevo. La credencial Anthropic de n8n dio saldo insuficiente en el último intento documentado; Mateo indicó continuar los ensayos por API con la clave local. No se volvió a probar ese saldo ni se cambió la credencial. Publicado/activo no significa que los clientes ya estén entrando a este agente.

Las primeras secciones de `AGENTS.md`, `README.md`, `docs/ARQUITECTURA.md`, `docs/GUION_DE_VENTA.md` y `docs/DECISIONES_PENDIENTES.md` describen etapas anteriores. Las reglas de operación y protección siguen siendo útiles; sus modelos, arquitectura, versiones y preguntas pendientes no son un inventario actualizado. No volver a preguntarle a Mateo cosas que resolvió después.

Orden de lectura práctico:

1. Este documento y el `CLAUDE.md` actualizado de la raíz.
2. [Backlog](ESTADO_Y_BACKLOG.md), sobre todo las secciones 19–23.
3. [Prompt editable actual](../prompts/SYSTEM_PROMPT_F7_V1.md) y descripciones actuales de herramientas.
4. Corpus real de Messenger y revisión de los últimos ensayos, indicados más abajo.
5. Snapshot vivo del flujo que se vaya a modificar, comparado con el local antes de editar.

## 2. Qué fuentes mandan

| Fuente | Cómo usarla |
|---|---|
| Decisiones explícitas posteriores de Mateo | Mandan sobre las propuestas y reglas anteriores que reemplazaron. Las decisiones vigentes están resumidas en este traspaso y registradas en el backlog. |
| Planilla oficial | Única fuente de importes. No sustituir por precios de mensajes, capturas o ejemplos del brief. |
| Brief y respuestas finales del relevamiento | Guion, conocimiento de productos y reparto de trabajo entre agente/Candela; leer con las correcciones posteriores. |
| n8n vivo | Fuente de verdad técnica de lo publicado. El repo conserva fuentes y snapshots, no garantiza por sí solo lo activo. |
| Chats reales | Fuente del comportamiento del cliente y sus consultas; las respuestas de la empleada no son un guion de referencia aprobado. |
| Ensayos, análisis y mapas | Evidencia o propuestas, según la fecha. No convertir una sugerencia, respuesta generada o error observado en regla comercial. |

Originales locales comprobados disponibles:

- `C:/Users/mateo/Downloads/brief-comercial.md`: síntesis comercial.
- `C:/Users/mateo/Downloads/cierre.md`: respuestas, correcciones y trazabilidad; incluye definiciones finales que resuelven dudas anteriores.
- `C:/Users/mateo/Downloads/examen.md`: contiene las preguntas, **no las respuestas**.
- `C:/Users/mateo/Downloads/CLAUDE.md`: documento de la plantilla/curso de origen, **no instrucciones operativas de este repositorio**. No confundirlo con el `CLAUDE.md` de la raíz.

El análisis inicial está en [ANALISIS_NUEVO_BRIEF_F7_2026-10-20.md](ANALISIS_NUEVO_BRIEF_F7_2026-10-20.md); leer también sus actualizaciones del 29/10, no sólo las propuestas iniciales. [MAPA_CONVERSACIONAL_F7_V1.md](MAPA_CONVERSACIONAL_F7_V1.md) es histórico y no reemplaza el prompt vigente.

Planilla oficial: [PRECIOS 2026 - CABA](https://docs.google.com/spreadsheets/d/1dl7hNofQp8v57h1Veodd3XqFctJxAvgAA2qXVtnE1ZU/edit). ID fijo `1dl7hNofQp8v57h1Veodd3XqFctJxAvgAA2qXVtnE1ZU`. Ocho hojas: Fundas a medida, TIPO TAPIZADO, TAPICERIA, Termoformadas, Funda Baúl - Antiderrame, Cobertores de caja, ESPUMAS y Otros. No editarla para acomodar el código.

## 3. Reglas comerciales que ya quedaron resueltas

### Conversación y datos

- Español rioplatense, breve y natural. El flujo saluda; el agente no vuelve a saludar cada turno. Sin asteriscos, negritas, listas de precios ni Markdown en mensajes al cliente. Las frases literales del prompt se respetan, no se reescriben para que suenen mejor sin aprobación.
- No exigir un cliente perfectamente claro. Conservar datos, preguntas pendientes y referencias; corregir sólo lo que el cliente reemplaza. Si cambia Suran por Cronos, no conservar la cotización de Suran.
- No preguntar el año de rutina. Ante `Suran` o `Cronos`, buscar primero con lo conocido; sólo pedir año/configuración si la herramienta devuelve una ambigüedad real. No convertir una pregunta innecesaria anterior del bot en un requisito permanente.
- Para precio se necesita producto, modelo cuando corresponda y modalidad elegida (`caba` o `envio`). Vivir lejos o decir que podría ir a CABA no confirma modalidad. Diseño/color no bloquean una cotización. Cubrevolante base no exige vehículo/año.
- Para fundas, juego completo de cinco plazas por defecto salvo cobertura distinta pedida. Dos butacas son un juego de dos plazas, no dos juegos. No inferir butacas de un vehículo adaptado.
- `Fundas` genérico no elige automáticamente fundas a medida. Si aún no eligió y quiere precio, comparar las dos opciones. Comparar alternativas no autoriza a sumarlas.
- Pedidos explícitos de fotos/videos se atienden ese turno aun sin modalidad, como ejemplos. Mostrar material o encontrar tarifa no confirma medidas, stock ni disponibilidad.

### Cotización y medios de pago

- `buscar_precio` consulta la planilla y envía la cotización. El LLM no calcula, inventa, recupera precios antiguos ni vuelve a enviar el presupuesto.
- Cotización natural en **un solo mensaje**, no ficha/lista tipo «Configuración / Cantidad / Efectivo / Transferencia / Cuotas».
- Sin medio indicado: transferencia, sin preguntar antes cómo quiere pagar. La cotización inicial por transferencia termina exactamente con **«Quisieras aprovechar el valor en transferencia o en 3 cuotas sin interes?»**.
- Si pide efectivo, usar la columna EFECTIVO, sólo en CABA. Si pide cuotas, mismo total que TRANSFERENCIA por decisión explícita de Mateo: **no usar POSNET ni recalcular porcentajes**. Una cotización explícita de efectivo/cuotas no vuelve a preguntar transferencia o cuotas.
- Si cambia de envío a CABA y venía preguntando efectivo, conservar esa intención y recotizar efectivo. Efectivo con envío no produce una tarifa de efectivo; requiere resolver modalidad. No reemplazar silenciosamente por transferencia.
- `tarjeta` sin precisar: crédito o débito. Débito, otro medio o combinación sin regla: revisión de Candela, sin prometer aceptación ni precio.
- Consultar «quiero pagar en efectivo, cuánto sale?» no significa querer pagar ahora. Alias, reserva, pago efectivo de la compra o pedido de persona sí requieren pase.
- «Cuánto todo junto», «total» y similares de artículos acumulados requieren `tipo_solicitud=combo`, con todos los artículos, cantidades y variantes, aunque el cliente todavía no decidió comprar. Comparaciones no se suman y un combo incompleto no tiene total completo.
- No recotizar sólo porque eligió color/diseño o pidió una foto. Sí ante cambio de producto/modelo/cantidad/cobertura/modalidad/medio, o pedido actual de precio/total.
- No mostrar **«El costo del envío y la compatibilidad/medidas quedan a confirmar.»**, ni variantes. Mateo pidió eliminar ese aviso. No afirmar tampoco envío gratis o compatibilidad. Si lo pregunta expresamente, deriva para que Candela lo responda.
- No se eliminó ninguna variante de cubrevolante. CV01 es un video; pedir foto puede devolver material faltante. No confundir eso con eliminar un producto.

### Candela y límites

- El agente informa, muestra contenido, cotiza y asesora en diseño/color. Candela continúa cierre, alias/link, acreditación, datos/fotos, confirmación final, carga del pedido y coordinación. No dar por cobrados, encargados o reservados pedidos desde el bot.
- Candela usa la cuenta **Melanie, usuario 3 de Chatwoot, cuenta 1**. Esto ya lo confirmó Mateo; no volver a buscar una cuenta llamada Candela ni volver a preguntarlo.
- `derivar_humano` pausa con `humano`, abre la conversación, asigna a Melanie y verifica antes de confirmar. El LLM no puede asegurar pase por el simple hecho de haber llamado la herramienta.
- Diseño/color aislados, gracias, emoji o `dale` sin referente no confirman compra. Un pedido de persona o de gestión humana se atiende sin retenerlo por año, diseño o color.
- Con `bot_pausado=true`, estado `derivado` o `control_humano`: silencio y ninguna herramienta adicional, aun si asignación/ACK quedaron parciales o inciertos. No afirmar asignación o entrega sin confirmación. El guard técnico suprime salidas raw indebidas; no quitarlo suponiendo que el prompt ya basta.
- Motos, plazos, garantías, ubicación, horarios, objeciones y señas: leer los bloques literales del prompt. No copiar políticas de un reclamo histórico ni improvisar descuentos, excepciones, garantías o seguimientos por silencio.

## 4. Arquitectura y archivos actuales

Instancias: `https://n8n.teotec.org` y `https://chatwoot.teotec.org`. Las versiones siguientes corresponden al último readback del 06/11; volver a consultar si se va a modificar algo.

| Función / slug | ID n8n | Nodos / estado | Versión activa |
|---|---|---|---|
| `agente-principal-unificado` | `m7jZDzyP17BayLrI` | 121, activo | `2f840d76-0527-4467-b34d-a513a87da601` |
| `herramienta-precios-v1` | `uNguhYLYJ4vEASG0` | 42, activo | `6e4e9300-19bf-4a5a-b1ba-9c0116caac22` |
| `herramienta-multimedia-v1` | `BArOU48SoyGqiDE7` | 62, activo | `c586a875-af1b-40be-a2f5-461be653e0b4` |
| `herramienta-derivacion-v1` | `TWnWokkaRUO3eFsf` | 62, activo | `1a23f8ba-8d53-4be5-8aec-71f5de9eb365` |
| `test-prompt-f7-v1` | `IHsdDfjuW3T6hw1Q` | 14, inactivo | QA histórico; no representa automáticamente la última rama técnica de reinicio |

Los cuatro snapshots actuales están en `workflows/inactivos/` por el registro histórico `tier:off`. **La carpeta no prueba que estén inactivos.** `scripts/workflows.json` registra IDs; `workflows/MANIFEST.json` registra la exportación. No tocar flujos ajenos ni borrar los anteriores como parte de una corrección.

El webhook del principal es `/webhook/f7-principal-unificado-v1`. Su recorrido normal conserva filtros de eventos, texto/audio, transcripción, buffer Redis de 15 segundos desde el último mensaje, consumo ordenado, memoria Postgres, ensamblador por fase, agente, herramientas y envío por Chatwoot. El split conserva precios con puntos, decimales y URLs. Cotizaciones y adjuntos no pasan por ese split: salen de sus herramientas.

| Área | Fuentes a editar/revisar |
|---|---|
| Prompt actual | `prompts/SYSTEM_PROMPT_F7_V1.md`, `src/prompt-f7/ensamblar.mjs` |
| Integración principal | `src/unificado/aplicar-prompt.mjs`, `aplicar-precios.mjs`, `aplicar-derivacion.mjs`, `aplicar-modalidad.mjs`, `aplicar-salida-comercial.mjs` |
| Normalización, buffer, salida | `src/unificado/logica.mjs`, snapshot principal y tests del buffer |
| Guard y memoria comercial | `src/unificado/salida-comercial.mjs`, nodos Controlar salida comercial / Reparar memoria comercial |
| Precios | `src/precios/motor.mjs`, `descripcion.mjs`, `modalidad-contexto.mjs`, `salida-agente.mjs`, `transporte.mjs`, `sql.mjs`, `construir.mjs` |
| Multimedia | `src/multimedia/catalogo.json`, `seleccion.mjs`, `entrega.mjs`, `sql.mjs`, `construir.mjs`; descripciones en `prompts/ENVIAR_MULTIMEDIA_F7.md` y `SOLICITUDES_MULTIMEDIA_F7.md` |
| Derivación | `src/derivacion/motor.mjs`, `descripcion.mjs`, `sql.mjs`, `construir.mjs` |
| Reinicio | `src/reinicio/logica.mjs`, `sql.mjs`, `aplicar-principal.mjs`, `aplicar-herramientas.mjs` |

`src/agent/`, `prompts/PROMPT_UNIFICADO_agente_ventas.md` y los scripts extract/inject de ese agente son legado. **No reconstruir el principal actual desde la base histórica con `preparar-unificado` para hacer un cambio pequeño.** Se perderían capas posteriores. No existe actualmente `scripts/preparar-precios-f7.mjs`; no inventar ese comando.

Los campos de destino (`account_id`, `conversation_id`), `modo` e ID de solicitud los fija el flujo, no `$fromAI`. El modelo sólo aporta `solicitudes` en multimedia, `pedido` en precios y `motivo` en derivación. La solicitud actual usa `cw:1:<conversation_id>:<message_id>:<tipo>-v1`; no cambiar el formato o fabricar otro ID para eludir deduplicación. Los productos admitidos varían entre herramientas: multimedia tiene cuatro; precios incluye también las categorías de las ocho hojas.

## 5. Multimedia disponible y comprobada

Catálogo cerrado de 14 archivos habilitados y 22 rutas al último inventario. Los archivos están organizados en `recursos/f7-media/`; el runtime descarga desde Drive usando IDs, hashes, tamaños y versiones del catálogo. Diez copias comerciales se subieron con autorización a [la carpeta F7](https://drive.google.com/drive/folders/1YM8dcc_Dr6CcHpsoWVTyIXrjLAIqcJu9), conservando permisos. Procedencia/conversiones en `docs/medios-f7/preparacion-multimedia.json` y `catalogo-recuperado.json`.

| Pedido de presentación | Selección |
|---|---|
| Sólo fundas a medida | MP02 |
| Sólo tipo tapizado | TT01 |
| Sólo alfombra | AL01 + N8N01 |
| Sólo cubrevolante | CV01 |
| Fundas y tipo tapizado juntos | MP01 comparativo, una sola vez |
| Los cuatro | MP01 + AL01 + N8N01 + CV01 |

Respetar producto, contenido y formato pedidos. Para todos los productos se enumeran los cuatro, no existe `producto:todos`. Todos los diseños no significa todos los productos. Sin formato compatible se informa faltante; no enviar otro producto ni afirmar éxito. Las referencias «la segunda» requieren saber qué opciones se mostraron y su orden.

**Adjuntos sin pie de foto ni texto**, por decisión explícita de Mateo. La descarga recupera el binario después de Crypto mediante el item de la misma iteración: no retirar `Recuperar binario tras hash`. No reintentar POST de mensajes ante resultado incierto. Aceptado por Chatwoot no equivale a entregado/leído.

Prueba real histórica en conversación **27**, confirmada por Mateo como suya: ejecución 36251 envió cuatro videos y se verificó lectura posterior. Ejecución 36271 verificó CV01 sin caption, `content:null`, entregado. Esto no certifica todos los otros archivos ni el principal completo. Detalle y límites: [HERRAMIENTA_MULTIMEDIA.md](HERRAMIENTA_MULTIMEDIA.md); sus estados iniciales de activación son históricos.

## 6. Últimas modificaciones, en orden

1. **Base unificada:** filtros contra ecos/notas/eventos falsos; buffer agrupado con 15 segundos de silencio; audio; envío Chatwoot y split seguro. Se descartó continuar con un Memory Manager separado.
2. **Multimedia:** selección de uno, varios o todos los productos; subida autorizada, integridad, entrega real y eliminación de pies de foto.
3. **Prompt y herramientas:** brief convertido en bloques por fase, precios oficiales y derivación efectiva a Melanie. Pausa y verificación de control humano también antes de cada fragmento de salida.
4. **Naturalidad:** precio enviado por herramienta en un mensaje humano, transferencia inicial y pregunta literal. Se implementaron controles contra duplicación, memoria comercial y bloqueo de registros internos; persisten recotizaciones y reformulaciones del modelo. El registro interno nunca debe aparecer en el chat.
5. **Sonnet 5:** Mateo pidió repetir exactamente los siete casos. Se congeló el replay del ensayo anterior y se cambió el modelo. La conversación mejoró, pero quedaron fallas; no se declaró aprobación integral. Se conserva `thinking:false` en n8n y disabled en el runner.
6. **Sin avisos de envío/medidas:** se retiró la frase que Mateo rechazó, no una variante de cubrevolante.
7. **Medios de pago y total:** efectivo oficial CABA, cuotas=transferencia, rechazo de métodos sin regla, distinción entre consultar y pagar. El caso05 falló en total; v9.4 corrigió la selección de combo y el retest dio $413.000 efectivo por fundas Cronos+cubrevolante.
8. **Comando `borrar`:** último cambio publicado, explicado debajo. Se mantuvieron prompt v9.4, Sonnet 5, contratos comerciales y credenciales.

Los importes anteriores son evidencias fechadas, **no precios para hardcodear**. El 06/11 se contrastaron Suran 2017–2019 $385.000/$466.092, fundas Cronos $353.000/$427.350, tipo tapizado Cronos $550.000/$665.500 y cubrevolante $60.000/$72.600, efectivo/transferencia. Ver `TARIFAS_VERIFICADAS_MEDIOS_PAGO_2026-11-06.json`; volver a consultar Sheets en una tanda futura.

### Último cambio: borrar y reactivar

Después de los IF, antes de audio/buffer/modelo, detecta el comando completo con variantes de mayúsculas, tildes, espacios y signos. También admite `borrá`, `borrame` y calificadores previstos por el detector; una oración común que contiene borrar no lo activa. No pasa por la espera de 15 segundos ni usa tokens del modelo.

Respuesta exacta: **`Ya borre mi memoria, a partir de ahora comienza una conversación nueva`**.

Mateo confirmó que debe reactivar el bot incluso después de Candela. Quita sólo `humano`, preserva otras etiquetas y no desasigna a Melanie. Verifica que el comando exista como mensaje entrante público reciente de ese contacto en Chatwoot antes de mutar nada.

El reinicio crea una época y key nueva por cuenta/conversación; el historial viejo queda fuera del contexto nuevo, sin borrado físico de auditoría. Vacía el buffer anterior sin eliminar su lock. Los locks/memoria capturados por ejecuciones viejas no se mezclan con los nuevos. Principal y herramientas comprueban vigencia antes de actuar; duplicados no generan dos ACK. Un nuevo mensaje con época nueva puede esperar a que termine el reset, sin añadir Wait a la rama del comando.

Límites: no revoca HTTP ya en vuelo y SQL→POST no es atómico. Un mensaje que capturó la época anterior durante el reset puede descartarse: para nuevas pruebas, esperar el ACK antes de seguir. No afirmar borrado físico de la base ni cancelación retroactiva de mensajes.

Ver [REINICIO_CONVERSACION_F7_2026-11-06.md](REINICIO_CONVERSACION_F7_2026-11-06.md), [PUBLICACION_REINICIO_F7_2026-11-06.json](PUBLICACION_REINICIO_F7_2026-11-06.json) y [SMOKE_REINICIO_F7_2026-11-06.json](SMOKE_REINICIO_F7_2026-11-06.json). Backup principal `backups/2026-11-06_111640/`; herramientas `_111626`, `_111630`, `_111635`.

## 7. Conversaciones REALES: de dónde sacar los próximos casos

La fuente primaria es [RELEVAMIENTO_MESSENGER_F7_2026-11-03.md](RELEVAMIENTO_MESSENGER_F7_2026-11-03.md), con:

- [casos-01-20.json](relevamiento-messenger/casos-01-20.json): M01–M20.
- [casos-21-31.json](relevamiento-messenger/casos-21-31.json): M21–M31.

También leer [RELEVAMIENTO_MENSAJES_CORTOS_F7_2026-11-05.md](RELEVAMIENTO_MENSAJES_CORTOS_F7_2026-11-05.md): seis hilos releídos, R01–R06, luego de que Mateo señaló que el primer piloto tenía clientes demasiado claros. No sumar 31+6 como si fueran 37 conversaciones únicas. R01 separa «Hola», «Vi unas fundas a medida de Suran» y «Quisiera saber cuanto estan»; R03 responde sólo «Hola, Baic EU5 PLUS» y luego «Hola, opcion envio»; R05 insiste «Dame el precio de las dos gracias» en lugar de contestar modalidad. R02 reúne visitas de meses distintos: no concatenarlas como una charla continua.

Son fragmentos seleccionados de 31 conversaciones leídas, con `mensajes_cliente`, `contexto_observado`, `tipo_entrada`, `criterios_propuestos` y `limites`. **No son transcripciones completas ni incluyen respuestas esperadas aprobadas.** Se quitaron identificadores personales. No publicar el corpus fuera del proyecto; evitar recuperar nombres/teléfonos de los backups.

M22 es de enero de 2024 y M31 de enero de 2025. Sus importes, señas y condiciones son históricos. La observación de material en esa lectura no prueba que se reprodujo el video. Tampoco se exportaron timestamps para atribuir intervalos reales al buffer.

Casos particularmente útiles:

| Casos reales | Qué recrear y revisar |
|---|---|
| M03, M07, M08, M14 | Insistencia por precio, respuestas de dos palabras, no seguir la pregunta que hace el bot. |
| M02, M18, M19 | Varios datos/preguntas de golpe: producto, vehículo, envío, precio, pago, demora, uso Uber. |
| M04, M21 | Modalidad condicional, comparar valores, rechazo por presupuesto; no convertirlo en envío/compra decididos. |
| M12, M20, M27 | «La segunda», colores/costuras, recompra y logos; respetar contexto visible sin adivinar. |
| M16, M23, M30 | Corregir producto/vehículo/configuración después de respuestas o precios anteriores. |
| M23 | Fundas+cubrevolante+alfombra trasera; pedir total, excluir baúl, no perder artículos. |
| M05, M11, M13, M28 | Asientos/configuración ambiguos o adaptados. |
| M17, M22, M26, M29, M31 | Cuotas, dificultad técnica, desconfianza, reventa, reclamo sin vendedor confirmado, alias/seña: límites y pase. |

Ejemplos literales cortos, conservar errores de escritura:

- M03: «Hola cuánto sale?» → «Una Duster» → «Cuánto salen?» → «Me decís el precio?».
- M08: «Quisiera saver el precio primero gracias».
- M12: «La segunda» / «Pero toda negra».
- M16: «Yo estoy buscando fundas».
- M23: «No es una Suran, es un Fiat Cronos» / «Me pasarían el precio total por las tres cosas?».
- M28: «Creo que de amarok o una así».
- M30: «Son dos butacs» / «Es cabina simplw».

No pegar esos fragmentos seguidos sin revisar el contexto: pueden provenir de momentos separados. La respuesta de la empleada puede ser precisamente el problema a corregir; el oráculo comercial viene del brief, decisiones y herramienta de precios.

### Cómo hacer un test fiel a la realidad

1. Elegir casos reales por variedad y registrar sus IDs en la fixture (`fuentes`). Definir qué dato conoce el cliente y cuál aún no expresó.
2. Usar mensajes sueltos, breves, faltas de ortografía, insistencias, correcciones y preguntas desviadas. No escribir «quiero producto X, modelo Y, año Z, modalidad y medio...» en cada inicio si la fuente no lo hace.
3. El cliente sólo da los datos que sabe y cuando tiene sentido. No adaptarlo artificialmente para ayudar al bot a pasar. `envio`, `las dos`, `cuanto`, `negro`, `y efectivo` necesitan el contexto anterior.
4. Mantener preguntas pendientes y lo que ya se mostró. No obligar al cliente a contestar la última pregunta del agente. Diferenciar cita real, resumen observado y puente inventado para la simulación.
5. Simular ráfagas con intervalos declarados sintéticos; no decir que son tiempos reales de Messenger. No llamar «audio real» a un texto inventado.
6. Continuar hasta pase real/simulado confirmado, negativa o límite observado. Si deriva antes, registrar turnos no ejecutados; no forzar una conversación después de la pausa para completar una cuota.
7. Revisar cada turno: contexto, precio por fila/método, cantidades/total, media correcta y formato, textos duplicados, afirmaciones sin fuente y momento del pase. Completar técnicamente no es aprobar comercialmente.
8. Mostrarle a Mateo los mensajes **tal como salieron**, en una interfaz de chats legible. Separar texto del bot, cotización enviada por herramienta, adjunto y ACK humano. Conservar raw y salida final entregable; no editar errores para embellecer resultados.

Todavía no hay muestra suficiente de audios reales transcritos, garantía/devolución confirmada de F7, pedido actual pagado reconstruido completo ni colocación específica Bariloche/Angostura/Bolsón. Un caso inventado de esas categorías debe marcarse sintético.

## 8. Ensayos SIMULADOS y sus reportes

Estos chats tuvieron respuestas reales del modelo por API cuando el reporte lo indica, pero los clientes son recreaciones/fixtures. **No son conversaciones reales atendidas en Messenger.** Los envíos de precios/media y pases humanos del runner integral son `MOCK_TRANSPORTE`.

| Serie | Fixture / reporte | Uso |
|---|---|---|
| Diez conversaciones iniciales | `docs/pruebas-f7-diez-conversaciones-api-2026-11-05.json`, `REVISION_DIEZ_CONVERSACIONES_F7_2026-11-05.md` | Histórico; guion/herramientas anteriores. |
| Integral, diez casos | `tests/fixtures/piloto-integral-f7-2026-11-05.json`; `docs/PRUEBA_INTEGRAL_F7_2026-11-05.json` y `_r2`, `_r3`, `_r4` | Pedidos ambiguos, varias categorías, datos corregidos, intervención humana. No mezclar las rondas. |
| Cotización natural, siete casos | `tests/fixtures/cotizacion-natural-f7-2026-11-05.json`; `docs/PRUEBA_COTIZACION_NATURAL_F7_2026-11-05_r2.json` | Histórico Haiku y base del replay exacto. |
| Sonnet 5, mismo test | `tests/fixtures/sonnet-5-replay-r2-f7-2026-11-05.json`; `docs/PRUEBA_SONNET_5_F7_2026-11-05.json` | Replay de 44 turnos previstos: 39 ejecutados/69 generaciones, USD0,971998. Guard histórico congelado sólo en ensayo. |
| Medios de pago, cinco casos | `tests/fixtures/medios-pago-f7-2026-11-06.json`; `docs/PRUEBA_MEDIOS_PAGO_F7_2026-11-06.json` y `_r2.json` | Última evidencia comercial: 32 turnos/55 generaciones originales y 6 turnos/11 generaciones de retest caso05. |

Leer [REVISION_MEDIOS_PAGO_F7_2026-11-06.md](REVISION_MEDIOS_PAGO_F7_2026-11-06.md) y sus métricas. Los casos01–04 mostrados vienen de v9.3 y el05 repetido de v9.4: **no decir que se ejecutaron los cinco sobre v9.4**. Total de esa etapa USD1,0040666, 66 generaciones y reserva incierta cero; topeUSD1,50. Los registros de presupuesto son acumulativos.

Vistas existentes fuera del repo, en `C:/Users/mateo/.codex/visualizations/2026/10/20/01a15b80-2ef5-73f2-84da-8e236ba56ed2/`:

- `f7-medios-pago.html`: últimos cinco casos, con caso05 del retest identificado.
- `f7-sonnet-5.html`: comparación Sonnet/Haiku R2 manteniendo cada fuente.
- `f7-cotizacion-natural.html`, `chats-f7-integral.html`, `f7-chats-claros.html`, `f7-diez-conversaciones.html`: históricos.

Los JSON son la evidencia portátil. Si Claude Code no tiene las herramientas visuales de Codex, puede preparar HTML local; no asumir que dispone de los mismos plugins ni borrar vistas históricas.

## 9. Cómo ejecutar pruebas y modificar sin perder lo ya hecho

Entorno: Windows/PowerShell, Node24, proyecto en Google Drive (`G:/Mi unidad/BACKUP NAZI/Proyectos/Agente f7 completo`). Python no está instalado. Si G: desaparece o un archivo no cambia, revisar montaje/sincronización de Drive; ya ocurrió con el `.env`. No pedir que Mateo pegue claves en el chat.

### Verificación local sin gasto

```powershell
$env:F7_PGLITE_MODULE='C:\Users\mateo\AppData\Local\Temp\f7-multimedia-pglite-20261104\node_modules\@electric-sql\pglite\dist\index.js'
npm.cmd test
node scripts/test-integral-f7-api.mjs --dry-run --stage medios-pago
```

La ruta PGlite existe al traspaso; está en Temp y puede desaparecer. Sin esa dependencia, algunas pruebas SQL se omiten: no reportar cobertura SQL completa si hubo skips. Última suite: **545 pasan, cero fallos/omitidos, cuatro TODO históricos**. Runtime del reinicio usa SQL real local y HTTP/Redis simulados.

El runner principal es `scripts/test-integral-f7-api.mjs`. `--dry-run` no lee claves ni hace red. `--run` consume API y guarda reportes inmutables; usarlo cuando Mateo pida los ensayos, con presupuesto acotado, etapa/casos/modelo/reporte revisados. Nunca ejecutar un comando de gasto sólo por leer este traspaso.

Detalles que evitan pruebas engañosas:

- El stage por defecto `integral` usa **Haiku**, aunque el principal use Sonnet. `cotizacion-natural` también es histórico Haiku. `medios-pago` usa Sonnet5 y el guard actual.
- `sonnet-5` es un replay congelado. Hoy puede rechazar por hashes de fuentes cambiadas después del ensayo; es una protección deliberada, no quitarla. Para un ensayo nuevo del prompt actual se prepara otro caso/etapa, sin falsificar comparabilidad histórica.
- Los límites y reportes se concilian por etapa. No borrar JSON/locks ni subir topes para evadir el consumo histórico. La etapa medios-pago ya gastó USD1,0040666 deUSD1,50; no queda presupuesto para asumir otra tanda completa.
- La selección de casos es `--cases ID,ID`; los IDs exactos están en cada fixture. `--report` sólo admite la familia auditada de esa etapa y no sobrescribe archivos existentes. Revisar `argumentos()` y `ETAPAS` antes de armar el comando.
- La API usa clave local: primero `C:/Users/mateo/OneDrive/Desktop/.env`, luego `.env` del proyecto, variable `ANTHROPIC_API_KEY`. No imprimir valores ni copiarla a la credencial de n8n. No asumir que `.env` y n8n usan la misma cuenta/saldo.
- Fixture de importes: `tests/fixtures/precios-oficiales-2026-11-05.json`, contrastada en parte el06/11. El runner no consulta Sheets vivo en cada turno. Para otra fecha, contrastar tarifas y documentar la fuente/fecha antes de juzgar exactitud.
- `MOCK_TRANSPORTE` no acredita credenciales, Redis, memoria Postgres remota, entrega WhatsApp ni asignación humana real. El runner tampoco ensaya la nueva rama `borrar`: tiene pruebas específicas.

### Cambios en n8n, cuando Mateo los solicite

Trabajar sobre los cuatro slugs actuales explícitamente: `npm run export` sin argumentos sigue el registro histórico y no basta.

```powershell
node scripts/n8n-export.mjs agente-principal-unificado herramienta-precios-v1 herramienta-multimedia-v1 herramienta-derivacion-v1
node scripts/n8n-diff.mjs agente-principal-unificado herramienta-precios-v1 herramienta-multimedia-v1 herramienta-derivacion-v1
```

Si hay cambios locales, inspeccionar y preservarlos antes de exportar; no pisar trabajo ajeno ni usar `--force` para evitar la revisión. El proyecto quedó sin commits/push y con muchos archivos untracked: no limpiar ni crear commits salvo pedido.

Para preparar prompt localmente: `node scripts/preparar-prompt-f7.mjs --permitir-publicado`. Usa la fuente actual y conserva al final la capa de reinicio si estaba instalada. No publica por sí solo. Si se reconstruyen herramientas desde sus constructores, aplicar después **`node scripts/preparar-reinicio-f7.mjs`** antes de importarlas: el constructor base no conserva automáticamente esa capa. Validar snapshot completo, no sólo fuente individual.

Protocolo: export/diff del alcance → editar fuente y ensamblar → pruebas pertinentes → validación n8n → dry-run de import → import de un workflow por vez con backup → readback de `activeVersion.nodes`/conexiones/credenciales → runtime apropiado → export/diff final y backlog. Ejemplo de dry-run: `node scripts/n8n-import.mjs agente-principal-unificado`; `--yes` aplica y puede publicar inmediatamente porque está activo. No confundir PUT con un borrador inocuo.

En esta instancia el PUT actualiza versión activa. No llamar activar/desactivar adicionalmente. El servidor agregó `webhookId` a un Wait nuevo: se investigó la diferencia y se conservó en el constructor; no se ignoró una divergencia completa del grafo. Rollback con `scripts/n8n-restore.mjs` sobre backup exacto si realmente falla.

Operación que hay que conservar: SQL parametrizado por credencial `Postgres account`; PUT sólo `name,nodes,connections,settings`, UTF-8, sin `binaryMode` ni `pinData`; no `Invoke-RestMethod` de PowerShell5.1. Redis `eval`/`expire` standalone habían sido no-ops silenciosos en esta instancia: no usarlos sin demostrar el efecto real. No reintentar POST de mensajes a ciegas ni cambiar el pairing del binario dentro de loops.

El test MCP remoto prepare/pinned no estuvo disponible por falta de configuración de acceso MCP de instancia. No exigir nuevas claves si la tarea puede verificarse localmente y con consultas seguras. No confundir herramientas disponibles en Codex con configuración asegurada de Claude Code; leer su configuración sin exponer secretos. `.claude/skills` no estaba presente al traspaso; las skills n8n usadas desde Codex están bajo `C:/Users/mateo/.codex/skills/` y se pueden leer si resultan pertinentes.

### Qué se verificó realmente del reinicio

Cinco ejecuciones n8n 36357–36361 comprobaron filtros, rechazo de un comando no persistido mediante GET real y creación/consulta del esquema de sesión con Postgres real. Cero POST, cero tokens del modelo y cero reinicios de chats reales. El ACK y Redis de la rama completa sólo se probaron localmente con transporte simulado. Readback publicado y export/diff limpios; 21 pruebas dirigidas posteriores al readback también pasaron.

`scripts/smoke-reinicio-f7.mjs` repite esas cinco verificaciones acotadas; no es un smoke de envío. `scripts/verificar-publicacion-reinicio-f7.mjs` compara las versiones publicadas de esa fecha y registra routing sin exponer URL/secretos; sus referencias históricas pueden dejar de ser las esperadas después de otra modificación.

## 10. Pendientes reales, sin reabrir lo resuelto

1. **Entrada y runtime completo:** conectar Chatwoot al principal con Mateo, resolver saldo/credencial Anthropic con él, ensayar texto/audio, buffer/memoria, herramientas y pase desde su WhatsApp. Conversación de pruebas reciente confirmada:27; no usar24 sólo porque figura en guías antiguas. No enviar pruebas a clientes.
2. **`borrar` real:** comprobar ACK literal, reactivación después de Candela y nueva conversación sin contexto, incluyendo pendientes. No está acreditado aún por WhatsApp.
3. **Comercial tras v9.4:** no hay una nueva tanda completa de cinco casos sobre v9.4. Se verificó específicamente el retest de combo. Planificar variedad sin presentar el único retest como aprobación integral.
4. **Descuento insistente:** caso02/T5 del último ensayo negó categóricamente un descuento sin revisión humana. No inventó un descuento, pero tampoco había base para denegar la excepción. Revisar el pase correcto sin inventar otra política comercial.
5. **Foto de cubrevolante:** caso02/T4 devolvió sin material compatible; existe CV01 video. Considerar ofrecer esa alternativa cuando corresponda, sin sustituir silenciosamente el formato ni afirmar que se envió una foto.
6. **Fidelidad literal y fluidez:** todavía hay reformulaciones, repreguntas, recotizaciones y confirmaciones innecesarias. Preservar evidencia raw y verificar salida visible; el guard corrigió textos indebidos después de algunos pases, no volvió perfecto al modelo.
7. **Medidas/stock/compatibilidad:** no hay fuente operativa verificada por vehículo/configuración. Precios/video no la reemplazan. No resolverlo pidiendo más datos sin fuente ni reintroducir el aviso eliminado.
8. **Integración multimedia/derivación:** cuatro videos tuvieron prueba real histórica; no todos los archivos y combinaciones. Asignación humana de este hijo y cadena completa requieren evidencia real, no sólo mocks. Evaluar fallos parciales e incertidumbre.
9. **Operación antes de abrir tráfico:** monitoreo y conciliación de inciertos, identidad del inbox y separación de otros bots/cadenas. No tocar `AGENTE PRUEBA 2` u otros proyectos al corregir F7. Revisar pendientes de seguridad históricos con Mateo, sin rotar ni borrar por cuenta propia.

El error de total de combo está corregido en el alcance probado; no tratarlo como si siguiera sin tocar. También quedaron resueltos: cuál es la planilla oficial, quién es Candela, cuotas=transferencia, efectivo oficial, no exigir año de rutina, cotización natural, no captions, no avisos de envío/medidas y reinicio que reactiva. No volver a pedir esas definiciones.

## 11. Forma de trabajar con Mateo

Mateo quiere que se avance dentro de lo que ya autorizó; le frustran las preguntas repetidas y los frenos innecesarios. Si pide explicar antes de modificar, explicar primero y esperar esa aprobación concreta. No cambiar el guion, agregar requisitos o extender alcance para resolver una dificultad técnica.

No enviar mensajes, tocar conversaciones reales, cambiar el webhook, activar/desactivar, borrar workflows o editar credentials sin la autorización que corresponda. Las reglas del proyecto reservan esas operaciones a Mateo salvo instrucción explícita posterior. No pedir contraseñas/API keys por chat. Tokens sólo en `.env`, `secrets/` o credentials; nunca en docs, JSON públicos ni commits. El archivo histórico de workflows puede contener secretos: no volcarlo ni compartirlo entero.

Usar `rg`, Node y lecturas por nodo; no abrir JSON enormes completos. No hacer commits/push por iniciativa propia. No ejecutar testeos pagos, imports ni envíos sólo por leer este documento. Ante un próximo pedido, consultar primero el estado vigente, aprovechar estas decisiones y terminar la tarea autorizada, indicando qué fue probado localmente, por API real y en la cadena remota.

Este traspaso sólo actualiza documentación de continuidad; no introduce cambios nuevos en n8n, prompt, precios, multimedia, credenciales ni routing.
