# Herramienta multimedia F7 — v1

Estado al 2026-11-04: creado [F7 · Enviar multimedia · v1](https://n8n.teotec.org/workflow/BArOU48SoyGqiDE7), ID `BArOU48SoyGqiDE7`, inactivo, 55 nodos (49 ejecutables y 6 notas). Prueba real completada con cuatro videos en la conversación 27. El nodo `Ejemplo seguro` quedó restaurado a `simular` y `pinData` está vacío. Después se conectó como única herramienta del principal unificado inactivo con el [prompt nuevo](SYSTEM_PROMPT_F7_V1.md). No se modificó la herramienta fotos de la cadena anterior.

## Qué hace

Recibe una lista de pedidos, elige archivos de un catálogo cerrado y los envía de a uno por Chatwoot. Una llamada puede pedir uno, dos, tres o los cuatro productos, mezclar presentación/diseños/colores/calidad y filtrar fotos o videos. No usa un modelo de IA dentro de la herramienta.

El catálogo tiene 14 archivos habilitados y 22 rutas. Las diez copias autorizadas por Mateo se subieron a [F7 de Drive](https://drive.google.com/drive/folders/1YM8dcc_Dr6CcHpsoWVTyIXrjLAIqcJu9), sin cambiar permisos. Se verificaron nombre, MIME y tamaño de las diez: 29.963.643 bytes en total. Las otras cuatro piezas reutilizan IDs existentes. Procedencia, hashes y conversiones: [manifiesto](medios-f7/preparacion-multimedia.json).

| Pedido de presentación | Archivos seleccionados |
|---|---|
| Solo fundas | MP02, video exclusivo de fundas |
| Solo tipo tapizado | TT01, video exclusivo de tipo tapizado |
| Solo alfombra | AL01 + N8N01, presentación y colocación |
| Solo cubrevolante | CV01 |
| Fundas y tipo tapizado | MP01, comparativo una sola vez |
| Los cuatro productos | MP01 + AL01 + N8N01 + CV01 |

Para cualquier otra combinación se conserva la selección exclusiva de cada producto. Un archivo que muestra dos categorías exige que ambas estén solicitadas para ese contenido y formato. Pedir presentación de fundas y diseños de tipo tapizado no habilita el comparativo. La carta de colores y las cinco láminas de diseños son material compartido según las rutas del catálogo anterior; su uso no confirma medidas ni stock.

## Contrato de entrada

El modelo recibe solamente `solicitudes`. El flujo llamador fija `account_id`, `conversation_id`, `solicitud_id` y `modo` a partir del evento confiable. No usar `$fromAI` para esos cuatro campos ni permitir que el modelo elija una URL o un ID de Drive.

```json
{
  "account_id": 1,
  "conversation_id": 24,
  "solicitud_id": "cw:mensaje-123:multimedia-1",
  "modo": "enviar",
  "solicitudes": [
    { "producto": "fundas", "contenido": "presentacion" },
    { "producto": "alfombra", "contenido": "presentacion" }
  ]
}
```

El ejemplo ilustra el contrato; no ejecutarlo contra la conversación real para probar. `solicitud_id` debe mantenerse en los reintentos del mismo pedido. Una nueva solicitud del cliente lleva otro identificador. No generarlo con la fecha actual en cada intento ni usar solo el ID de ejecución del subworkflow.

| Campo de cada solicitud | Valores |
|---|---|
| `producto` | `fundas`, `tipo tapizado`, `alfombra`, `cubrevolante` |
| `contenido` | `presentacion`, `disenos`, `colores`, `calidad`, `comparacion` |
| `formato` opcional | `auto` por defecto, `foto`, `video` |
| `disenos` opcional | Array usado solo con `disenos`: `baston`, `vip`, `hexagonal`, `diamante`, `ultra` |
| `reenvio_solicitado` opcional | Booleano; conserva la intención explícita, no anula la protección del mismo pedido |

Para todos los productos, enumerar los cuatro; no enviar `producto: "todos"`. Para todos los diseños, omitir el filtro `disenos`. Para comparar, incluir fundas y tipo tapizado con `contenido: "comparacion"` en ambas solicitudes. Máximo 16 solicitudes y 20 archivos por llamada. Cualquier campo o producto inválido rechaza la llamada completa. Un pedido válido sin material compatible se informa en `faltantes`; nunca se sustituye por otro producto.

Ejemplo de diseños concretos y otro producto:

```json
{
  "modo": "simular",
  "solicitudes": [
    { "producto": "fundas", "contenido": "disenos", "disenos": ["vip", "diamante"], "formato": "foto" },
    { "producto": "cubrevolante", "contenido": "presentacion" }
  ]
}
```

## Envío, registro y fallos

1. Normalizar y seleccionar; `simular` termina acá, sin credenciales ni I/O.
2. Preparar tres tablas `f7_multimedia_*` si no existen. No se modifican tablas comerciales anteriores. RLS habilitado sin políticas públicas; el credential Postgres debe tener permisos para operar estas tablas.
3. Adquirir exclusión por conversación y registrar la huella del pedido. El mismo identificador con contenido distinto se rechaza.
4. Reservar cada archivo y descargarlo con OAuth de Drive. Después de calcular SHA-256, `Recuperar binario tras hash` une el resultado JSON de Crypto con el binario de esa misma iteración de Drive. Verificar hash, bytes, firma del formato y límites de tamaño. Fotos JPEG/PNG hasta 5 MiB y videos MP4 hasta 16 MiB.
5. Consultar la conversación antes de cada envío. La etiqueta `humano`, una identidad distinta o la imposibilidad de verificar etiquetas detienen el lote.
6. Confirmar en Postgres el estado `enviando` antes del POST multipart con `attachments[]`. Nunca reintentar automáticamente ese POST. Revalidar el margen de tiempo antes de comenzarlo.
7. Registrar el resultado por archivo, continuar cuando corresponda, devolver un resumen y liberar únicamente el bloqueo propio.

La exclusión dura 900 segundos y el workflow tiene timeout de 480 segundos. No inicia otro POST después del segundo 390; reserva margen para el POST de hasta 60 segundos y el registro. Una caída o cancelación externa todavía puede interrumpir el resumen. Las filas `enviando`/`desconocido` permanecen protegidas incluso después de vencer el bloqueo.

La deduplicación funciona dentro de la misma `solicitud_id`, por archivo y versión. Un resultado `fallo_previo` puede volver a intentarse porque no comenzó el POST. Un envío aceptado se omite. Un rechazo posterior no se vuelve a ejecutar automáticamente; una incertidumbre detiene lo pendiente. Un pedido nuevo puede volver a enviar material: el prompt deberá evitar pedidos redundantes no solicitados. No se implementa memoria comercial ni bloqueo permanente de material ya visto.

Para conciliar un resultado incierto, revisar la ejecución y los mensajes de la conversación en Chatwoot antes de autorizar un nuevo intento. No borrar filas ni cambiar a `fallo_previo` por suposición. No hay un nodo que resuelva automáticamente la incertidumbre.

## Qué devuelve al agente

Un único objeto con `estado`, `solicitud_id`, `modo`, `aceptados`, `omitidos`, `fallidos`, `desconocidos`, `control_humano`, `simulados`, `faltantes`, `errores` y el detalle de cobertura de cada solicitud. Cuando se detiene el lote también informa lo que quedó sin intentar. No devuelve secretos ni respuestas crudas del proveedor.

`aceptado` significa que Chatwoot confirmó un mensaje público con adjunto e identidad verificables. **No confirma entrega ni lectura en WhatsApp**: `entrega_confirmada` queda en `false`. El futuro prompt debe usar los resultados reales; no afirmar que envió todo ante fallas parciales, simulación o incertidumbre, ni repetir ciegamente la herramienta.

Los mensajes de esta herramienta contienen únicamente el adjunto, **sin pie de foto ni texto**, por indicación explícita de Mateo del 2026-11-04. El HTTP multipart omite `content`; los títulos del catálogo se conservan como metadatos internos. Cotizaciones, preguntas de venta, cierres y derivación siguen fuera de este workflow.

Comprobación del ajuste: ejecución [36271](https://n8n.teotec.org/workflow/BArOU48SoyGqiDE7/executions/36271), video `CV01` enviado a la conversación de prueba 27. Chatwoot confirmó el mensaje 9718 con `content:null`, un adjunto de video y estado posterior `delivered`.

## Verificación y condiciones de integración

- Suite final: 127 pruebas pasan, 0 fallan, 4 TODO anteriores. Incluye SQL PGlite. Validador n8n: 0 errores, 0 conexiones inválidas, 1 advertencia heurística esperada en la salida final del loop.
- Selección: quince combinaciones de productos, diseños, formatos, pedidos inválidos, material faltante y contenido compartido.
- Código embebido y grafo: simulación sin I/O, conexiones, errores externos, recuperación del binario después de Crypto en dos iteraciones con archivos distintos, consultas parametrizadas, POST sin retry, IDs BIGINT y margen de tiempo.
- Postgres local PGlite: SQL real para exclusión, huella, idempotencia, estados, vencimiento, parámetros y RLS. No equivale a probar el credential de la instancia.
- Historial de runtime, conversación 27: la [prueba 36248](https://n8n.teotec.org/workflow/BArOU48SoyGqiDE7/executions/36248) confirmó esquema, reservas, registros, iteración, resumen y liberación de Postgres; los cuatro archivos fallaron antes de enviar porque el OAuth de Drive necesitaba reconexión. No ejecutó ningún POST Chatwoot.
- Tras reconectar OAuth, la [prueba 36250](https://n8n.teotec.org/workflow/BArOU48SoyGqiDE7/executions/36250) descargó los cuatro archivos y detectó que Crypto v1 devolvía el hash en JSON sin conservar `binary`. La validación impidió los envíos. Se agregó `Recuperar binario tras hash`, con vínculo al item de Drive de la misma iteración y una prueba de regresión.
- La [prueba 36251](https://n8n.teotec.org/workflow/BArOU48SoyGqiDE7/executions/36251) terminó correctamente en 30,191 segundos: MP01 → mensaje 9714, AL01 → 9715, N8N01 → 9716 y CV01 → 9717. Los cuatro resultados quedaron registrados como `aceptado` y el bloqueo se liberó. Una consulta posterior a Chatwoot confirmó los cuatro en estado `read`, con un adjunto de video cada uno y tamaños correctos. Esa comprobación posterior no cambia el contrato de salida: la herramienta sigue informando aceptación, sin prometer entrega o lectura. [Evidencia local](../backups/2026-11-04-multimedia-prueba-27/resultado-36251.json).
- Alcance comprobado con el OAuth de n8n: esos cuatro videos, incluida descarga, integridad y envío. Queda comprobar el acceso y la integridad de los otros diez archivos del catálogo; tener acceso con el conector de Drive de Codex no prueba ese acceso. El pedido `f7-smoke-20261104-c27-01` ya tiene sus cuatro piezas aceptadas: reutilizar ese ID debe omitirlas, no volver a enviarlas.
- Integración preparada en el principal inactivo: solamente `solicitudes` proviene del modelo; destino, modo e identificador estable los fija el principal. El prompt interpreta resultados parciales, control humano e incertidumbre, y recibe el registro real de archivos aceptados/inciertos de la conversación.
- Tiempos del principal actualizados: timeout 780 s, Redis 900 s; inicio de herramienta permitido hasta 210 s desde normalización, 480 s para esta herramienta y 90 s de margen. Falta probar ese presupuesto en runtime del principal completo.
- Antes del webhook de producción, Mateo debe publicar la herramienta y el principal según el protocolo de activación. La herramienta no tiene `activeVersion` publicada; una ejecución manual del borrador no demuestra que pueda invocarse desde producción. No se publicó ni activó en esta etapa.
- La simulación manual se inicia con `Probar seleccion sin enviar`: cuatro presentaciones y respuesta estructurada. No requiere conversación, Drive, Postgres, Chatwoot ni créditos de LLM.
- Completar con Mateo las pruebas de integración de pedidos mixtos, fotos y diseños, control humano, repetición de la misma solicitud y un error parcial. La activación y el cambio del webhook siguen a cargo de Mateo conforme a `AGENTS.md`.

No se agregó un workflow global de errores. Fallas externas previstas tienen salidas conectadas; una excepción inesperada queda en ejecuciones, conserva el registro existente y deja vencer el bloqueo. Falta definir monitoreo operativo antes de producción.

## Mantenimiento

Fuentes: `src/multimedia/catalogo.json`, `seleccion.mjs`, `entrega.mjs`, `sql.mjs` y `construir.mjs`. El constructor incorpora código y catálogo al JSON del workflow; no necesita archivos del disco local en runtime.

```powershell
node src/multimedia/construir.mjs
npm.cmd test
npm.cmd run import -- herramienta-multimedia-v1
# Revisar diff y backup antes de aplicar una actualización futura.
npm.cmd run import -- herramienta-multimedia-v1 --yes
```

Para incluir las pruebas SQL, `F7_PGLITE_MODULE` debe apuntar a `dist/index.js` de `@electric-sql/pglite` instalado aparte. La dependencia no se agregó al proyecto. Si falta, esa prueba se marca omitida explícitamente. Cambiar un archivo remoto requiere actualizar hash, bytes y versión; de lo contrario se rechazará su envío por integridad.

Documentación oficial consultada: [adjuntos de Chatwoot](https://developers.chatwoot.com/api-reference/messages/create-new-message) y [vínculos de items en Code](https://docs.n8n.io/data/data-mapping/data-item-linking/item-linking-code-node/). El resumen del lote usa la salida `done` del loop; la advertencia heurística del validador sobre ese nodo es esperada.
