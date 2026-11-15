Envía fotos y videos comerciales de F7 a la conversación actual de WhatsApp, sin pie de foto ni texto adjunto. Usá esta herramienta cuando el cliente pida ver un producto, fotos, videos, diseños, colores, calidad o comparación, o cuando el recorrido comercial indique mostrar las opciones aplicables después de definir modalidad. No consulta precios, medidas, stock ni realiza derivación humana.

Único argumento del modelo: `solicitudes`, un ARRAY JSON (no string, no objeto contenedor). Cada elemento tiene `producto`, `contenido` y, si corresponde, `formato`, `disenos`, `reenvio_solicitado`.

COMPARACIÓN: exige DOS solicitudes en la misma llamada, una de fundas y otra de tipo tapizado, las dos con contenido comparacion. Si pide video, ambas llevan formato video. Mandar solo fundas/comparacion es entrada_invalida. Antes de invocar, comprobá que el array tenga las dos categorías.

- producto: `fundas`, `tipo tapizado`, `alfombra`, `cubrevolante`. Usá estos nombres exactos; cubrevolante es singular. No existe producto `todos`.
- El enum `fundas` significa exclusivamente fundas a medida. Una mención genérica del cliente a «fundas» no elige esa categoría: resolvé si quiere conocer ambas alternativas o una concreta, usando el contexto o una aclaración breve.
- contenido: `presentacion`, `disenos`, `colores`, `calidad`, `comparacion`.
- formato opcional: `auto` (por defecto), `foto` o `video`. Respetá un formato expresamente solicitado. Si pidió solo fotos y no existen, no mandes un video como reemplazo.
- disenos opcional: solo para contenido `disenos`, array con `baston`, `vip`, `hexagonal`, `diamante`, `ultra`. Omitilo para mostrar todos los diseños del producto. No pases nombres de colores como diseños.
- reenvio_solicitado opcional: true solo si pidió explícitamente volver a ver material. No fuerza reenvío de un mismo pedido ni elimina la protección de duplicados.

Reuní TODOS los productos y contenidos solicitados en UNA llamada por turno. Máximo 16 solicitudes. No mandes un producto que el cliente excluyó. «Todos» se resuelve por contexto: todos los diseños de fundas no son todos los productos. Si el referente es ambiguo, aclaralo antes. Si pide los cuatro productos principales, enumeralos. Tapicería y cobertores no están disponibles en esta herramienta; no inventes un producto o uses otro para representarlos.

Ejemplos de solicitudes:
Solo fundas a medida: [{"producto":"fundas","contenido":"presentacion"}].
Solo tipo tapizado: [{"producto":"tipo tapizado","contenido":"presentacion"}].
Fundas y cubrevolante: [{"producto":"fundas","contenido":"presentacion"},{"producto":"cubrevolante","contenido":"presentacion"}].
Los cuatro: [{"producto":"fundas","contenido":"presentacion"},{"producto":"tipo tapizado","contenido":"presentacion"},{"producto":"alfombra","contenido":"presentacion"},{"producto":"cubrevolante","contenido":"presentacion"}].
Comparar ambas fundas en video: [{"producto":"fundas","contenido":"comparacion","formato":"video"},{"producto":"tipo tapizado","contenido":"comparacion","formato":"video"}]. La comparación necesita ambas categorías. Para mostrar solo una, usá su presentación exclusiva.
Dos diseños de fundas: [{"producto":"fundas","contenido":"disenos","disenos":["baston","ultra"],"formato":"foto"}].
Todos sus diseños: [{"producto":"fundas","contenido":"disenos"}].
Carta de colores de fundas: [{"producto":"fundas","contenido":"colores"}].

El workflow selecciona archivos y evita repetir piezas compartidas. No decidas URLs, IDs de archivo, destinatario, cuenta, modo ni identificador del pedido: esos campos los fija el flujo. Mostrar un video o una foto nunca confirma compatibilidad, disponibilidad, diseño elegido ni precio.

Esperá el resultado y mirá el detalle por solicitud. `aceptados` confirma mensajes creados, no entrega/lectura; `omitidos` ya estaban aceptados en ese pedido; `simulados` no hizo envíos. Ante `faltantes` o `fallidos`, informá la parte que no se pudo compartir sin negar los aceptados. Ante `desconocidos`, no asegures éxito/fracaso y no reintentes. Ante `control_humano`, detené la atención automática. No repitas la herramienta para sortear un error o límite de tiempo. No reproduzcas títulos internos como pies de foto o mensajes separados.
