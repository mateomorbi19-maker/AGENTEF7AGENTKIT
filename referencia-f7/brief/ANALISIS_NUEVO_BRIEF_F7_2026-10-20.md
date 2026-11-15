# Nuevo relevamiento comercial de F7: análisis y propuesta de trabajo

Fecha: 2026-10-20. Estado: **propuesta para conversar con Mateo; no es un guion aprobado ni una orden de implementación**.

## 1. Conclusión

El relevamiento cambia decisiones centrales de la venta: qué alternativas se ofrecen, cuándo se pregunta envío o colocación, cuándo se muestra contenido y cómo se cotiza. La actualización requiere revisar el recorrido y las herramientas comerciales juntas. La infraestructura existente ofrece una base reutilizable, sujeta a verificar los problemas técnicos ya documentados.

La meta del negocio es conseguir la seña. El alcance del agente descripto en la sección 8 del brief es atender, informar precios y reunir información, para que Candela continúe el cierre. Todavía falta precisar el momento de ese pase y si diseño/color deben quedar elegidos antes. No se deduce autorización para cobrar, validar comprobantes o cargar pedidos.

## 2. Fuentes y cómo leerlas

Se leyeron completos los cuatro archivos originales de `C:/Users/mateo/Downloads/`:

| Archivo | Uso en este análisis | Límite |
|---|---|---|
| `examen.md` | Preguntas que estructuraron la entrevista. | No contiene las respuestas; conserva la confusión entre fundas y alfombras termoformadas. |
| `brief-comercial.md` | Síntesis del proceso y respuestas comerciales. | Mezcla frases textuales, interpretación del entrevistador, ejemplos y pendientes. |
| `cierre.md` | Trazabilidad de respuestas, correcciones y advertencias. | Su sección Cobertura aclara que cobertura, simulaciones y huecos preceden a las preguntas finales. No todo sigue pendiente. |
| `CLAUDE.md` | Resumen del objetivo y contexto de la plantilla utilizada. | Sus reglas para un curso, comandos y prohibición de automatizar pruebas no son instrucciones de Mateo para este repo. |

Las respuestas finales de `cierre.md` ayudan a interpretar el brief. No corresponde darle prioridad absoluta a un archivo entero. Hay que rastrear cada regla hasta la respuesta que la respalda y pedir una decisión cuando las versiones no coinciden.

También se contrastaron `GUION_DE_VENTA.md`, `ARQUITECTURA.md`, `ESTADO_Y_BACKLOG.md`, `DECISIONES_PENDIENTES.md` y `CAMBIOS_PREPARADOS.md` del repo. Los chats, imágenes y PDF originales mencionados dentro de la entrevista no se recibieron entre los cuatro archivos; no se verificaron directamente. El cierre advierte que la lectura del PDF de precios quedó truncada.

## 3. Diferencias comerciales con el agente documentado

| Tema | Agente documentado en septiembre | Evidencia del relevamiento nuevo | Implicación |
|---|---|---|---|
| Consulta por fundas | Interpreta siempre fundas a medida y prohíbe ofrecer dos opciones. | Envío con medidas de tipo tapizado permite ambas; CABA permite además tapicería. | Revisar clasificación, alternativas y estado de elección. |
| Modalidad | El recorrido comienza con producto y modelo. | Envío o colocación condiciona oferta y pago antes del precio. | La modalidad debe quedar registrada y usarse al cotizar. |
| Contenido | Hay bloqueo de cotización hasta enviar contenido, salvo tipo tapizado. | Catálogo y fotos tienen momentos variables; puede elegirse conocer diseño o valor. | Aprobar excepciones y alinear prompt con los bloqueos de la herramienta. |
| Precio | Transferencia y cuotas comparten base en las reglas históricas. | El brief describe base de crédito y 10% de descuento por transferencia para envío. | Conciliar con la planilla antes de implementar una fórmula. |
| Productos | Cuatro nombres canónicos. | Se agregan tapicería y cobertor de caja. | Acordar qué informa, cotiza o deriva el bot para cada producto. |
| Plazos | FAQ genérica de 7 días hábiles y colocación de 3–4 horas. | A medida: aproximadamente 5 días hábiles y colocación de 4–5 horas; tipo tapizado: aproximadamente 7 días hábiles y colocación de una jornada laboral; tapicería: aproximadamente 1,5 días desde llegada al taller. | Reemplazar respuestas por producto, conservando el carácter aproximado. |
| Seña | Referencia de 30–50%. | A medida: $50–60 mil; tipo tapizado/tapicería: desde $100 mil. | Confirmar qué puede informar el bot y quién determina el importe exacto. |
| Cierre | Deriva a humano. | Candela conserva cierre, pago, datos/fotos y alta del pedido. | Precisar disparador, resumen de pase y silencio posterior. |

