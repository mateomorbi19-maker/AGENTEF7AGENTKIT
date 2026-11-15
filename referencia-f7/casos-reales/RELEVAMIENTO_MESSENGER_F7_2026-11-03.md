# Consultas reales de Messenger — F7

Fecha de revisión: 3 de noviembre de 2026. Estado: material de análisis y preparación de pruebas; no modifica el guion aprobado.

## Alcance y resultado

Se leyeron tramos de **31 conversaciones distintas** en la bandeja de Messenger de F7, incluyendo su contexto y repreguntas. La selección combinó recorrido de conversaciones recientes y búsquedas dentro de los mensajes para ampliar temas: tarjetas, demoras, seña, precio caro, desconfianza, alfombras, pedidos, compras previas y alias. Los resultados de búsqueda que no se abrieron no se cuentan como conversaciones revisadas.

La muestra tiene variedad suficiente para preparar una primera batería de conversaciones de preventa y excepciones. Incluye comparaciones, correcciones, consultas por varios productos, configuraciones especiales, recompra, reventa y un cierre con pago informado. **No es una muestra estadística ni un relevamiento completo de la bandeja.** La selección por términos busca diversidad y no permite estimar qué porcentaje de clientes pregunta cada cosa.

La mayor parte de los ejemplos es de 2026. M22 es de enero de 2024 y M31 de enero de 2025: se incluyen como situaciones históricas útiles, sin trasladar sus condiciones comerciales al presente. Las fechas que muestra el listado pueden corresponder a la última actividad; para los casos históricos se leyó la fecha dentro del hilo.

Se conservaron mensajes de clientes sin nombres, teléfonos, perfiles, correos, alias de pago, comprobantes ni direcciones particulares. Las localidades y los modelos se mantienen cuando son necesarios para entender la consulta. El corpus es anónimo en su presentación; las citas y combinaciones de datos aún podrían permitir reconocer una conversación a quien conoce la bandeja, por lo que no se plantea como dataset público.

Archivos reutilizables:

- [Casos M01–M20](relevamiento-messenger/casos-01-20.json).
- [Casos M21–M31](relevamiento-messenger/casos-21-31.json).

Cada ficha contiene mensajes seleccionados, contexto observado, tipo de entrada, criterios propuestos para pruebas y límites. No son transcripciones completas ni respuestas esperadas ya aprobadas.

## Hallazgos que deben entrar en las pruebas

### 1. Una consulta puede contener varias necesidades

M18 pregunta en un mismo mensaje por precio, formas de pago, demora y tarjeta bancaria para un Peugeot 306 de 1996. M02 ya aporta vehículo, envío a Chaco y color negro. M19 prioriza resistencia y protección para un vehículo de Uber, además de precio y plazo.

Una prueba debe comprobar que esas preguntas se conservan pendientes hasta ser atendidas. Pedir el siguiente dato del guion no debería borrar lo que el cliente ya preguntó. La forma de resolver esa tensión debe ajustarse al recorrido aprobado; este informe no cambia su orden.

### 2. La insistencia por precio es una situación real y distinta de una consulta nueva

En M03 la secuencia es «Hola cuánto sale?» → «Una Duster» → «Cuánto salen?» → «Me decís el precio?». M08 dice «Quisiera saver el precio primero gracias». M07 y M14 responden «El precio» luego de recibir contenido y otras preguntas.

No alcanza con evaluar que el agente identifica la palabra precio. Debe conservar el modelo, reconocer la insistencia y explicar o resolver el dato que realmente falta según el guion. No se deducen enojo, abandono ni falta de interés solamente de estas secuencias.

### 3. El cliente puede necesitar información antes de elegir envío o colocación

M04 dice «Si es muy difícil....lo llevaría a colocar» y «Pero si es fácil, no tendría inconveniente en recibirlo y hacerlo yo». También pregunta si “cuero automotor” es ecocuero o cuerina. M21 pide conocer dos precios y aclara que suele ir a CABA.

La modalidad puede estar pendiente, ser condicional o ser objeto de una comparación. No corresponde guardarla como decidida solo porque el mensaje menciona CABA o envío.

### 4. Hay elecciones que solo se entienden con el contenido anterior

M12 responde «La segunda» y «Pero toda negra». M27 dice «Las segundas con cuero automotor completas! De las mismas que les compre a mi autito». M20 menciona dos diseños posibles y define colores de superficie y costuras.

Para recrear estos casos hay que incluir qué opciones presentó la herramienta y en qué orden. Los videos comerciales no se reprodujeron en esta revisión; no se asigna por intuición un producto a “la segunda”. Interesarse por dos diseños tampoco equivale a elegir uno.

