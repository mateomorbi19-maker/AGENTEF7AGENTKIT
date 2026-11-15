# Cotización natural — cambio aprobado por Mateo

Pedido: reemplazar la lista de precios por un mensaje natural, siempre con el valor por transferencia y luego la pregunta exacta «Quisieras aprovechar el valor en transferencia o en 3 cuotas sin interes?». Mateo autorizó implementar, publicar y ejecutar siete conversaciones realistas.

## Comportamiento publicado

El motor de precios genera el texto completo y el único POST de Chatwoot lo envía sin pasar por el divisor de frases del agente. La comparación reúne las alternativas en un párrafo y no las suma. El combo completo enumera productos/cantidades/coberturas en prosa y presenta un solo total. Los ítems con cantidad mayor a uno conservan una distinción clara entre total y valor unitario cuando corresponde.

Se mantienen las celdas y cálculos oficiales: la presentación usa transferencia; cuotas tiene el mismo total. No se infiere transferencia desde efectivo si la fuente no la contiene. Los resultados parciales conservan los pendientes, sin un total completo ni la pregunta de cierre de una cotización completa. La pregunta incluida en el texto es la misma en CABA y envío. Las advertencias existentes sobre flete y medidas se conservan.

Tras aceptación u omisión de una cotización completa, `continuacion_obligatoria` queda vacía. El agente no agrega otra pregunta ni repite importes. Una FAQ explícita validada puede contestarse aparte. Las aclaraciones, errores y resultados inciertos siguen siendo visibles; el silencio no se usa para encubrir una falla de envío.

## Ajuste V9.1 del historial

La primera tanda mostró recotizaciones innecesarias ante video y color. Había antecedentes de esa conducta, pero V9 dejó sin rastro de cotización el historial porque la continuación pública pasó a ser vacía. Se corrigió esa pérdida de evidencia: `memoria_output` agrega una constancia interna determinística desde la observación real de la herramienta, con aceptación, ID válido e ítems coherentes. No contiene importes ni se envía al cliente. Se usa la misma memoria Postgres y SQL parametrizado; no hay tablas nuevas ni manager adicional.

El prompt aclara que fotos/videos/diseño/color no requieren volver a cotizar un pedido ya cotizado. Un cambio de producto, modelo, cantidad, cobertura o modalidad, o un pedido explícito de precio/total actual, sí puede requerir nueva consulta. Esto no garantiza por sí solo que el modelo conserve correctamente todas las decisiones del cliente; los resultados conversacionales se revisan aparte.

## Verificación

- Revisión final: 456 pruebas aprobadas, cero fallos/omitidas y cuatro TODO históricos. Incluye ejecución local real de SQL con PGlite, protección de memoria, contrato de herramientas, importe y JSON de un único POST.
- [Publicación y backups](PUBLICACION_COTIZACION_NATURAL_F7_2026-11-05_final.json): grafos activos, conexiones y credenciales comparados con la versión probada. Validación n8n sin errores; queda una advertencia heurística previa en Normalizar evento.
- [Runtime 36323](RUNTIME_COTIZACION_NATURAL_F7_2026-11-05.json): ocho hojas leídas en vivo, valores iguales a la fixture, siete artículos cotizados y dos pendientes. Sin LLM, Postgres ni Chatwoot.
- [Primera tanda de siete casos](PRUEBA_COTIZACION_NATURAL_F7_2026-11-05.json) y [revisión](REVISION_COTIZACION_NATURAL_F7_2026-11-05.md) conservadas sin reescribir. La segunda tanda usa el mismo conjunto y su propio reporte `_r2`.

Las conversaciones usan Haiku real con la clave local autorizada y transporte simulado. No acreditan entrega, pase humano ni cadena completa en n8n. La credencial n8n no se modificó y Chatwoot conserva su webhook anterior. Se conserva el tope monetario de USD 1,25 para ambas tandas; el límite técnico se amplió de 120 a 200 generaciones para poder repetir los siete casos tras corregir la pérdida de memoria.

## Resultado de las dos tandas y corrección posterior

Total consumido estimado: USD 0,83904005,149 generaciones; sin consumo incierto. R2 quedó no aprobada para atención real: logró comparación y combos correctos, pero conserva recotizaciones y confusión de selección/año, una segunda llamada de precio bloqueada y un falso pase humano. Detalle literal en [revisión R2](REVISION_COTIZACION_NATURAL_F7_2026-11-05_R2.md).

R2 03T7 expuso el registro interno en la salida libre del modelo. Se agregó después una protección determinística: marcador interno o estructura técnica equivalente en texto libre produce salida pública vacía y activa el fallback humano existente. Las ramas de precio/humano con resultado comprobado conservan su comportamiento. Se verificó la reproducción exacta y variantes en pruebas locales; no se ejecutó otra tanda con LLM. Los chats R2 conservan el fallo observado, sin sustituirlo por lo que habría ocurrido con la protección final.
