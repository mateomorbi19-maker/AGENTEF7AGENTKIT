# Biblioteca de fotos y videos F7

Recopilación del 3 y 4 de noviembre de 2026, solicitada por Mateo para preparar los medios del futuro agente. Abrí [el índice visual](index.html) para ver las imágenes y reproducir o abrir los videos.

Se conservaron los archivos descargados sin editar ni recomprimir. Las carpetas por producto contienen copias con nombres descriptivos. Las carpetas `_ingesta_*` conservan la descarga de cada fuente; no cuentan como piezas adicionales. `_previews` y `_verificacion` contienen fotogramas auxiliares, no fotos comerciales independientes.

## Qué está confirmado

| Prefijo | Fuente | Qué acredita |
|---|---|---|
| `MP` | Messenger | Pieza comercial enviada por F7 y recuperada desde el chat. Puede ser una versión comprimida por Meta. |
| `N8N` | Herramienta de fotos viva | Archivo referenciado por la configuración actual y descargado de Drive. Su presencia en n8n no prueba su envío en Messenger. |
| `DRV` | Biblioteca comercial F7 de Drive | Archivo del producto recuperado de las carpetas del negocio. Queda pendiente confirmar que sea la versión que se envía actualmente. |

La biblioteca reúne **20 archivos catalogados: 12 imágenes y 8 videos**. Incluye versiones de distintas fuentes, por lo que no son 20 contenidos comerciales diferentes. Ocho archivos tienen envío observado en Messenger: seis imágenes y dos videos.

## Carpetas por producto

| Carpeta | Contenido |
|---|---|
| [fundas/disenos](fundas/disenos/) | Diamante, Bastón, VIP, Hexagonal y Ultra. Versiones de Messenger y de n8n identificadas por separado. |
| [fundas/colores](fundas/colores/) | Carta de colores, costuras, vivos y logos. |
| [fundas/videos](fundas/videos/) | Presentación, comparación con tipo tapizado y demostraciones de calidad/ajuste. |
| [tipo-tapizado](tipo-tapizado/) | Referencias al material compartido con fundas, sin duplicar los videos. |
| [alfombra/videos](alfombra/videos/) | Demostración de colocación de n8n y presentación recuperada de Drive. |
| [cubrevolante/videos](cubrevolante/videos/) | Video de cubrevolante recuperado de Drive. |

## Piezas verificadas en Messenger

| ID | Pieza | Observación |
|---|---|---|
| MP01 | Comparación de fundas, 47 s | Primero presenta **fundas a medida** y después **fundas tipo tapizado**. Con audio. |
| MP02 | Presentación de fundas, 28 s | Presenta fundas a medida; comparte escenas con MP01, pero es otro archivo. Con audio. |
| MP03 | Diamante | Lámina con variantes. Descarga disponible en WebP de 480 × 679; el JPG de n8n tiene mayor resolución y coincide visualmente. |
| MP04 | Colores y logos | Carta de personalización. |
| MP05 | Bastón | Incluye Bastón chico, grande y deportivo. |
| MP06 | VIP | Incluye las variantes que aparecen rotuladas en la lámina actual. |
| MP07 | Hexagonal | Lámina con versión deportiva. |
| MP08 | Ultra | Lámina con versión deportiva. |

MP02 y las seis láminas se recuperaron de la conversación anónima M05 del relevamiento, enviadas el 03/11/2026. MP01 se recuperó de otra consulta por una Ranger 2015 doble cabina, también con envío del 03/11. El catálogo omite nombres de clientes, datos de contacto y URLs privadas de las conversaciones.

## Diferencias a tener presentes al armar las herramientas

- **VIP y Bastón cambiaron:** las láminas enviadas por Messenger no son las imágenes homónimas configuradas en n8n. Las actuales muestran varias variantes; las anteriores son fotos individuales con anotaciones. No sustituirlas solo por coincidencia de nombre.
- **Colores, Diamante, Hexagonal y Ultra:** hay coincidencia visual entre las versiones revisadas de Messenger y n8n, pero sus archivos no son idénticos. Se conservan ambas procedencias.
- **Tipo tapizado:** el uso compartido del catálogo de diseños proviene de la configuración de n8n. Las láminas por sí mismas no acreditan qué variantes corresponden a cada producto. El video MP01 sí nombra ambas opciones y permite identificar su orden.
- **Los tres videos DRV no reemplazan automáticamente referencias rotas.** Sus IDs son diferentes de los inaccesibles. El comparativo DRV01 dura 34 s y muestra un presentador; es distinto del MP01 de 47 s.
- Los videos de n8n recuperados no tienen pista de audio. MP01, MP02 y algunos originales de Drive sí tienen audio; no se transcribió ni validó su discurso comercial.

## Pendientes concretos

Tres referencias de la herramienta viva devolvieron 404 con la cuenta conectada: comparación de fundas, cubrevolante e introducción de alfombra. Esto indica que no se pudieron recuperar con ese acceso; no demuestra que los archivos hayan sido borrados. Sus IDs y nodos están en [referencias-n8n.json](../../docs/medios-f7/referencias-n8n.json).

Los videos de alfombra y cubrevolante ya están guardados desde las fuentes disponibles, pero su envío actual por Messenger no quedó confirmado en los tramos revisados. La búsqueda no cubrió todo el historial. Tampoco se recuperó la versión de máxima resolución de Diamante desde Messenger.

## Trazabilidad y reutilización

El [catálogo detallado](../../docs/medios-f7/catalogo-recuperado.json) registra para cada archivo su fuente, ruta, SHA-256, tamaño, formato, dimensiones, duración, audio y límites de la verificación. El [manifiesto de los candidatos de Drive](../../docs/medios-f7/candidatos-drive.json) conserva sus IDs y carpetas de origen. Cada copia organizada se compara con su ingesta mediante SHA-256.

Al desarrollar las herramientas, usar los IDs del catálogo para elegir la pieza y su momento de envío. Estos archivos no fijan precios, disponibilidad de diseños/materiales ni frases del guion. La selección comercial y su integración al agente se harán en la etapa correspondiente del proyecto.

No se enviaron mensajes, ejecutaron workflows ni modificaron prompts, credenciales o archivos de Drive. No se consumieron APIs pagas de modelos, generación o transcripción para recopilar y verificar estos medios.