### 5. Las correcciones tienen que actualizar el pedido completo

M16 aclara «Yo estoy buscando fundas» después de recibir una respuesta automática sobre cubrevolante. M23 corrige «No es una Suran, es un Fiat Cronos». M30, después de una cotización, agrega «Son dos butacs» y «Es cabina simplw».

Estos casos sirven para comprobar que el agente sustituye el dato incorrecto, conserva los demás y vuelve a consultar la tarifa que corresponda. Los importes históricos no se reutilizan como valores esperados.

### 6. Atender solo un producto puede dejar sin resolver el pedido

M23 consulta por fundas, cubrevolante y alfombra trasera de goma entera. Pregunta «Me pasarían el precio total por las tres cosas?» y «La colocación con qué cargo cuenta?». Más adelante explica: «Pero solo me envían el precio del cubre volante a 72mil» y «Por eso no les contesté más».

En este caso el propio cliente vincula su silencio con la respuesta incompleta. Es una evidencia concreta para priorizar pruebas de pedidos de varios productos: conservar cada artículo, su compatibilidad, las preguntas pendientes y el pedido de total. El importe mencionado pertenece a su mensaje histórico, no a una tarifa vigente.

### 7. El modelo del vehículo no siempre determina las butacas

M05 informa tres asientos en una Partner Van. M11 repite “Spin Activ 2018” cuando se le pregunta la cantidad de butacas. M13 escribe “Master 3”, sin aclarar qué representa ese número. M28 tiene una Boxer con dos butacas de otra camioneta y dice «Creo que de amarok o una así».

Las pruebas deben impedir que el agente transforme una suposición en una configuración confirmada. En M28 la incertidumbre sobre el origen de las butacas es parte central del caso, y puede requerir revisión humana conforme al alcance aprobado.

### 8. Retomar y volver a comprar son recorridos distintos

M01, M07 y M15 retoman consultas separadas por semanas o meses. M27 afirma haber comprado antes para un Cronos y ahora consulta por una Ranger 2026, incluyendo la palabra “ranger” en las fundas.

El historial ayuda a entender la conversación, pero no convierte un precio o una afirmación antigua de compatibilidad en un dato vigente. Una compra anterior tampoco define automáticamente el modelo, diseño ni configuración de la nueva.

### 9. Las excepciones no deberían convertirse en promesas automáticas

- M17 necesita tarjeta en tres cuotas y sigue con una dificultad en el apoyabrazos; adjunta un video. Recibirlo no equivale a haberlo analizado.
- M21 rechaza por presupuesto. Conviene distinguir esa negativa de una solicitud de otra cotización.
- M22 desconfía de la seña; el ejemplo es histórico y no autoriza nuevas condiciones de pago.
- M26 consulta por descuento para reventa desde un taller. No corresponde inventar una política mayorista.
- M29 cuenta que una funda comprada quedó angosta y se rompió. No se pudo establecer quién la vendió: no es evidencia de un reclamo confirmado contra F7.
- M31 pide alias y luego afirma que envió la seña. Esa afirmación no prueba acreditación. El cierre, pago y coordinación corresponden a Candela según el brief.

## Índice de la muestra