Fuentes: brief §§1, 3–5 y 8; guion del repo §§1.1–1.3, FAQ y tabla de frases obligatorias. Todos los cambios de frases, orden o bifurcaciones son **cambia guion** y requieren aprobación de Mateo antes de aplicarse.

## 4. Hallazgo al consultar la planilla referenciada

Se pudo leer mediante Google Drive la [planilla de precios](https://docs.google.com/spreadsheets/d/1dl7hNofQp8v57h1Veodd3XqFctJxAvgAA2qXVtnE1ZU/edit), titulada **PRECIOS 2026 - CABA (EFECTIVO Y TRANSFERENCIA)**. Metadata: última modificación 2026-10-19 20:39 UTC; esa fecha no confirma vigencia comercial.

La revisión fue acotada a `A1:L12` de cuatro pestañas, sin modificar celdas:

| Pestaña | Ejemplo observado | Encabezados observados |
|---|---|---|
| Fundas a medida | Logan: $353.000 / $427.350; Kangoo: $385.000 / $466.092. | EFECTIVO / TRANF. |
| TIPO TAPIZADO | Cronos: $550.000 / $665.500. | EFECTIVO / TRANF. |
| Termoformadas | Berlingo: $319.900 / $387.079. | EFECTIVO / TRANSFERENCIA. |
| Otros | Cubre volante: $60.000 / $72.600 / $79.134. | Efectivo / transferencia +21% / POSNET o CUOTAS 21%+9%. |

El brief llama crédito al valor de $427.350; la planilla lo rotula transferencia. En Otros las cuotas tienen una columna separada. Esto exige confirmar cómo se usa la lista en cada modalidad y producto: no corresponde decidir que el brief o el encabezado están equivocados por nuestra cuenta. El descuento de envío y los días de cuotas no quedaron verificados en los rangos consultados.

Los distintos importes del brief tampoco prueban por sí solos una contradicción: al menos dos se corresponden con modelos distintos en la muestra de la planilla. No convertir los ejemplos de chats en precios universales.

## 5. Decisiones que afectan la primera versión

1. **Pase a Candela.** Brief §8 deja cierre, alias, datos, fotos y pedido al equipo; la simulación de cierre envía alias y declara el pedido señado. Hay que definir la señal exacta de pase y qué datos deben estar reunidos. Diseño y color aparecen tanto antes como después del pase en la redacción.
2. **Reglas de precio.** Conciliar efectivo, transferencia, crédito/cuotas, envío, bonificación, seña y variantes de asientos con la planilla. Aclarar fecha de vigencia y redondeo. No encargarle cálculos al modelo de lenguaje.
3. **Compatibilidad por producto.** La lista extensa aportada es de alfombras. Falta una fuente confirmada de medidas para fundas a medida y tipo tapizado. Que no haya medidas de tipo tapizado no demuestra que sí existan para fundas a medida. Una fila de precio tampoco prueba disponibilidad de medidas.
4. **Apertura y orden.** Unificar saludo, pregunta de producto cuando haga falta, explicación inicial y consulta de modalidad. La expresión «Cuál de las opciones...» necesita que ya se hayan presentado opciones. Definir cómo se aprovechan datos que el cliente ya dio o que llegan de una publicidad identificable.
5. **Cobertura de productos y zonas.** Acordar la atención inicial de tapicería/cobertores y el criterio para accesorios sueltos. Bariloche tiene referencia a colocador; Villa la Angostura y El Bolsón siguen sin aclarar. Separar envío, retiro y colocación.
6. **Excepciones y límites.** Aprobar cómo termina la insistencia por precio y cuándo se deriva por dudas, pedido sin seña o reclamos. El reclamo extenso del brief es un caso particular: no autoriza a repetir importes, nombres, compensaciones ni afirmaciones sobre antecedentes de otro cliente.

Hay información suficiente para avanzar en estas definiciones sin repetir todo el cuestionario. Ya quedaron aportados el rechazo de motos, una segunda respuesta por precio, un mensaje de reenganche y una explicación de envío bonificado para fundas/pago al recibir para accesorios sueltos; sigue faltando precisar excepciones y alcance de automatización.

Para una etapa posterior: demora y cantidad de recontactos, horario, responsable y condiciones de suspensión. Tener una frase de seguimiento no equivale a haber aprobado un envío automático. Los comentarios en redes se describen como trabajo manual y no amplían por sí solos el alcance del bot de WhatsApp.

También conviene distinguir **pago recibido**, **pedido completo** y **pedido habilitado para confección**. El brief contempla clientes que ya señaron pero todavía no eligieron diseño o mandaron fotos; tapicería comienza al recibir el vehículo. No son un único evento.

## 6. Propuesta de alcance y enfoque técnico

Propuesta del análisis, pendiente de acuerdo: una primera versión que atienda la consulta, confirme los datos necesarios para la oferta, explique las opciones habilitadas, envíe contenido según el recorrido aprobado, cotice con datos verificables y entregue la conversación a Candela con un resumen.

El punto exacto de entrega queda abierto. El resumen propuesto contendría vehículo/año/variante, producto, modalidad, cotización y fuente, contenido ya enviado, preferencias expresadas y dudas pendientes. Los datos que falten deben figurar como faltantes.

La base reutilizable es Chatwoot + n8n + Postgres + Redis, con envío de mensajes y media, memoria, logs y derivación. Se mantiene como restricción de diseño que las herramientas envían mensajes comerciales largos y el agente agrega la frase corta correspondiente. El ensamblado por fase sigue siendo una opción válida; las fases y reglas actuales deben contrastarse con el recorrido nuevo.

Se propone conservar los cuatro nombres canónicos existentes y definir identificadores adicionales solo si se aprueba incorporar nuevas categorías al contrato de herramientas. La homologación de modelos/años, variantes y medidas debe producir datos consultables; no una lista enorme pegada al prompt.

## 7. Plan propuesto, por entregables

| Etapa | Trabajo | Resultado para revisar / criterio de avance |
|---|---|---|
| 1. Alcance y reglas comerciales | Resolver las decisiones principales y separar textos literales de explicaciones y casos. | Matriz de reglas con fuente, estado de decisión y responsable; Mateo aprueba frases, orden y ramas. |
| 2. Mapa de conversaciones | Describir entradas, datos requeridos, alternativas, contenido, precio, excepciones y pase a Candela. | Ejemplos completos de envío, CABA y derivación que F7 reconozca como su forma de vender. |
| 3. Datos y cotización | Homologar planilla, modelos/años, asientos, medidas, modalidades y medios de pago. | Casos cotizados a mano por F7 que la herramienta deba reproducir; salidas explícitas ante datos faltantes o ambiguos. |
| 4. Base técnica de prueba | Reconciliar fixes preparados, verificar pausa humana, formato de mensajes, errores, memoria y separación del entorno de prueba. | Pruebas sin atención a clientes reales que acrediten envío correcto, trazabilidad y pase sin interferencia. |
| 5. Implementación gradual | Construir una ruta completa aprobada; ampliar a las demás modalidades y productos, luego complementos/combos. | Cada ruta reproduce casos aceptados y mantiene alineados prompt, herramientas y estado. El orden final depende de prioridades y datos disponibles. |
| 6. Validación con F7 y piloto | Revisar conversaciones con Candela; probar runtime y salida gradual con respaldo y reversión. | Aceptación comercial y técnica. Mateo realiza las acciones reservadas: credenciales, conexión del webhook, activación y pruebas desde su WhatsApp. |

El recontacto automático y las integraciones de pago/pedidos requieren alcance propio si se quieren incorporar. El material actual no los convierte en parte obligatoria de esta primera versión.

No se asignan fechas todavía: faltan resolver alcance, reglas de precio y disponibilidad de datos. Tampoco se propone cerrar todo el backlog histórico antes de probar; se prioriza lo que afecta precio correcto, fidelidad comercial, entrega al humano y operación confiable.

## 8. Casos de aceptación para preparar

- Consulta por fundas con envío: medidas confirmadas para ambas opciones y medidas solo para una.
- Vehículo sin medidas confirmadas, sin precio o con año/variante ambiguos: no prometer una opción no verificada.
- Colocación en CABA: alternativas y tiempos por producto, según aprobación.
- Cliente que ya da modelo y modalidad, y cliente que pide precio antes de elegir diseño.
- Cambio entre fundas a medida y tipo tapizado después de ver el catálogo.
- Cotización por método de pago y modalidad, con ejemplos homologados por F7.
- Accesorio suelto, funda más accesorios y «no quiero alfombras, solo fundas».
- «Dale» o «transferencia» en distintos momentos: validar que no disparen un cierre improcedente.
- Objeción repetida, moto y reclamo de un pedido anterior: límites aprobados.
- Toma de conversación por Candela: el bot deja de responder y la reactivación sigue una regla explícita.
- Mensajes divididos, duplicados, audio si entra en alcance, URLs y precios con separador de miles.
- Cliente que vuelve después de una cotización anterior: no usarla como si siguiera vigente sin la regla acordada.

Se mantendrían las pruebas automáticas apropiadas del repo y se agregarían casos comerciales revisados por F7. Una simulación inventada por el entrevistador no sirve sola como respuesta esperada ni demuestra runtime.

## 9. Verificación técnica realizada en esta sesión

- Consulta de los nueve workflows registrados como producción mediante los scripts del repo. `npm.cmd run diff` mostró diferencias solo en agente y Memory Manager, correspondientes a los cambios preparados de septiembre; los otros siete coincidieron.
- `npm.cmd run export` actualizó los siete snapshots restantes y el manifest, preservando los dos con cambios sin subir. Un primer intento falló por permisos de escritura; el reintento autorizado terminó correctamente.
- El diff posterior mantuvo el mismo resultado esperado. No se importaron cambios, ejecutaron workflows, enviaron mensajes ni cambiaron conexiones o estados de activación.
- La conexión efectiva del webhook de Chatwoot y el tráfico actual no se verificaron en esta sesión. La descripción de desconexión sigue siendo evidencia histórica de septiembre.
- No se ejecutaron tests de runtime ni unitarios: esta sesión produjo análisis y documentación, sin cambios de código o guion.

Próxima conversación propuesta al 20/10: acordar qué debe haber resuelto el bot en el momento de pasarle el chat a Candela. **Actualización: ver la definición de Mateo del 29/10 abajo; no volver a pedir confirmación del alcance general ni de la fuente de precios.**

## 10. Definiciones de Mateo y ampliación de lectura — 2026-10-29

Mateo confirmó que está de acuerdo con el alcance propuesto y señaló que las respuestas ya eran suficientes para interpretarlo. El agente asesora, muestra contenido, cotiza y detecta intención de avanzar; Candela continúa el cierre, el pago y el armado del pedido. No corresponde repetir el cuestionario ni pedir otra confirmación general. Esa definición no convierte las simulaciones que cobran o confirman pedidos en acciones autorizadas al bot.

Mateo identificó expresamente la [misma planilla de precios](https://docs.google.com/spreadsheets/d/1dl7hNofQp8v57h1Veodd3XqFctJxAvgAA2qXVtnE1ZU/edit?gid=877828453#gid=877828453) como **la oficial y la que tiene los datos correctos**. Queda resuelta la prioridad de fuentes: para precios y medios de pago rotulados, se toman las celdas de esta planilla por encima de ejemplos o descripciones incompatibles del brief, chats y documentos anteriores. No sigue pendiente elegir cuál fuente manda.

Se revisó la estructura y rangos de datos de sus ocho pestañas, en modo de solo lectura:

| Pestaña | Datos que permiten elegir un precio |
|---|---|
| Fundas a medida | Marca/modelo y variantes, configuración de asientos, efectivo/transferencia; adicional de logo indicado aparte. |
| TIPO TAPIZADO | Modelo/variante, configuración de asientos y efectivo/transferencia. Los encabezados varían por sección: hay configuraciones de 6, 9 y 12 asientos, además de las habituales. |
| TAPICERIA | Modelo, 5/2/7 plazas o butaca y butacón, según sección; efectivo/transferencia. |
| Termoformadas | Marca, modelo/generación/configuración y efectivo/transferencia. |
| Funda Baúl - Antiderrame | Modelo/generación y efectivo/transferencia. |
| Cobertores de caja | Modelo y variante, como furgón o 5 asientos; efectivo/transferencia. |
| ESPUMAS | Vehículo/variante, asiento o respaldo, efectivo/transferencia. |
| Otros | Producto o servicio, efectivo, transferencia y una columna separada para POSNET/cuotas cuando hay importe. |

Implicaciones para el diseño:

- Leer el importe explícito de la celda correspondiente. Los porcentajes escritos en encabezados no justifican recalcular todos los precios con una fórmula única. Conservar hoja, fila, columna y fecha de consulta como origen de la cotización.
- No interpretar una celda vacía, un guion o una `x` como precio cero. Si falta el dato necesario para seleccionar una fila o un medio de pago no tiene precio, no inventar el importe.
- Mantener separados producto, modelo/variante, configuración de asientos, modalidad y medio de pago. Los encabezados de asientos cambian entre secciones; no asumir una configuración fija por letra de columna para toda la hoja.
- La tabla de precios no demuestra por sí sola existencia de medidas ni stock. También hay rótulos y filas incompletas que requieren un criterio de selección conservador, sin corregir la planilla original por nuestra cuenta.
- La descripción anterior de «crédito menos 10% para transferencia por envío» no se debe aplicar automáticamente por encima de las celdas oficiales. Las condiciones comerciales no expresadas en la planilla se mantienen separadas, pendientes de definición solo si resultan necesarias para la ruta que se implemente.
- Que una categoría figure en la planilla amplía la información disponible; no autoriza por sí solo a automatizar toda su venta ni a cambiar los límites de atención ya definidos.

Alcance de lectura: `A1:X24` y `A25:L300` en las cuatro primeras pestañas; `A1:U25` en las cuatro complementarias, con extensión en Baúl hasta la fila 45 y ESPUMAS hasta la 145. Se inspeccionaron encabezados, ejemplos, variantes y faltantes; no fue una auditoría completa de todas las celdas de la grilla. No se modificaron datos, fórmulas ni permisos de la planilla.

Próximo trabajo: preparar el mapa de conversaciones y la correspondencia entre cada consulta del cliente y la fila de precios oficial, usando el alcance ya confirmado. No se implementó ni desplegó ningún cambio comercial en esta revisión.