| Caso | Situación principal | Aporte a la variedad |
|---|---|---|
| M01 | Prisma 2017, fotos, envío y retoma | Historial y medidas vigentes |
| M02 | Strada, Chaco y negro en el mismo mensaje | Extracción de varios datos |
| M03 | Duster, insiste tres veces por precio | Pregunta comercial pendiente |
| M04 | Prisma Joy, material e instalación condicional | Dudas antes de elegir modalidad |
| M05 | Partner Van de tres asientos | Configuración fuera del juego habitual |
| M06 | Ubicación prearmada repetida | Botones y múltiples automatismos |
| M07 | Duster 2.0, Río Gallegos y retoma | Consulta antigua que vuelve |
| M08 | Fiesta 2005, precio primero y dirección | Cambio de pregunta sin perder contexto |
| M09 | Corolla, fotos para después | Información pendiente |
| M10 | Suran 2007 con envío | Caso sencillo de control |
| M11 | Spin sin cantidad textual confirmada | No inferir plazas por modelo |
| M12 | “La segunda”, “toda negra” | Referencia al contenido anterior |
| M13 | Master 3, “una de cuero” | Cantidad y producto ambiguos |
| M14 | Amarok cabina simple | Presupuesto orientativo |
| M15 | Cronos 2026, CABA y ubicación | Retoma y explicación de precios |
| M16 | Buscaba fundas, automatismo de cubrevolante | Corrección de producto |
| M17 | Tres cuotas y apoyabrazos que no pudo retirar | Restricción de pago y revisión técnica |
| M18 | Peugeot 306: precio, pago y demora | Varias preguntas en un turno |
| M19 | Cronos para Uber | Protección y durabilidad como prioridad |
| M20 | Ecosport, dos diseños y colores de costuras | Preferencias detalladas sin elección final |
| M21 | Cronos y negativa por presupuesto | Comparación y rechazo explícito |
| M22 | Desconfianza de la seña, enero de 2024 | Objeción histórica |
| M23 | Tres productos y corrección de vehículo | Pedido incompleto y recuperación |
| M24 | Alfombra para Siena | Compatibilidad de otro producto |
| M25 | Ecosport y pedido de funda toda en cuero | Solicitud especial y modalidad por precisar |
| M26 | Taller interesado en reventa | Consulta comercial de otro negocio |
| M27 | Compró para Cronos, ahora Ranger con logos | Recompra y personalización |
| M28 | Boxer con butacas no originales | Límite del catálogo por vehículo |
| M29 | Funda angosta y rota, vendedor sin identificar | Problema posterior a una compra |
| M30 | Saveiro, dos butacas aclaradas después del precio | Actualización de configuración |
| M31 | Alias, seña informada y turno, enero de 2025 | Pase al trabajo de Candela |

## Qué queda sin muestra suficiente

No se obtuvo una muestra verificable de audios de clientes transcritos, seguimiento actual de un pedido de F7 ya pagado, reclamo confirmado de garantía contra F7, devolución resuelta, ni colocación específica en Bariloche/Villa La Angostura/El Bolsón. La búsqueda de “reclamo” no devolvió resultados; eso no demuestra que tales conversaciones no existan. Tampoco se reconstruyó un pedido completo de principio a fin con sus fotos, comprobantes y carga interna.

Se vieron videos y referencias a fotos, pero no se reprodujeron ni descargaron. M17 permite probar “adjunto recibido / análisis pendiente”, no la exactitud de una interpretación audiovisual. Los tiempos de cada evento no se exportaron: para recrear ráfagas y el buffer de 15 segundos habrá que declarar intervalos sintéticos, sin presentarlos como tiempos reales de Messenger.

Se cerró esta revisión porque ya hay variedad útil para una primera batería y límites concretos documentados. No se afirma saturación de toda la bandeja: todavía hay categorías con ejemplos únicos y otras sin muestra.

## Uso propuesto para el mapa y las pruebas

1. Seleccionar recorridos completos a partir de las fichas: cliente nuevo, envío, visita, elección, corrección, varios productos, excepción y pase a Candela.
2. Reconstruir el contexto mínimo de cada turno. Diferenciar citas, resúmenes y cualquier mensaje de enlace que se redacte para la simulación.
3. Preparar la respuesta esperada usando el brief y el guion aprobado. Para precios y métodos de pago, usar la [planilla oficial indicada por Mateo](https://docs.google.com/spreadsheets/d/1dl7hNofQp8v57h1Veodd3XqFctJxAvgAA2qXVtnE1ZU/edit), identificando la versión o fecha usada. Los chats no reemplazan esa fuente.
4. Mantener el límite del brief: el agente cubre cotización y elección de diseño/color; Candela continúa el cierre, envío del alias, confirmación de elecciones, datos y fotos, revisión y armado del pedido. El pase antes de elegir diseño/color del C10 del mapa anterior era una propuesta, no una aprobación inferida de estas conversaciones.
5. Evaluar primero conservación de contexto, preguntas pendientes, selección de producto y herramientas, manejo de correcciones y límites de derivación. Cada criterio de las fichas es una propuesta de evaluación, no una nueva frase contractual.

La lectura y preparación del corpus no invocó los modelos por API, no ejecutó n8n ni envió mensajes a clientes. Todavía no se probó cómo responde el agente a estos casos. Una recreación local con herramientas simuladas puede verificar lógica y contexto sin esas llamadas; medir la respuesta del modelo configurado requiere ejecutarlo o disponer de respuestas grabadas válidas.

## Cambios realizados

Solo se incorporaron este informe, los dos archivos de casos y el registro de sesión en el backlog. No se modificaron prompt, herramientas, workflows, credenciales ni la planilla oficial. En Messenger se navegó y leyó: no se enviaron respuestas ni se modificaron etiquetas, asignaciones o ajustes. La apertura de hilos puede afectar su estado de leído. Sin commit ni push.
