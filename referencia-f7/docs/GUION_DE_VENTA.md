# Guion de venta F7 — versión canónica para validar con el dueño

**Estado: BORRADOR PARA VALIDACIÓN.** Reconstruido el 2026-09-07 leyendo el prompt vivo del agente (`src/agent/clasificar_y_ensamblar.js`), las 5 herramientas y el Memory Manager tal como están en n8n. No es lo que el dueño *quiere* sino lo que el sistema *hace hoy*, con cada frase textual y quién la manda (AGENTE = el LLM; FOTOS/PRECIOS/HUMANO/COMBO/MM = una herramienta o el Memory Manager).

Cómo usarlo:
- Sección 5 es el resumen de la secuencia single (leer primero).
- Sección 2 es la tabla de frases obligatorias F1-F51: marcar cada una como OK / cambiar / eliminar.
- Sección 3 lista 30 divergencias entre lo que dice el prompt y lo que hacen las herramientas: cada una necesita una decisión (las más importantes están en `docs/DECISIONES_PENDIENTES.md`).
- Sección 4 son 27 preguntas concretas sin respuesta en el prompt.
- Sección 1 es el árbol de decisión completo por paso.

Convenciones: [HV] = verificado en el JSON vivo; [INF] = inferencia por lectura estática; [CW] = mensaje por Chatwoot; [WA] = media por WhatsApp Cloud API. Regla del proyecto: **ninguna frase, orden de pregunta o bifurcación de este documento se modifica en n8n sin aprobación del dueño.**

---

Fecha: 2026-09-07. Fuente de verdad: snapshot vivo de n8n bajado hoy (`scratchpad/live/*.json`), en particular:
- `Agente_de_ventas_V2.10.json` (id `WkimZVkuhISAHoAbfH7DS`, updatedAt 2026-06-11) → prompt vivo extraído en `analysis/clasificar_y_ensamblar_LIVE.js`, contexto dinámico en `analysis/preparar_estado_LIVE.js`, tools en `analysis/agente_tools_LIVE.md`.
- `Herramienta_precios.json` (175 nodos), `Herramienta_fotos.json` (139), `Herramienta_humano.json` (32), `Registrar_Intencion_F7.json` (6), `Cotizar_Combo_F7.json` (15), `Memory_Manager_F7_v3.json` (26), `Log_Mensaje.json`, `Cleanup_Pendientes_F7.json`.
- Informes previos R1–R9 (misma carpeta). Todos los textos entre comillas de este documento fueron re-verificados hoy contra los nodos vivos con Node (no contra los .md del proyecto).

Convenciones:
- **[HV]** hecho verificado (texto literal de un nodo o bloque del prompt). **[INF]** inferencia sobre comportamiento en runtime (la API de n8n devuelve 0 ejecuciones; nada se ejecutó).
- **AGENTE** = mensaje escrito por el LLM (Claude Haiku 4.5) y enviado por el nodo `1ª Parte Respuesta1` del Agente (POST Chatwoot). **PRECIOS / FOTOS / HUMANO / COMBO / MM** = mensaje enviado por esa herramienta o por el Memory Manager por su cuenta, sin pasar por el LLM.
- **[CW]** = enviado por API de Chatwoot (`POST /conversations/{id}/messages`, `message_type: outgoing`; queda en la bandeja del operador). **[WA]** = enviado por WhatsApp Cloud API directo (Graph v19.0; **no queda en la bandeja de Chatwoot** [INF], solo en `conversation_log`).
- "Estado" = fila de `session_state` (clave = teléfono): `producto_vigente`, `modelo_vehiculo`, `contenido_visto` (CSV), `productos_cotizados` (CSV), `productos_pendientes` (CSV, TTL 1 h), `updated_at`. "Memoria" = `n8n_chat_histories` (ventana de 30 mensajes que ve el LLM).

### Regla de lectura crítica sobre lo que dice el AGENTE [HV]
El nodo `devuelve outputs` del Agente, ANTES de enviar, hace sobre la respuesta del LLM: quita todas las `"`, quita todos los `¿`, parte el texto por `.` en N mensajes (uno cada 2 s, nodo `Wait1` amount 2) y **elimina TODOS los puntos** (incluidos los de miles: `$72.500` → `$72500`; `ej.` → `ej`; una URL con puntos se destruye). Consecuencia: **ninguna frase "textual" del prompt llega al cliente tal cual si contiene `¿` o `.`**. En este documento, cuando una frase del prompt tiene `¿` o `.`, anoto "llega como: …" con lo que el cliente recibe realmente. Los mensajes de las HERRAMIENTAS no pasan por ese nodo y llegan íntegros.

---

## 0. Mapa de un turno (infraestructura que condiciona el guion)

1. Chatwoot → webhook `POST /memory-manager-f7` (MM). Filtros: `event == message_created`, `body.content` no vacío, `message_type == incoming`, IF `Verificar Label Humano`. [HV]
   - **[HV lectura estática / INF runtime]** `Verificar Label Humano` evalúa `($json.conversation.labels || []).includes('humano')`, pero en ese punto `$json` es el item del webhook (`{headers, params, query, body}`; los nodos vecinos leen `$json.body.event`, `$json.body.content`). `$json.conversation` es `undefined` → siempre `false` → **el bot NUNCA se silencia por el label `humano`**. Es decir: después de cualquier derivación a humano, el agente sigue respondiendo al cliente en paralelo con el equipo. Esto atraviesa todo el guion (ver §2.15 y Divergencia D1).
   - Audios: `Tiene contenido?` exige `body.content` no vacío; un audio de WhatsApp llega con `content: null` → se descarta antes de la rama Whisper [INF fuerte, R6 §3.1].
2. Buffer Redis por teléfono: el lote se cierra ~15–21 s después del PRIMER mensaje del lote (no por silencio) [HV+INF]. Los mensajes del lote se concatenan con `\n` y van como UN solo `texto` al agente.
3. **Saludo inicial (MM)**: si `COUNT(human en n8n_chat_histories) == 0` → `Wait` 7 s → **MM [CW]: "Hola, te comunicaste con F7-Automotriz"** → y DESPUÉS ejecuta el agente igual (el agente responde al texto del cliente en el mismo turno; el prompt le prohíbe saludar: "Nunca saludes (nada de 'Hola', 'Buen dia', 'Buenas')"). El saludo no se guarda en memoria ni en `conversation_log`. [HV]
4. Agente: `Guardar Human` (inserta el turno humano) → `Leer Estado` → `Preparar Estado` (contexto dinámico `## DATOS CONFIRMADOS DE ESTA SESION` + `## MULTI-PRODUCTO ACTIVO`) → `Clasificar y Ensamblar` (elige 1 de 16 fases; solo carga los bloques de esa fase; ver tabla en R1 §2.4) → AI Agent (Haiku 4.5, memoria 30 msgs, 5 tools) → `devuelve outputs` → N POST a Chatwoot (2 s entre cada uno) → `Borrar Human Duplicado`. [HV]
5. Herramientas: cada una envía sus mensajes al cliente por su cuenta, escribe en `session_state`, inserta filas `ai` en la memoria (precios y fotos; humano/combo/registrar NO) y devuelve un string `output` al LLM, que decide la frase corta final según el mapeo del prompt. [HV]

---

## 1. Árbol de decisión completo

Formato de cada nodo: **(a)** cliente · **(b)** agente (acción/tool) · **(c)** mensajes que recibe el cliente y QUIÉN los manda (texto exacto) · **(d)** qué queda registrado · **(e)** siguiente paso.

### 1.0 Primer contacto

**N0 — Cualquier primer mensaje de un teléfono nuevo** [HV]
- (a) Cliente escribe cualquier cosa ("hola", "buenas, precio de fundas", etc.).
- (b) MM detecta primer mensaje → saludo; luego el agente clasifica (`inicio`, porque no hay `producto_vigente`) y aplica Paso 1.
- (c) **MM [CW]: "Hola, te comunicaste con F7-Automotriz"** (≈7 s después de cerrarse el lote). Luego lo que corresponda al Paso 1 (N1.x), ~2 s después.
- (d) Memoria: `human` + `ai`. Estado: nada todavía (la fila de `session_state` la crea la primera tool).
- (e) Paso 1.

### 1.1 Paso 1 — obtener producto + modelo (bloque `paso1`; fases `inicio`, `cambio_producto`, `multi_producto_inicio`)

**N1.1 — Faltan AMBOS** (ej. "hola", "buenas", "precio", "cuanto sale", "cotizacion", "presupuesto") [HV]
- (b) Ninguna tool. Regla anti-asunción: "precio"/"cuanto sale" NO implica producto ("NUNCA asumir que 'precio' = fundas").
- (c) **AGENTE**: "¿Te interesa algun articulo en especial o quisieras conocer cuales son nuestros productos?" → llega como: `Te interesa algun articulo en especial o quisieras conocer cuales son nuestros productos?`
- (d) Memoria. Estado: sin cambios.
- (e) N1.2 / N1.3 / N1.4 según responda.

**N1.2 — Cliente pregunta qué venden** ("que venden?", "que productos tienen?", o responde "quiero conocer los productos") [HV]
- (c) **AGENTE**: "Ofrecemos fundas a medida, fundas tipo tapizado, alfombras termoformadas y cubrevolantes para vehiculos. ¿Cual te interesa mas?" → llega como 2 mensajes: `Ofrecemos fundas a medida, fundas tipo tapizado, alfombras termoformadas y cubrevolantes para vehiculos` / `Cual te interesa mas?`
- (e) ESPERAR elección → N1.4 o N1.5.
- Nota [HV]: es la ÚNICA situación en que el prompt permite listar productos ("Nunca listes productos si no te lo pidieron").

**N1.3 — Tiene modelo, falta producto** ("tengo un corolla", "es para mi hilux") [HV]
- (c) **AGENTE**: "¿Que producto buscas para tu {modelo}?" → llega como `Que producto buscas para tu Corolla?`
- (e) N1.4.

**N1.4 — Tiene producto, falta modelo** ("quiero fundas", "alfombras", "cubrevolante", "precio de fundas") [HV]
- (b) Mapeo de producto (bloque `base` "Estado 1"): "fundas/funda/funda a medida/quiero fundas/las fundas" → fundas a medida ("FUNDAS = FUNDAS A MEDIDA. SIEMPRE"; PROHIBIDO preguntar tipo de funda u ofrecer dos opciones); "tapizado/tipo tapizado/fundas tipo tapizado" y "las otras fundas/la otra opcion de fundas" → tipo tapizado; "alfombras/alfombra" → alfombra; "cubrevolante/cubrevolantes/cubre volante/volante" → cubrevolantes. "Para cubrevolantes tambien se necesita modelo de vehiculo."
- (c) **AGENTE**: "¿Que modelo de vehiculo buscas proteger y renovar?" → llega como `Que modelo de vehiculo buscas proteger y renovar?` (única pregunta permitida para pedir modelo).
- (d) Estado: sin cambios (ninguna tool corrió). El "producto vigente" existe solo en el historial del LLM hasta que corra fotos/precios [HV: `producto_vigente` lo escribe `upsert_session_state` desde las tools].
- (e) Cliente da modelo → N1.6 (o N1.5 si da solo marca).
- Contradicción interna [HV]: `errores` #25 dice "PROHIBIDO responder con texto al cliente cuando menciona cubrevolante si no ejecutaste una herramienta en ese turno", pero sin modelo la única acción es esta pregunta de texto. Ver Ambigüedad A4.

**N1.5 — Cliente dice solo una MARCA** ("toyota", "ford") [HV]
- (b) Lista de 25 marcas en `base`: Toyota, Renault, Ford, Chevrolet, Fiat, Volkswagen, Peugeot, Citroen, Nissan, Honda, Hyundai, Jeep, Audi, Mercedes, Kia, Mitsubishi, Suzuki, Subaru, Dodge, Chrysler, Land Rover, Iveco, SsangYong, Cherry, Alfa Romeo. "NUNCA ejecutar fotos ni precios con solo una marca."
- (c) **AGENTE**: "Que modelo de {marca} tenes? (ej: {2-3 modelos populares de esa marca})", ejemplo del prompt: "Que modelo de Toyota tenes? (Corolla, Etios, Hilux, etc)" → llega como `Que modelo de Toyota tenes? (Corolla, Etios, Hilux, etc)`.
- Red de seguridad [HV]: si el LLM igual ejecuta fotos/precios/registrar_intencion con `modelo_vehiculo` igual (exacto, lowercase) a una de esas 25 marcas, la tool NO manda nada al cliente y devuelve al LLM: `ERROR: El cliente dijo la MARCA <marca> pero no especifico el MODELO exacto. Debes preguntar: Que modelo de <marca> tenes? y dar 2-3 ejemplos de modelos de esa marca.` (precios y fotos, nodo `Devolver Error Marca`); registrar_intencion devuelve una variante equivalente. Marcas fuera de la lista (BMW, Volvo, Chery bien escrito, etc.) no se detectan.
- (e) Cliente da modelo → N1.6.

**N1.6 — Tiene producto + modelo (en el mismo mensaje o acumulado)** [HV]
- (b) "REGLA DE ACCION INMEDIATA": ejecutar fotos "sin hacer NINGUNA pregunta intermedia". Excepciones: tipo tapizado (→ precios directo, N3), y butacas (N1.7).
- (e) → Paso 2 del producto: fundas N2.1, alfombra N2.3, cubrevolante N2.4, tipo tapizado N3 (sin Paso 2).

**N1.7 — Fundas a medida + modelo Spin / Kangoo / Master / H1** [HV]
- (a) Cliente: "fundas para mi master".
- (b) Preguntar butacas ANTES de fotos, UNA sola vez. "El flujo es: preguntar butacas → fotos → reaccion del cliente → precios."
- (c) **AGENTE**: "Cuantas butacas tiene tu {modelo}?" → llega como `Cuantas butacas tiene tu Master?`
- (a') Cliente responde cantidad ("9", "7", "5", "2") → (b') fotos(producto="fundas") → N2.1. Al cotizar (N3), el prompt manda pasar `butacas` con ese valor.
- Qué hace PRECIOS con `butacas` [HV]: `Number(butacas) >= 7` → precio 7 asientos y texto "(7 asientos)"; `== 2` → rama "2 fundas individuales" que **nunca se activa** porque la query SQL no selecciona `price_2ind_*` (código muerto) → cotiza juego completo 5 plazas; cualquier otro valor (5, 9 sin precio 7, vacío) → 5 plazas. Alfombra/TT/CV ignoran `butacas`.
- Contradicción [HV]: la descripción de la tool `precios.butacas` dice "Solo enviar si el cliente tiene 7 o mas butacas y el producto es fundas. Si no aplica o el cliente tiene 5 plazas, enviar string vacio", el prompt manda pasar la cantidad dicha y `butacas="2"` para "fundas individuales/delanteras/solo 2 butacas" (paso3). Ver D8.

### 1.2 Paso 2 — enviar contenido (bloque `paso2_contenido` + mapeo del `base`)

Regla [HV]: si el producto ya está en "Contenido ya visto" → saltar a Paso 3. Si no → fotos DIRECTAMENTE "sin preguntar si quiere ver". El prompt prohíbe cualquier "Te interesa conocer las alfombras?" (bloque `errores`).

Prefijo común de FOTOS para todos los productos [HV]: `Es Marca sin Modelo?` → `Guardar Estado` = `upsert_session_state(telefono, producto, modelo||null)` (escribe `producto_vigente` y `modelo_vehiculo` con lo que llegue, **incluso** `video_calidad`, `discreto`, `personalizado`, `diferenciacion`, `tipo_tapizado`; el cuerpo de la RPC no está en el proyecto [INF sobre el efecto]) → `Leer Contenido Visto` → `Switch Producto` (8 salidas, sin fallback: un valor no reconocido termina sin output).

**N2.1 — Fundas a medida: fotos(producto="fundas", modelo_vehiculo=M)** [HV]
- (c) En este orden:
  1. **FOTOS [CW]** (solo si `contenido_visto` NO contiene `catalogo`): "Cada funda se realiza a medida y por encargo para cada butaca, el material que utilizamos es cuero automotor."
  2. **FOTOS [WA texto]**: "Aca te dejo el catalogo con los diseños"
  3. **FOTOS [WA texto]**: "https://wa.me/c/5491156013327" (link al catálogo de WhatsApp Business)
  4. **FOTOS [WA imagen]** (Drive `1Gj8nftQ…`, se descarga y sube en cada llamada) con caption "cualquiera de los diseños se pueden confecionar con los colores y logos de esta imagen" (sic, "confecionar")
  5. **AGENTE**: "¿Hay algún diseño que te haya gustado o quisieras que te ayude a elegir?" → llega como `Hay algún diseño que te haya gustado o quisieras que te ayude a elegir?`
- (d) Memoria (`ai`): "Aca te dejo el catalogo con los diseños para que elijas el que mas te gusta" (≠ texto enviado), "https://wa.me/c/5491156013327", "[CONTENIDO VISTO: catalogo]". Estado: `producto_vigente=fundas`, `modelo_vehiculo=M`, `contenido_visto += catalogo`. Output al LLM: "El catalogo de diseños de fundas a medida fue enviado al cliente".
- (e) N2.5 (reacción) / N2.6 (asesoramiento).

**N2.2 — Tipo tapizado: NO tiene Paso 2** [HV]: "TIPO TAPIZADO NO TIENE PASO 2. Si el producto vigente es tipo tapizado y tenes modelo → ejecutar precios directamente con metodo_pago vacio." → N3.3. (El catálogo de tipo tapizado se manda recién DESPUÉS de cotizar, si el cliente elige "conocer los diseños": N4.2.)

**N2.3 — Alfombras: fotos(producto="alfombra", modelo_vehiculo=M)** [HV]
- (c) En este orden:
  1. **FOTOS [CW]** (solo si no vio `alfombra`): "Las alfombras termoformadas cubren por completo el piso de tu vehículo, evitando derrames o futuros daños. Vienen para cubrir el piso delantero y trasero"
  2. **FOTOS [WA video]** intro (Drive `1Anu4zb…`, sin cache) caption "Estas son las alfombras"
  3. **FOTOS [WA video]** principal (Drive `1GGQ-YUM…`, cacheado 30 días en `wa_media_cache`) caption "asi quedan colocadas"
  4. **AGENTE**: "¿Te gustaria encargar las alfombras en transferencia o aprovechar las 3 cuotas sin interes?" → llega como `Te gustaria encargar las alfombras en transferencia o aprovechar las 3 cuotas sin interes?`
- (d) Memoria: "[CONTENIDO VISTO: alfombra]". Estado: `producto_vigente=alfombra`, `contenido_visto += alfombra`. Output: "Los videos de alfombras termoformadas fueron enviados al cliente".
- (e) N2.5. Atención: la frase del agente ya pregunta método de pago ANTES de cotizar (ver D4).

**N2.4 — Cubrevolante: fotos(producto="cubrevolantes", modelo_vehiculo=M)** [HV]
- (c) En este orden:
  1. **FOTOS [CW]** (solo si no vio `cubrevolante`): "El cubre volante cosido a mano incluye su colocación, la cual dura 45 minutos aprox con turno previo en CABA y Bariloche. También realizamos envíos a todo el país"
  2. **FOTOS [WA video]** (Drive `1NTU8i1f…`, cacheado) sin caption
  3. **AGENTE** (según prompt): "Te gustaria encargar tu cubrevolante mediante transferencia o aprovechar las 3 cuotas sin interes?"
- (d) Memoria: "[CONTENIDO VISTO: cubrevolante]". Estado: `producto_vigente` = lo que mandó el LLM (`cubrevolantes`, plural, según el enum de la tool), `contenido_visto += cubrevolante` (singular). Output REAL: **"El video de cubrevolante fue enviado al cliente"**.
- Divergencia [HV]: el prompt mapea la frase obligatoria al output "El video de **cubrevolantes** fue enviado al cliente" (plural). No hay match exacto → la frase (3) queda a criterio del LLM (D2). Además el clasificador exige `cubrevolantes` en `contenido_visto` y la tool escribe `cubrevolante` → la fase determinística queda en `enviar_contenido` para siempre mientras el vigente sea cubrevolantes (D3).
- (e) N2.5.

**N2.5 — Reacción al contenido (bloque `reaccion_contenido`, fase `reaccion_contenido`)** [HV]
- (a) SEÑALES DE COTIZACIÓN / AVANCE: elige diseño ("me gusta el negro", "el primero", "ese esta bueno"), pide precio ("cuanto sale?", "precio?", "pasame el valor"), avance ("lo quiero", "vamos con ese", "quiero avanzar"), positiva ("estan lindos", "me gustan", "esta bueno", "quiero ese") → (b) precios con `metodo_pago` vacío ("NO preguntar si quiere cotizacion") → N3.
- (a) Pide ayuda ("ayudame", "que me recomendas", "no se cual elegir") → N2.6.
- (a) SEÑALES DE CONSULTA ("tenes en otro color?", "como es la colocacion?", "como es el tema del envio?", "cuanto tarda?") → (b) responder sin precios. Nota [HV]: en fase `reaccion_contenido` NO se carga el bloque `faq`; solo si el texto matchea la regex FAQ del clasificador (material|tela|cuero|atras|trasera|tardan|demoran|instala|airbag|factura|cuotas.*tarjeta|stock|inmediata|encarg.*abono|colocacion.*ustedes|seña.*ir|como funciona|como es el proceso|tener que ir) va a `consulta_faq` con los datos del negocio. "envio", "garantia", "color", "direccion", "horario" NO están en la regex → el LLM responde sin el bloque faq (riesgo de inventar, prohibido por `errores` #22).
- (a) SEÑALES NEGATIVAS ("no me gustan", "ninguno", "paso") → N10 (negaciones; el clasificador rutea por regex `^(no|paso|nada|ninguno|...)`).
- (a) "las dos"/"ambas": si es VER ambos tipos de fundas → fotos(diferenciacion) (N2.7); VER productos distintos → fotos de cada uno; PRECIO de 2+ → "Cotizacion de multiples productos" (ver §1.14, régimen A vs B); ambiguo → VER.
- (a) Cambio de producto ("y alfombras?") → N11.
- Butacas (Spin/Kangoo/Master/H1): se preguntó una sola vez al inicio; no repetir.

**N2.6 — Asesoramiento de diseño (fundas a medida y tipo tapizado)** [HV, bloque `base`]
- (a) "ayudame", "que me recomendas", "no se cual elegir", "cual me recomendas".
- (c) **AGENTE**: "¿Buscas un diseño discreto o algo que combine con tu modelo de vehiculo?" → llega como `Buscas un diseño discreto o algo que combine con tu modelo de vehiculo?`. ESPERAR.
- Rama DISCRETO: (b) fotos(producto="discreto") → (c) **FOTOS [WA texto]** "Cualquiera de estos diseños pueden ir bien" → **FOTOS [WA imagen]** ×3 sin caption (log interno: "baston grande", "baston chico", "VIP"; la 3ª imagen es el MISMO archivo Drive que la "imagen de colores" `1Gj8nftQ…` [HV]; ver A12) → **FOTOS [WA texto]** "Estos son los modelos baston grande, chico o Vip" → **AGENTE**: "¿Cual de estos te gusta mas?" → llega como `Cual de estos te gusta mas?`. (d) Memoria: "Cualquiera de estos diseños pueden ir bien\nEstos son los modelos baston grande, chico o Vip" (sin marcador). Estado: `contenido_visto += discreto`, `producto_vigente = discreto` [INF por el upsert]. Output: "Las fotos de diseños discretos de fundas fueron enviadas al cliente".
- Rama COMBINAR: (c) **AGENTE**: "¿De que color es tu vehiculo? Contame asi veo que diseños pueden combinar bien" → llega como `De que color es tu vehiculo? Contame asi veo que diseños pueden combinar bien`. Cliente da color → (b) fotos(producto="personalizado") → (c) **FOTOS [WA texto]** "Cualquiera de estos diseños pueden ir bien" → **FOTOS [WA imagen]** ×6 con 1 s entre cada una (las 3 primeras propias; la 4ª y 5ª son las mismas de discreto; la 6ª es la imagen de colores con caption "Podes combinar el logo, las costuras y el vivo de las fundas con el color de tu vehiculo") → **AGENTE**: "¿Hay alguno que te haya gustado?" → llega como `Hay alguno que te haya gustado?`. (d) Memoria "[CONTENIDO VISTO: personalizado]"; Estado `contenido_visto += personalizado`. Output: "Las fotos de diseños personalizados de fundas fueron enviadas al cliente".
- Nota [HV]: FOTOS no usa el color que dijo el cliente (envía siempre las mismas 6 imágenes); el prompt dice "veo que diseños pueden combinar bien". Ver A11.
- Elección de diseño ("baston grande", "vip", "el primero", "el del medio", "me gusta ese") → (b) precios(producto="fundas", modelo del historial, metodo_pago vacío) → N3.1. "NUNCA responder con 'Quisieras encargar tus fundas mediante transferencia o aprovechar las 3 cuotas sin interes?' despues de que el cliente elija un diseno discreto o personalizado."
- Divergencia [HV]: si el producto vigente era tipo tapizado (el asesoramiento aplica a ambos), la elección dispara `precios(producto="fundas")` → cotiza fundas A MEDIDA (el guard de contenido pasa porque `catalogo` es compartido). Ver D16.

**N2.7 — Diferenciación fundas a medida vs tipo tapizado (bloque `diferenciacion`, fase `diferenciacion`)** [HV]
- (a) Triggers: "que diferencia hay entre las fundas", "cual es la diferencia entre fundas a medida y tipo tapizado", "que tipos de fundas tienen", "hay dos tipos de fundas?", "cual es mejor, fundas a medida o tipo tapizado?" (clasificador: regex `diferencia.*(funda|medida|tapizado)|tipos? de funda|mejor.*(medida|tapizado).*(tapizado|medida)|hay dos tipos`, prioridad alta). "NO aplica cuando el cliente simplemente dice 'fundas'."
- (b) fotos(producto="diferenciacion") "INMEDIATAMENTE. Esta es tu UNICA accion posible en este turno."
- (c) **FOTOS [CW]** (SIEMPRE, sin chequear visto): "Te envio un video donde explicamos las diferencias entre fundas a medida y tipo tapizado" → **FOTOS [WA video]** (Drive `192WIGfN…`, cacheado) sin caption → **AGENTE**: "¿Cual se adapta mas a lo que estabas buscando?" → llega como `Cual se adapta mas a lo que estabas buscando?`
- (d) Memoria "[CONTENIDO VISTO: diferenciacion]"; Estado `contenido_visto += diferenciacion` ("NO cuenta como catalogo ni como video de calidad"), `producto_vigente = diferenciacion` [INF por upsert]. Output: "El video de diferenciacion entre fundas a medida y tipo tapizado fue enviado al cliente".
- (a') "cual es mas cara/barata?" → **AGENTE**: "Las dos opciones tienen precios diferentes segun el modelo de tu vehiculo. ¿Cual te interesa conocer primero?" → llega como 2 mensajes: `Las dos opciones tienen precios diferentes segun el modelo de tu vehiculo` / `Cual te interesa conocer primero?`
- (a') Elige tipo tapizado → vigente = tipo tapizado; con modelo → precios (N3.3); sin modelo → "¿Que modelo de vehiculo buscas proteger y renovar?".
- (a') Elige fundas → vigente = fundas; con modelo → fotos(fundas) (N2.1); sin modelo → pregunta modelo y luego fotos.
- Gap [HV]: en fase `diferenciacion` solo se cargan `base + diferenciacion + errores`: si en ese turno cotiza tipo tapizado, la frase post-cotización de N4.2 no está cargada. En `reaccion_contenido` la misma situación tiene OTRA frase textual: "¿Cual de las opciones se adapta a lo que estabas buscando?" (D13).

**N2.8 — "Como quedan / como son / como se ven" (bloque `como_quedan`)** [HV]
- Fundas → fotos(video_calidad) solo si no visto (N4.1 describe qué manda); si ya lo vio → **AGENTE**: "Ya te envie el video de como quedan, ¿te quedo alguna duda?" → llega como `Ya te envie el video de como quedan, te quedo alguna duda?`
- Alfombras → fotos(alfombra) solo si no visto (N2.3). Cubrevolantes → fotos(cubrevolantes) solo si no visto (N2.4). Tipo tapizado → "NO aplica" (sin respuesta definida).
- Sin frase definida si alfombra/cubrevolante ya visto (A14).

### 1.3 Paso 3 — cotizar (bloque `paso3_cotizar`; fases `reaccion_contenido`, `cotizar`)

Reglas [HV]: (1) verificar contenido visto (salvo tipo tapizado) → si no, fotos primero; (2) verificar modelo; (3) `metodo_pago` SIEMPRE vacío salvo pedido explícito ("en efectivo", "transferencia", "en cuotas") o `todos` si pide "todos los metodos de pago"; "NUNCA preguntar metodo de pago antes de cotizar"; "metodo_pago NUNCA se hereda"; (4) fundas individuales → `butacas="2"`; (5) "Para cubrevolantes SE EJECUTA la herramienta precios igual que para alfombras y fundas".

REGLA DE PRECIO EXPLÍCITO [HV, `base`]: "cuanto sale en efectivo?", "cuanto estan en cuotas?", "precio en transferencia?", "y en efectivo?", "y en cuotas?" → precios INMEDIATAMENTE con ese método, "prioridad sobre cualquier otro paso del flujo". No aplica a "precio"/"cuanto sale" genérico.

Guards de PRECIOS antes de cotizar [HV]: `Es Marca sin Modelo?` (ERROR marca, sin mensaje al cliente) → `Guardar Estado` (upsert `producto_vigente`/`modelo`, se ejecuta AUNQUE luego se bloquee) → `Contenido OK?`: fundas requiere `catalogo`, alfombra `alfombra`, cubrevolante `cubrevolante`, tipo tapizado pasa siempre. Si falla → sin mensaje al cliente, output al LLM: `ERROR: El cliente NO vio contenido de <producto>. DEBES ejecutar la herramienta fotos PRIMERO para este producto antes de poder cotizar. NO ejecutes precios hasta que el cliente haya visto el contenido.` (El prompt no tiene mapeo para este error; el LLM debe reaccionar solo.) `Switch` producto: contains "funda" / contains "alfombra" / equals "tipo tapizado" / contains "cubrevolante", sin fallback. `Switch Metodo Pago`: "" / transferencia / efectivo / cuotas / todos, sin fallback ("credito", "tarjeta" → nada, sin mensaje ni output [INF]).

Tabla producto × método → mensajes que manda **PRECIOS [CW]** (T = precio transferencia, E = efectivo, M = modelo tal como lo mandó el LLM; valores crudos de DB sin separador de miles salvo cubrevolante que usa `toLocaleString('es-AR')`) [HV, nodos `EF *`]:

| Producto | `metodo_pago` = "" (3 mensajes, 2 s entre cada uno) | transferencia | efectivo | cuotas | todos |
|---|---|---|---|---|---|
| **Fundas a medida** | 1) "El juego completo de fundas en cuero automotor y a medida tiene un valor de $T encargando tu trabajo con una seña en transferencia y el restante en su colocacion (abonas en dos partes)" (7+ butacas: mismo texto con T7) 2) "Tambien podes abonar en 3 cuotas sin interes los dias miercoles y sabado" 3) "En efectivo tenes un precio promocional (disponible solo colocando en CABA)" | "El valor del juego completo de fundas en cuero automotor y a medida para M es de $T en transferencia" (7+: "... para M (7 asientos) es de $T7 en transferencia") | "El valor del juego completo de fundas en cuero automotor y a medida para M es de $E en efectivo" | "El juego completo de fundas en cuero automotor y a medida para M se puede abonar en 3 cuotas sin interes de $round(T/3)" | "Las fundas a medida para M tienen un valor de $E en efectivo, $T en transferencia o 3 cuotas sin interes de $round(T/3)" |
| **Tipo tapizado** | 1) "Las fundas tipo tapizado en cuero automotor tienen un valor de $T encargando tu trabajo con una seña en transferencia y el restante en su colocacion (abonas en dos partes)" 2) y 3) idénticos | "El valor de las fundas tipo tapizado en cuero automotor para M es de $T en transferencia" | "El valor de las fundas tipo tapizado en cuero automotor para M es de $E en efectivo" | "El valor de las fundas tipo tapizado en cuero automotor para M se pueden abonar en 3 cuotas sin interés de $round(T/3)" | "Las fundas tipo tapizado para M tienen un valor de $E en efectivo, $T en transferencia o 3 cuotas sin interes de $round(T/3)" |
| **Alfombras** | 1) "Las alfombras termoformadas tienen un valor de $T encargando tu trabajo con una seña en transferencia y el restante en su colocacion (abonas en dos partes)" 2) y 3) idénticos | "El valor de las alfombras para M es de $T en transferencia" | "El valor de las alfombras para M es de $E en efectivo" | "Las alfombras para M se pueden abonar en 3 cuotas sin interés de $round(T/3)" | "Las alfombras para M tienen un valor de $E en efectivo, $T en transferencia o 3 cuotas sin interes de $round(T/3)" |
| **Cubrevolante** (precio fijo de `precios_fijos`, no usa modelo) | 1) "El cubre volante tiene un valor de $T encargando tu trabajo con una sena en transferencia y el restante en su colocacion (abonas en dos partes)" 2) y 3) idénticos | "El cubre volante tiene un valor de $T en transferencia, con colocacion incluida" | "El cubre volante tiene un valor de $E en efectivo (solo en CABA), con colocacion incluida" | "El cubre volante se puede abonar en 3 cuotas sin interes de $round(T/3), con colocacion incluida" | "El cubre volante tiene un valor de $E en efectivo (solo en CABA), $T en transferencia o 3 cuotas sin interes de $round(T/3), con colocacion incluida" |

Output al LLM [HV]: "La cotizacion ya fue enviada" (16 ramas) / "todos los metodos de pago fueron enviados" (4 ramas). Registro [HV]: memoria `ai` con el texto enviado (en "" los 3 mensajes unidos en una sola fila); Estado `productos_cotizados += fundas | tipo tapizado | alfombra | cubrevolante` (solo tras HTTP exitoso); `conversation_log`.

**Sin match** (query fuzzy devuelve una fila sin `brand`/`marca`) [HV]:
- Fundas: **PRECIOS [CW]** "Lamentablemente no contamos con las medidas de tu vehiculo para cotizarte las fundas a medida" → output "no contamos con las medidas de fundas a medida para este vehiculo".
- Alfombras: **PRECIOS [CW]** "Lamentablemente no contamos con las medidas de tu vehiculo para cotizarte las alfombras" → output "no contamos con las medidas de alfombras para este vehiculo".
- Tipo tapizado: **PRECIOS [CW]** "No contamos con las medidas de tu vehiculo para cotizarte las fundas tipo tapizado" → output "no contamos con las medidas de tipo tapizado para este vehiculo".
- Cubrevolante: no existe rama sin match.
- NO se marca como cotizado. [INF] Si la query devuelve 0 filas (caso más probable cuando no hay parecido), el IF `Tiene match *` no recibe items y la tool termina SIN mensaje y SIN output → el LLM recibe vacío y el prompt no tiene regla para eso (A15).
- Importante [HV]: la columna `fundas_a_medida.medidas` se selecciona pero NO se usa → un modelo con fila pero `medidas=false` recibe precio igual (la cadena "Sin Medidas Fundas" del Sprint 2 no está en el vivo).

Nodos del árbol:

**N3.1 — Fundas a medida** → precios(producto="fundas", M, metodo_pago, butacas) → mensajes de la tabla → N4.1.
**N3.2 — Alfombras** → precios(producto="alfombra") → N4.3.
**N3.3 — Tipo tapizado** (directo desde Paso 1, sin contenido) → precios(producto="tipo tapizado") → N4.2.
**N3.4 — Cubrevolante** → precios(producto="cubrevolante") → N4.3. Contradicción [HV]: la descripción viva de la tool dice "NUNCA ejecutar para cubrevolantes (precio fijo $72.500)" y su enum es "fundas / tipo tapizado / alfombra"; el prompt (`paso3`, `errores` #24 "El cubrevolante NO tiene precio fijo en el prompt... Si 'recordas' un precio (72500, 60000, 72600) ESO ES ERROR", #25) ordena lo contrario; el workflow SÍ cotiza cubrevolante (D5).
**N3.5 — Precio pedido antes de ver contenido** ("cuanto salen las fundas para el corolla?" sin catálogo visto) → REGLA ABSOLUTA: fotos primero (N2.x), y en el turno siguiente, ante señal de precio, precios. Si el LLM igual llama precios → ERROR sin contenido (sin mensaje al cliente). INSISTENCIA (pide precio del mismo producto 2ª vez consecutiva sin querer ver contenido): el prompt la define pero no dice qué hacer; la tool bloquea igual (A5).

### 1.4 Paso 4 — cierre según output de precios (bloque `paso4_cierre`)

**N4.1 — Fundas a medida cotizadas** (output "La cotizacion ya fue enviada", vigente fundas) [HV]
- Si `video_calidad` NO visto → **AGENTE**: "Te gustaria conocer la calidad de las fundas en nuestro punto de venta o mediante un video?" ("ESTA PREGUNTA ES OBLIGATORIA... NUNCA saltarla. NUNCA responder con 'Que te queda mas comodo?' en este caso.")
  - Elige VIDEO → (b) fotos(producto="video_calidad") → (c) **FOTOS [WA video]** 1 (Drive `1hHxM9VD…`, sin caption) → **FOTOS [WA video]** 2 (Drive `1rNsh1N5…`, caption "Asi quedan en las butacas de atras") → **AGENTE**: "Quisieras encargar tus fundas mediante transferencia o aprovechar las 3 cuotas sin interes?" (en `base` la misma frase lleva "¿" inicial; da igual: `devuelve outputs` lo quita). (d) Memoria "[VIDEO CALIDAD FUNDAS ENVIADO]"; Estado `contenido_visto += video_calidad`, `producto_vigente = video_calidad` [INF por upsert]. Output: "El video de calidad de fundas a medida fue enviado al cliente".
  - Elige PUNTO DE VENTA → **AGENTE**: "La direccion es Av Olivera 1265, CABA. Te esperamos de lunes a viernes de 9 a 18 hs y sabados de 9 a 14 hs." → llega como 2 mensajes: `La direccion es Av Olivera 1265, CABA` / `Te esperamos de lunes a viernes de 9 a 18 hs y sabados de 9 a 14 hs`. NO se deriva a humano(turno) (a diferencia de "sin medidas").
- Si `video_calidad` YA visto → **AGENTE**: "Que te queda mas comodo?"
- (e) N5 (cierre) / N6 (método de pago) / N10 (negación) / N11 (cambio) / FAQ.

**N4.2 — Tipo tapizado cotizado** [HV]
- **AGENTE**: "¿Te gustaria respetar el diseño original de tus butacas o conocer los diseños disponibles?" → llega como `Te gustaria respetar el diseño original de tus butacas o conocer los diseños disponibles?`
  - DISEÑO ORIGINAL → humano(motivo="butacas_originales") → **HUMANO [CW]**: "Perfecto, enviame una foto de tus butacas originales para chequear si podemos replicar un modelo parecido. Una persona de nuestro equipo se contactará con vos para analizar la imagen y contarte las posibilidades" + labels `humano`, `butacas`. Agente: nada más ("NO escribir ningun mensaje").
  - CONOCER DISEÑOS → fotos(producto="tipo_tapizado") → (c) **FOTOS [CW]** (solo si no vio `catalogo`; si ya vio el catálogo de fundas a medida, esta descripción NO sale): "Las fundas tipo tapizado son en cuero automotor por delante y por detrás. Las mismas quedan como si fuese un tapizado original y podemos respetar el diseño de costura de tus butacas originales" → **FOTOS [WA texto]** "Aca te dejo el catalogo con los diseños" → **FOTOS [WA texto]** "https://wa.me/c/5491156013327" → **FOTOS [WA imagen]** colores (mismo caption que fundas) → **AGENTE**: "¿Hay algún diseño que te haya gustado o quisieras que te ayude a elegir?". Output: "El catalogo de diseños de tipo tapizado fue enviado al cliente". Estado: `contenido_visto += catalogo`, `producto_vigente = tipo_tapizado` (guion bajo) [INF por upsert] — distinto de `tipo tapizado` (espacio) que usan precios y el clasificador (D3/D17).
  - Después: elige diseño → N2.6 elección → precios(producto="fundas") (¡fundas a medida!, D16) / asesoramiento N2.6.
- Nota de fase [HV]: desde `inicio` (turno donde el cliente dice "tipo tapizado para corolla") se cargan `base, paso1, paso2_contenido, cambio_producto, errores`, sin `paso4_cierre`: la frase "¿Te gustaria respetar el diseño original...?" no está disponible en ese turno (A16).

**N4.3 — Alfombras o cubrevolante cotizados** → **AGENTE**: "Que te queda mas comodo?" [HV]. Se dice aunque el cliente haya pedido un método explícito ("y en efectivo?" → precios(efectivo) → "El valor de las alfombras para M es de $E en efectivo" → "Que te queda mas comodo?"), ver D9.

**N4.4 — `metodo_pago="todos"`** (output "todos los metodos de pago fueron enviados") → **AGENTE**: "Cual te queda mas comodo?" [HV].

**N4.5 — Sin medidas** (output "no contamos con las medidas...") [HV]: "IMPORTANTE: la herramienta YA envio el mensaje al cliente. NO repetir ese mensaje."
- Tipo tapizado → **AGENTE**: "De todas formas podes acercarte hasta nuestra sucursal en CABA para que tomemos las medidas de tus butacas o si no ir por la opcion de Fundas a medida, tambien estan hechas en cuero automotor y son de facil colocacion. ¿Tenes la posibilidad de acercarte al taller o preferis conocer los diseños de fundas a medida?" → llega como 2 mensajes: `De todas formas podes acercarte hasta nuestra sucursal en CABA para que tomemos las medidas de tus butacas o si no ir por la opcion de Fundas a medida, tambien estan hechas en cuero automotor y son de facil colocacion` / `Tenes la posibilidad de acercarte al taller o preferis conocer los diseños de fundas a medida?`
  - ACERCARSE → humano(motivo="turno") → **HUMANO [CW]**: "En la brevedad un asistente del equipo se va a contactar con usted para coordinar la visita" + labels `humano`, `turno`.
  - FUNDAS A MEDIDA → vigente = fundas → fotos(fundas) (N2.1).
- Alfombras o fundas a medida → **AGENTE**: "Podes acercarte al taller en CABA para tomar las medidas? O quisieras conocer los demas productos?" ESPERAR.
  - ACERCARSE → humano(turno) (mismo mensaje).
  - CONOCER DEMÁS → "ofrecer los productos que NO haya visto aun. Seguir el flujo normal del producto que elija" (sin frase textual; A6).
- Cubrevolante: sin rama (no puede pasar: precio fijo).
- Residuo huérfano al final del bloque [HV, texto literal]: `FIN de la seccion Sin medidas. → "Te puedo ofrecer fundas a medida, ya viste los diseños. ¿Te gustaria avanzar con las fundas?"` + "Si 'catalogo' aparece en contenido visto pero NO cotizo → precios(producto='fundas'...)" / "Si 'catalogo' NO aparece → fotos(producto='fundas')". Sin condición de entrada; la NOTA previa dice "Ignorar cualquier referencia a 'cambiar producto vigente a fundas automaticamente'" (A7).
- Cliente que recibe todo junto (caso alfombra sin match): **PRECIOS**: "Lamentablemente no contamos con las medidas de tu vehiculo para cotizarte las alfombras" → **AGENTE**: "Podes acercarte al taller en CABA para tomar las medidas? O quisieras conocer los demas productos?".

### 1.5 Métodos de pago como respuesta del cliente (post-cotización)

Los 5 valores que existen [HV]: `""` (sin especificar), `transferencia`, `efectivo`, `cuotas`, `todos`. "Crédito"/"tarjeta" NO existen como valor de la tool (Switch sin fallback → silencio).

**N6.1 — Cliente responde a "Que te queda mas comodo?" / "Quisieras encargar... transferencia o 3 cuotas?" con un método** ("transferencia", "en cuotas", "efectivo") [HV, dos reglas cargadas a la vez]
- Lectura (i) `paso4_cierre`: es "respuesta positiva" / "confirmacion de compra" → humano(motivo="venta") → **HUMANO [CW]**: "Perfecto, en breves un asistente del equipo se contacta con vos para coordinar tu pedido." → fin (el equipo humano pide seña, datos bancarios, nombre, dirección).
- Lectura (ii) REGLA DE PRECIO EXPLÍCITO (`base`): "y en efectivo?" → precios(metodo_pago="efectivo") → **PRECIOS [CW]** "El valor ... es de $E en efectivo" → agente vuelve a N4.x ("Que te queda mas comodo?" / pregunta de calidad). Nada en el prompt resuelve cuál gana (A1). Ambas terminan sin datos bancarios: **ni el prompt ni ninguna herramienta contienen CBU/alias/monto de seña** [HV]; solo FAQ: "Solemos pedir entre un 30% o un 50%, el restante lo abonas al momento de la colocacion o envio".
- Efectivo fuera de CABA: `faq` dice "Si NO es de CABA → ofrecer transferencia o cuotas, NO efectivo", pero PRECIOS ya mandó en la rama "" el msg3 "En efectivo tenes un precio promocional (disponible solo colocando en CABA)" y `errores` #16 prohíbe "Preguntar '¿Podes acercarte a CABA?' cuando el cliente ya eligio metodo de pago".
- Cuotas: FAQ "Las cuotas son unicamente con Visa o Mastercard bancarizadas, 3 cuotas sin interes"; PRECIOS msg2 dice además "los dias miercoles y sabado" (dato que NO está en el prompt). El motivo humano `cuotas` ("cliente quiere pagar todo en cuotas sin sena") existe en la tool pero NINGÚN bloque del prompt lo ordena (A2).
- "todos los medios de pago" → precios(todos) → tabla → "Cual te queda mas comodo?".

### 1.6 Cierre → humano(venta)

**N5 — Señal de cierre single** [HV, `paso4_cierre`]: "lo quiero", "quiero avanzar", "dale", "si", "avanzar con el encargo", "respuesta positiva", "cualquier confirmacion de compra" (tras cotizar).
- (b) humano(motivo="venta") INMEDIATAMENTE. "NO escribir NINGUN mensaje al cliente. NO pedir nombre. NO pedir metodo de pago. NO pedir ningun dato." "PROHIBIDO responder 'Gracias por elegirnos'".
- (c) **HUMANO [CW]**: "Perfecto, en breves un asistente del equipo se contacta con vos para coordinar tu pedido." Labels Chatwoot: `humano` + `venta`. Output al LLM: "La conversacion fue derivada a un agente humano para coordinar la venta. El label venta fue agregado al chat."
- (d) Estado: sin cambios. Memoria: el mensaje de HUMANO **no** se inserta (el LLM no lo ve en turnos siguientes). `conversation_log` sí.
- (e) Según el prompt "La conversacion queda en manos del equipo humano". Según el MM vivo, el bot NO se silencia (§0.1): si el cliente escribe de nuevo, el agente vuelve a clasificar (`post_cotizacion`/`cierre_pedido`) y puede volver a ejecutar humano(venta) → el cliente recibe otra vez "Perfecto, en breves..." (D1).
- Clasificador [HV]: `cierre_pedido` solo si regex `lo quiero|quiero avanzar|avanzar|dale.*encargo|si.*avanz` y producto cotizado; "si"/"dale" solos van a `post_cotizacion`, que igual carga `paso4_cierre`. Ambigüedad "si"/"dale" = aceptación de contenido (`reaccion_contenido`) vs cierre (`paso4_cierre`), ambos cargados en fase `reaccion_contenido` (A3).

### 1.7 Negaciones (bloque `negaciones`; fase `negacion` por regex `^(no|paso|nada|ninguno|no me (gusta|convence|interesa)|no quiero|es caro|muy caro|sale mucho|no conviene)`) [HV]

- Negación al contenido / después del contenido ("no me gustan", "ninguno") → **AGENTE**: "¿Te gustaria conocer los demas productos?" → llega como `Te gustaria conocer los demas productos?`. Si dice "si": la única frase de listado está en `paso1`, que NO se carga en fase `negacion` (solo `base, negaciones, cambio_producto, errores`) y `base` prohíbe listar salvo pregunta explícita (A8).
- Negación después del precio ("es caro", "no conviene", "sale mucho") → frase larga por producto (AGENTE, textual; llegan partidas por el punto interno en 2 mensajes y sin "¿"):
  - Fundas: "Te super entiendo, nosotros no buscamos ser lo mas baratos ya que garantizamos que tus butacas originales queden protegidas y renovadas con un material resistente por un tiempo considerable, sin que corran ni se muevan y te brindamos una garantia de 90 dias a partir de su colocacion. ¿Vos buscabas lo mas barato o quisieras invertir una sola vez para proteger tus butacas?"
  - Tipo tapizado: "Te super entiendo, nosotros no buscamos ser lo mas baratos ya que garantizamos que tus butacas queden como un tapizado original de fabrica, con cuero automotor por delante y por detras, respetando el diseño de costura de tus butacas. Ademas te brindamos una garantia de 90 dias a partir de su colocacion. ¿Vos buscabas lo mas barato o quisieras invertir una sola vez para renovar tu interior?" (3 mensajes)
  - Alfombras: "Te super entiendo, nosotros no buscamos ser lo mas baratos ya que garantizamos que el piso de tu vehiculo quede completamente protegido con alfombras termoformadas de alta resistencia que cubren todo el piso, evitando derrames y daños. Ademas te brindamos una garantia de 90 dias a partir de su colocacion. ¿Vos buscabas lo mas barato o quisieras invertir una sola vez para proteger tu vehiculo?" (3 mensajes)
  - Cubrevolantes: "Te super entiendo, nosotros no buscamos ser lo mas baratos ya que el cubre volante es cosido a mano con colocacion profesional incluida, lo cual garantiza un acabado de calidad que protege y renueva tu volante. Ademas te brindamos una garantia de 90 dias a partir de su colocacion. ¿Vos buscabas lo mas barato o quisieras invertir una sola vez para renovar tu volante?" (3 mensajes)
- Sigue sin querer → "¿Te gustaria conocer los demas productos?". No a todo → **AGENTE**: "Gracias por tu consulta, estoy a tu disposicion para cualquier cosa".
- "Una negacion a un producto NO es negacion a todos." "no" + otro producto en el mismo mensaje → cambio de producto (N11), no negación.
- Falsos positivos del clasificador [HV]: regex sin `\b` → "nosotros...", "nombre...", "nada mas que fundas" caen en `negacion`.

### 1.8 Cambio de producto (bloque `cambio_producto`; fase `cambio_producto` cuando el texto menciona otro producto distinto del vigente) [HV]

- (a) "Y alfombras?", "Tienen fundas?", "Quiero tipo tapizado", "no, mejor cubrevolante".
- (b) "ORDEN DE ACCION, no una consulta. EJECUTAR HERRAMIENTA INMEDIATAMENTE sin hacer NINGUNA pregunta." 1) actualizar vigente; 2) reutilizar modelo del historial; 3) descartar metodo_pago anterior; 4) si ya tiene contenido → Paso 3 (precios); 5) sin contenido y no tapizado → fotos "sin decir NADA"; 6) tipo tapizado → precios.
- (c) Los mensajes del Paso 2 o 3 del nuevo producto (N2.x / tabla de precios). Descripción [CW] de FOTOS solo si ese producto no fue visto.
- (d) `producto_vigente` se actualiza por el upsert de la tool.
- Gap [HV]: fase `cambio_producto` carga `base, cambio_producto, paso1, paso2_contenido, paso4_cierre, errores` — NO `paso3_cotizar` (reglas de butacas/metodo_pago/individuales no disponibles) (A16).
- Clasificador [HV]: `detectarCambioProducto` usa `\b(cubre\s?volantes?|volante)\b`, `\b(tapizado|tipo\s+tapizado)\b`, `\b(fundas?)\b`, `\b(alfombras?)\b`; con vigente `fundas`, "tapizado" → `cambio_producto` salvo que antes matchee la regex de diferenciación.

### 1.9 FAQ e información del negocio (bloque `faq`; fase `consulta_faq` solo si matchea la regex FAQ; también cargado en `multi_producto_activo`) [HV]

Datos: "Direccion: Av Olivera 1265, CABA", "Horarios: Lunes a viernes 9 a 18 hs, sabados 9 a 14 hs", "Google Maps: https://maps.app.goo.gl/Ls5yFbB74rMNJ6n28?g_st=ic" (→ `devuelve outputs` lo destruye: `Google Maps: https://maps` / `app` / `goo` / `gl/Ls5yFbB74rMNJ6n28?g_st=ic`), "Garantia: 90 dias a partir de la colocacion", "Envios a todo el pais. Colocaciones en CABA y Bariloche", "Envio: seña + restante al recibir video del trabajo terminado previo al envio", "Colocacion local: seña + restante en la colocacion", efectivo solo CABA.

Respuestas textuales (AGENTE; anoto cómo llegan cuando se parten):
- "Hacen fundas en tela?" → "Priorizamos cuero automotor ya que es resistente a liquidos y quemaduras, ideal para proteger tus butacas originales"
- "Atras tiene el mismo material?" → "Las fundas llevan cuero automotor por delante y tela elastizada premium en la parte trasera"
- "Cuanto tardan en confeccionar?" → "Aproximadamente 7 dias habiles. Nos contactamos con vos cuando este listo" (2 mensajes)
- "En cuanto tiempo lo instalan?" → "La instalacion se hace en el dia, entre 3 y 4 horas"
- "Son aptos para airbags laterales?" → "Los airbags al activarse rompen el cuero genuino del vehiculo, de la misma manera romperian la costura de las fundas"
- "Hacen facturas?" → "Con credito, cuotas o transferencia emitimos Factura A o B. En efectivo o monotributo emitimos Factura C. Otro tipo de facturacion tiene un 21% adicional" (3 mensajes)
- "Las cuotas son con todas las tarjetas?" → "Las cuotas son unicamente con Visa o Mastercard bancarizadas, 3 cuotas sin interes"
- "Si te hago transferencia para reservar, me queda el valor en efectivo?" → "Si, podes señar por transferencia y abonar el restante en efectivo en la colocacion"
- "Tenes descuento por pagar en efectivo?" (ya se pasó precio efectivo) → "El valor en efectivo es el mencionado, ¿quisieras aprovecharlo?" ; (se pasó transferencia/cuotas) → "Tenemos un valor preferencial en efectivo realizando la colocacion en CABA. ¿Podrias acercarte a nuestro taller?" (2 mensajes; choca con `errores` #16 si "ya eligio metodo")
- "Es el mismo precio en todos los metodos de pago?" → "En efectivo el valor es menor, pero solo aplica si sos de CABA, en transferencia o credito el valor es el que te pase"
- "Tienen stock / colocacion inmediata?" → "Tenemos diseños pre-confeccionados que se adaptan a tu vehiculo"
- "Te puedo encargar y te abono cuando llega?" → "Las fundas se confeccionan a medida por encargo, necesitamos una seña para poder comenzar a trabajar"
- "Hacen ustedes la colocacion?" → "Realizamos colocaciones en nuestro taller de CABA y en Bariloche. Tambien hacemos envios a todo el pais" (2 mensajes)
- "Tendria que ir para alla a dejarte la seña?" → "Aceptamos la reserva por transferencia para poder comenzar a confeccionar"
- "Hay algun combo?" → "Hacemos un redondeo en el precio final cuando se piden varios productos en un mismo pedido abonando en efectivo o transferencia"
- Toda pregunta sobre seña → "Solemos pedir entre un 30% o un 50%, el restante lo abonas al momento de la colocacion o envio" ("NUNCA improvisar otra respuesta sobre seña")
- "Como funciona la compra?" → "Se confeccionan a medida por encargo, tardan aproximadamente 7 dias habiles. Nos contactamos con vos cuando este listo. Realizamos envios a todo el pais, recibis un video del trabajo terminado previo al envio. El sistema es sena + restante al recibir el video. Que te queda mas comodo?" (5 mensajes)

En fase `consulta_faq` solo se cargan `base, faq, errores`: el agente no puede avanzar el flujo (fotos/precios) en ese turno.

### 1.10 Multi-producto / combo (bloques `multi_producto`, `paso4_cierre_combo`; tools `registrar_intencion`, `cotizar_combo`) [HV]

Detección: 2+ productos DISTINTOS en un mismo mensaje entre {fundas, tipo tapizado, alfombras, cubrevolante} (clasificador `contarProductosMencionados`; excepción: solo fundas + tipo tapizado = diferenciación, no combo). Prioridad: fundas > tipo tapizado > alfombra > cubrevolante.

**N12.1 — Turno 1 con modelo** ("precio de fundas y alfombras para Corolla")
- (b) registrar_intencion(productos="fundas,alfombra", modelo_vehiculo="Corolla").
- REGISTRAR: no manda nada al cliente; valida marca-sin-modelo, canoniza por substring, exige ≥2, ordena, llama `registrar_productos_multi` (escribe `productos_pendientes="fundas,alfombra"`, `modelo_vehiculo`, probablemente `producto_vigente=primario` [INF]). Output: "Multi-producto registrado. Producto primario: fundas. Secundarios pendientes: alfombra. SIGUIENTE ACCION: ejecutar fotos(producto=fundas). NO ejecutar fotos de los secundarios. Cuando el cliente reaccione al contenido del primario, ejecutar cotizar_combo (NO ejecutar precios en modo combo)."
- (b') En el MISMO turno, fotos del primario (N2.1) → cliente recibe los mensajes de FOTOS del primario + la frase obligatoria del AGENTE. (Esto son 2 tools en un turno; `base` dice "Maximo UNA herramienta por mensaje".)
- (d) Contexto dinámico del turno siguiente muestra `## MULTI-PRODUCTO ACTIVO` con pendientes/primario/secundarios.
- "NUNCA mencionar los productos secundarios en mensajes al cliente hasta que se cotice."

**N12.2 — Turno 1 sin modelo** ("quiero alfombras y cubrevolantes")
- (b) registrar_intencion(productos="alfombra,cubrevolante", modelo_vehiculo="") → output: "Multi-producto registrado SIN MODELO aun. Productos pendientes: alfombra,cubrevolante. SIGUIENTE ACCION: preguntar al cliente TEXTUAL: \"¿Que modelo de vehiculo buscas proteger y renovar?\". NO ejecutar fotos todavia. ..."
- (c) **AGENTE**: "¿Qué modelo de vehículo buscas proteger y renovar?" (el bloque `multi_producto` la escribe con tildes; la de `base` sin tildes) → llega como `Qué modelo de vehículo buscas proteger y renovar?`
- Turno siguiente: cliente da modelo → re-ejecutar registrar_intencion con EXACTAMENTE los productos pendientes + modelo → fotos del primario. Solo marca → "¿Qué modelo de {marca} tenés? (listar 2-3 modelos populares)". No parece modelo → manejar como FAQ/negación.

**N12.3 — Combo activo, reacción positiva al primario** ("me gusta el baston", "cuanto sale?", "dale")
- (b) cotizar_combo(telefono, conversation_id, metodo_pago ∈ {"", "cuotas", "efectivo"}) — NO precios; NO preguntar calidad/video ni "respetar diseño original" ni "Que te queda mas comodo".
- COMBO: lee `productos_pendientes` (TTL 1 h) y `modelo_vehiculo`; cotiza cada producto (fundas exige `tiene_match && medidas`; siempre 5 plazas); manda **N mensajes [CW]** (uno por producto cotizable), formato según método:
  - `""`: "Fundas a medida $185000" / "Alfombras termoformadas $60000" (etiquetas: "Fundas a medida", "Fundas tipo tapizado", "Alfombras termoformadas", "Cubrevolante"; precio transferencia crudo, sin separador de miles)
  - `cuotas`: "<Label> $<T> en 3 cuotas sin interés de $<floor(T/3)>"
  - `efectivo`: "<Label> $<E> (solo disponible en CABA)"
  - `transferencia`/`todos`: caen en el default (sin sufijo).
  - Si el primario es fundas sin match/sin medidas se agrega al final: "Tenes la posibilidad de acercarte a nuestro taller en CABA para tomar las medidas de tu <modelo>? Son 30 minutos y asi garantizamos un calce perfecto."
  - Si NINGÚN producto cotiza: un solo mensaje "Te paso la cotizacion para tu <modelo>:\n\n<Label>: no contamos con las medidas de tu <modelo>\n<Label>: no contamos con las medidas de tu <modelo>" (+ la invitación al taller si el primario es fundas).
  - Secundarios sin match se OMITEN en silencio.
- (d) `cerrar_combo(telefono, productos_cotizados_exitosos)` → mueve pendientes → cotizados y vacía pendientes [INF]. No inserta en memoria.
- Output y respuesta del AGENTE:
  - "Combo cotizado exitosamente. Se enviaron al cliente N mensajes (uno por producto) con el precio. Responder al cliente UNICAMENTE: \"¿Querrías encargar el combo con una seña en transferencia o aprovechar las 3 cuotas sin interés?\"" → la DESCRIPCIÓN de la tool ordena esa frase; el BLOQUE `multi_producto` ordena en cambio "¿Te gustaría encargar el combo?". Dos frases obligatorias distintas para el mismo evento (D6).
  - "Combo cotizado pero el primario (fundas) no tiene medidas para este modelo. Se envio al cliente mensaje con invitacion a taller. Esperar respuesta del cliente - si acepta ir al taller, ejecutar humano(motivo=\"turno\")." → acepta → humano(turno); no puede → "evaluar con el cliente cambiar el producto primario o cotizar solo los otros" (sin frase).
  - "Combo cotizado pero NINGUN producto tuvo match en base de datos. El cliente recibio el mensaje indicando que faltan medidas. Ofrecer turno en taller o cambiar productos." (sin frase).
  - "ERROR: No hay combo activo (o caducó el TTL de 1h)..." → prompt: reintentar 1 vez; 2 fallos → **AGENTE**: "Perdón, estoy teniendo un problema técnico, un agente te va a atender en breve" + humano(motivo="venta") → **HUMANO [CW]**: "Perfecto, en breves un asistente del equipo se contacta con vos para coordinar tu pedido." (dos mensajes de "disculpa/derivación" seguidos, y motivo venta en un combo; D23).

**N12.4 — Confirmación del combo** ("sí", "dale", "lo quiero", "vamos con eso", "perfecto", "bueno"; clasificador `cierre_combo` si `productos_cotizados >= 2` y afirmación breve exacta, o frase de cierre explícita)
- (b) humano(motivo="combo") ("En combo, el motivo SIEMPRE es 'combo' (no 'venta')").
- (c) **HUMANO [CW]**: "En breves personal del equipo se va a comunicar con vos para brindarte la mejor cotizacion posible" + labels `humano`, `combo`.
- Bug [HV]: `esCierreComboExplicito` incluye `' avanzar '` sin chequeo de negación → "no quiero avanzar" con combo activo/cotizado → `cierre_combo` → humano(combo).

**N12.5 — Cancelar un producto del combo** ("no, sacame las alfombras", "solo quiero fundas") → fase `multi_producto_cancelar` (bloques `base, multi_producto, cambio_producto, errores`). El prompt dice "El sistema limpia pendientes y vuelve a flujo single", pero NINGUNA tool ni nodo lo hace en esa fase (las RPC `limpiar_productos_pendientes`/`remover_producto_pendiente` existen en DB según docs pero no las llama nadie) → los pendientes siguen hasta el TTL de 1 h (`Cleanup` cada 30 min) (D24).

**N12.6 — Agregar producto** ("agregame cubrevolantes también") → registrar_intencion con lista completa.

Régimen contradictorio [HV]: en la misma fase `multi_producto_inicio` se cargan `multi_producto` (combo) y `cambio_producto` cuya sección "Multiples productos en un mismo mensaje" ordena lo opuesto ("Tomar el de MAYOR PRIORIDAD como producto vigente... NUNCA ejecutar precios de multiples productos a la vez. El segundo producto SOLO se retoma cuando el cliente lo menciona EXPLICITAMENTE"); `paso3_cotizar` §"Cotizacion de multiples productos" dice lo mismo (D19).

### 1.11 Derivación a humano — los 5 motivos [HV, `Herramienta_humano.json`]

Switch por `motivo` (igualdad exacta, case-sensitive, sin fallback: un motivo fuera de lista = ni mensaje ni label ni output). Orden interno: mensaje [CW] → Log → GET labels → POST labels (existentes + `humano` + motivo). No toca `session_state` ni memoria. Sin `onError`.

| motivo | Cuándo lo ordena el prompt | Mensaje EXACTO que recibe el cliente (HUMANO [CW]) | Labels | Output al LLM |
|---|---|---|---|---|
| `venta` | señal de cierre single tras cotizar (N5); fallback de errores de combo | "Perfecto, en breves un asistente del equipo se contacta con vos para coordinar tu pedido." | humano, venta | "La conversacion fue derivada a un agente humano para coordinar la venta. El label venta fue agregado al chat." |
| `combo` | confirmación con combo activo/cotizado (N12.4) | "En breves personal del equipo se va a comunicar con vos para brindarte la mejor cotizacion posible" | humano, combo | "La conversacion fue derivada a un agente humano para cotizar combo." |
| `turno` | sin medidas + quiere acercarse (N4.5); combo primario sin medidas + acepta taller | "En la brevedad un asistente del equipo se va a contactar con usted para coordinar la visita" (único con "usted") | humano, turno | "La conversacion fue derivada a un agente humano para coordinar turno. El label turno fue agregado al chat." |
| `butacas_originales` | tipo tapizado cotizado + "respetar diseño original" (N4.2) | "Perfecto, enviame una foto de tus butacas originales para chequear si podemos replicar un modelo parecido. Una persona de nuestro equipo se contactará con vos para analizar la imagen y contarte las posibilidades" | humano, butacas | "La conversacion fue derivada a un agente humano para coordinar butacas originales. El label butacas fue agregado al chat." |
| `cuotas` | NUNCA (solo existe en la descripción de la tool: "cliente quiere pagar todo en cuotas sin sena") | "En breves personal del equipo se va a comunicar con vos para ver posibilidades" | humano, cuotas | "La conversacion fue derivada a un agente humano para gestionar pago en cuotas." |

Después de cualquier derivación: el prompt supone silencio del bot; el MM vivo NO lo silencia (§0.1). Si el cliente manda "una foto de las butacas" (imagen), el MM la descarta en `Tiene contenido?` / `Confirmar audio1` (solo audio pasa) → el bot no responde, pero tampoco hay acuse (el humano la ve en Chatwoot).

---

## 2. Tabla "Frases obligatorias" (frase textual → cuándo → quién la manda)

Leyenda de "quién": AGENTE (LLM, vía `1ª Parte Respuesta1`; llega sin `¿` y partida por `.`), PRECIOS/FOTOS/HUMANO/COMBO/MM (herramienta, texto íntegro).

| # | Frase (texto exacto en la fuente) | Cuándo | Quién | Fuente |
|---|---|---|---|---|
| F1 | "Hola, te comunicaste con F7-Automotriz" | primer mensaje de un teléfono (COUNT human = 0), 7 s después | MM [CW] | MM `Enviar saludo inicial` |
| F2 | "¿Te interesa algun articulo en especial o quisieras conocer cuales son nuestros productos?" | faltan producto y modelo | AGENTE | `paso1` |
| F3 | "Ofrecemos fundas a medida, fundas tipo tapizado, alfombras termoformadas y cubrevolantes para vehiculos. ¿Cual te interesa mas?" | cliente pregunta qué venden | AGENTE (2 msgs) | `paso1` |
| F4 | "¿Que producto buscas para tu {modelo}?" | tiene modelo, falta producto | AGENTE | `paso1` |
| F5 | "¿Que modelo de vehiculo buscas proteger y renovar?" | tiene producto, falta modelo (única pregunta permitida para modelo) | AGENTE | `base`, `paso1`, `paso3`, `diferenciacion`; `multi_producto` y Registrar la escriben con tildes "¿Qué modelo de vehículo…" |
| F6 | "Que modelo de {marca} tenes? (ej: {2-3 modelos populares de esa marca})" | cliente dijo solo marca | AGENTE | `base` (multi_producto: "¿Qué modelo de {marca} tenés? (listar 2-3 modelos populares)") |
| F7 | "Cuantas butacas tiene tu {modelo}?" | fundas + Spin/Kangoo/Master/H1, antes de fotos, una vez | AGENTE | `paso1` |
| F8 | "Cada funda se realiza a medida y por encargo para cada butaca, el material que utilizamos es cuero automotor." | fotos(fundas) y no vio `catalogo` | FOTOS [CW] | `HTTP Desc Fundas` |
| F9 | "Aca te dejo el catalogo con los diseños" / "https://wa.me/c/5491156013327" / imagen colores "cualquiera de los diseños se pueden confecionar con los colores y logos de esta imagen" | fotos(fundas) y fotos(tipo_tapizado), siempre | FOTOS [WA] | `WA Msg Catalogo`, `WA Msg Link Catalogo`, `WA Enviar Imagen Colores` (+ `TT *`) |
| F10 | "¿Hay algún diseño que te haya gustado o quisieras que te ayude a elegir?" | tras output catálogo fundas o tipo tapizado, mismo turno | AGENTE | `base` |
| F11 | "Las fundas tipo tapizado son en cuero automotor por delante y por detrás. Las mismas quedan como si fuese un tapizado original y podemos respetar el diseño de costura de tus butacas originales" | fotos(tipo_tapizado) y no vio `catalogo` | FOTOS [CW] | `HTTP Desc Tipo Tapizado` |
| F12 | "Las alfombras termoformadas cubren por completo el piso de tu vehículo, evitando derrames o futuros daños. Vienen para cubrir el piso delantero y trasero" | fotos(alfombra) y no vio `alfombra` | FOTOS [CW] | `HTTP Desc Alfombra` |
| F13 | video caption "Estas son las alfombras" / video caption "asi quedan colocadas" | fotos(alfombra) | FOTOS [WA] | `Alf WA Send Intro`, `WA Enviar Video (Cached) Alfombra` |
| F14 | "¿Te gustaria encargar las alfombras en transferencia o aprovechar las 3 cuotas sin interes?" | tras output videos alfombras | AGENTE | `base` |
| F15 | "El cubre volante cosido a mano incluye su colocación, la cual dura 45 minutos aprox con turno previo en CABA y Bariloche. También realizamos envíos a todo el país" | fotos(cubrevolantes) y no vio `cubrevolante` | FOTOS [CW] | `HTTP Desc Cubrevolante` |
| F16 | "Te gustaria encargar tu cubrevolante mediante transferencia o aprovechar las 3 cuotas sin interes?" | tras output "El video de cubrevolantes fue enviado al cliente" (que la tool NUNCA devuelve así) | AGENTE | `base` |
| F17 | "Te envio un video donde explicamos las diferencias entre fundas a medida y tipo tapizado" | fotos(diferenciacion), siempre | FOTOS [CW] | `Chatwoot Intro Diferenciacion` |
| F18 | "¿Cual se adapta mas a lo que estabas buscando?" | tras output video diferenciación | AGENTE | `base`, `diferenciacion` |
| F18b | "¿Cual de las opciones se adapta a lo que estabas buscando?" | mismo evento, según `reaccion_contenido` §VER vs COTIZAR | AGENTE | `reaccion_contenido` |
| F19 | "Las dos opciones tienen precios diferentes segun el modelo de tu vehiculo. ¿Cual te interesa conocer primero?" | "cual es mas cara/barata" en diferenciación | AGENTE (2 msgs) | `diferenciacion` |
| F20 | "¿Buscas un diseño discreto o algo que combine con tu modelo de vehiculo?" | cliente pide ayuda para elegir | AGENTE | `base` |
| F21 | "¿De que color es tu vehiculo? Contame asi veo que diseños pueden combinar bien" | eligió "combinar" | AGENTE | `base` |
| F22 | "Cualquiera de estos diseños pueden ir bien" / "Estos son los modelos baston grande, chico o Vip" | fotos(discreto) (intro y cierre); fotos(personalizado) solo la intro | FOTOS [WA] | `Disc WA Msg Intro/Final`, `Pers WA Msg Intro` |
| F23 | "Podes combinar el logo, las costuras y el vivo de las fundas con el color de tu vehiculo" | caption de la 6ª imagen de personalizado | FOTOS [WA] | `Pers Preparar Imagenes` |
| F24 | "¿Cual de estos te gusta mas?" | tras output fotos discreto | AGENTE | `base` |
| F25 | "¿Hay alguno que te haya gustado?" | tras output fotos personalizado | AGENTE | `base` |
| F26 | Mensajes de cotización (tabla §1.3, 20 variantes) + "Tambien podes abonar en 3 cuotas sin interes los dias miercoles y sabado" + "En efectivo tenes un precio promocional (disponible solo colocando en CABA)" | precios según producto × método | PRECIOS [CW] | nodos `EF *` |
| F27 | "Lamentablemente no contamos con las medidas de tu vehiculo para cotizarte las fundas a medida" / "... las alfombras" / "No contamos con las medidas de tu vehiculo para cotizarte las fundas tipo tapizado" | precios sin match | PRECIOS [CW] | `Enviar Sin Match *` |
| F28 | "Te gustaria conocer la calidad de las fundas en nuestro punto de venta o mediante un video?" | fundas cotizadas y `video_calidad` no visto (OBLIGATORIA) | AGENTE | `paso4_cierre` |
| F29 | video 1 sin caption / video 2 caption "Asi quedan en las butacas de atras" | fotos(video_calidad) | FOTOS [WA] | `WA Enviar Calidad 1/2` |
| F30 | "Quisieras encargar tus fundas mediante transferencia o aprovechar las 3 cuotas sin interes?" | tras output video calidad (NUNCA tras elegir diseño discreto/personalizado) | AGENTE | `paso4_cierre` (`base` con "¿") |
| F31 | "La direccion es Av Olivera 1265, CABA. Te esperamos de lunes a viernes de 9 a 18 hs y sabados de 9 a 14 hs." | fundas cotizadas, elige punto de venta | AGENTE (2 msgs) | `paso4_cierre` |
| F32 | "Que te queda mas comodo?" | fundas cotizadas con video ya visto; alfombras/cubrevolante cotizados | AGENTE | `paso4_cierre` |
| F33 | "¿Te gustaria respetar el diseño original de tus butacas o conocer los diseños disponibles?" | tipo tapizado cotizado | AGENTE | `paso4_cierre` |
| F34 | "Cual te queda mas comodo?" | metodo_pago="todos" | AGENTE | `paso4_cierre` |
| F35 | "De todas formas podes acercarte hasta nuestra sucursal en CABA para que tomemos las medidas de tus butacas o si no ir por la opcion de Fundas a medida, tambien estan hechas en cuero automotor y son de facil colocacion. ¿Tenes la posibilidad de acercarte al taller o preferis conocer los diseños de fundas a medida?" | tipo tapizado sin medidas | AGENTE (2 msgs) | `paso4_cierre` |
| F36 | "Podes acercarte al taller en CABA para tomar las medidas? O quisieras conocer los demas productos?" | alfombras o fundas sin medidas | AGENTE | `paso4_cierre` |
| F37 | "Te puedo ofrecer fundas a medida, ya viste los diseños. ¿Te gustaria avanzar con las fundas?" | residuo sin condición de entrada ("FIN de la seccion Sin medidas") | AGENTE | `paso4_cierre` |
| F38 | "Perfecto, en breves un asistente del equipo se contacta con vos para coordinar tu pedido." | humano(venta) | HUMANO [CW] | `Mensaje Venta` |
| F39 | "En breves personal del equipo se va a comunicar con vos para brindarte la mejor cotizacion posible" | humano(combo) | HUMANO [CW] | `Mensaje Combo` |
| F40 | "En la brevedad un asistente del equipo se va a contactar con usted para coordinar la visita" | humano(turno) | HUMANO [CW] | `Mensaje Turno` |
| F41 | "Perfecto, enviame una foto de tus butacas originales para chequear si podemos replicar un modelo parecido. Una persona de nuestro equipo se contactará con vos para analizar la imagen y contarte las posibilidades" | humano(butacas_originales) | HUMANO [CW] | `Mensaje Butacas Originales` |
| F42 | "En breves personal del equipo se va a comunicar con vos para ver posibilidades" | humano(cuotas) — nunca ordenado por el prompt | HUMANO [CW] | `Mensaje Cuotas` |
| F43 | "¿Te gustaria conocer los demas productos?" | negación a contenido / sigue sin querer | AGENTE | `negaciones` |
| F44 | Las 4 frases "Te super entiendo, nosotros no buscamos ser lo mas baratos..." (§1.7) | "es caro"/"no conviene" tras precio, por producto | AGENTE (2–3 msgs) | `negaciones` |
| F45 | "Gracias por tu consulta, estoy a tu disposicion para cualquier cosa" | no a todo | AGENTE | `negaciones` |
| F46 | "Ya te envie el video de como quedan, ¿te quedo alguna duda?" | "como quedan" con video calidad ya visto | AGENTE | `como_quedan` |
| F47 | 18 respuestas FAQ + datos del negocio (§1.9) | pregunta FAQ | AGENTE | `faq` |
| F48 | "Solemos pedir entre un 30% o un 50%, el restante lo abonas al momento de la colocacion o envio" | TODA pregunta sobre seña | AGENTE | `faq` |
| F49 | "<Label> $<precio>" (uno por producto; variantes cuotas/efectivo) / "Te paso la cotizacion para tu <modelo>:..." / "Tenes la posibilidad de acercarte a nuestro taller en CABA para tomar las medidas de tu <modelo>? Son 30 minutos y asi garantizamos un calce perfecto." | cotizar_combo | COMBO [CW] | `Componer Mensaje` |
| F50 | "¿Te gustaría encargar el combo?" | tras combo exitoso, según bloque `multi_producto` | AGENTE | `multi_producto` |
| F50b | "¿Querrías encargar el combo con una seña en transferencia o aprovechar las 3 cuotas sin interés?" | mismo evento, según descripción de la tool y su output | AGENTE | tool `cotizar_combo` |
| F51 | "Perdón, estoy teniendo un problema técnico, un agente te va a atender en breve" | 2 fallos de cotizar_combo / registrar_intencion (seguido de humano(venta) → F38) | AGENTE | `multi_producto`, tools |

---

## 3. Divergencias prompt vs herramientas (con evidencia)

**D1 — La derivación a humano no silencia al bot.** Prompt `paso4_cierre`: "Despues de ejecutar humano(motivo='venta') tu respuesta termina ahi. La conversacion queda en manos del equipo humano". Herramienta humano solo pone labels. MM `Verificar Label Humano` = `{{ ($json.conversation.labels || []).includes('humano') }}` sobre el item del webhook, donde la conversación está en `$json.body.conversation` (los nodos vecinos leen `$json.body.*`) → siempre `false`, y la salida `true` no conecta a nada. [HV lectura estática; INF runtime]. Efecto: tras F38/F39/F40/F41 el agente sigue contestando cada mensaje del cliente; como el mensaje de HUMANO no queda en memoria, el LLM ni siquiera "sabe" que ya derivó salvo por su propio tool call en el historial (30 mensajes) → puede repetir humano(venta) y el cliente recibe F38 otra vez.

**D2 — Output de fotos cubrevolante ≠ mapeo del prompt.** Tool: "El video de cubrevolante fue enviado al cliente" (`Output Cubrevolante`, `Output CV Cached`). Prompt `base`: `Output: "El video de cubrevolantes fue enviado al cliente" → responder UNICAMENTE: "Te gustaria encargar tu cubrevolante mediante transferencia o aprovechar las 3 cuotas sin interes?"`. Sin match exacto, la frase F16 no está "habilitada" según la regla "SOLO SE PUEDEN USAR SI... RECIBISTE SU OUTPUT". [HV]

**D3 — `cubrevolante` (tools/DB) vs `cubrevolantes` (agente).** FOTOS escribe `contenido_visto='cubrevolante'` (`SS Cubrevolante`), PRECIOS marca `productos_cotizados='cubrevolante'` y exige `cv.includes('cubrevolante')`; el clasificador exige `contenido_visto.includes('cubrevolantes')` (`contenidoRequerido`) y `Preparar Estado` etiqueta `'cubrevolantes'` → el contexto muestra el crudo "cubrevolante" y la fase determinística es `enviar_contenido` en todos los turnos con vigente `cubrevolantes` (nunca `reaccion_contenido`/`post_cotizacion`) hasta que se cotice. La tool `fotos` acepta `cubrevolantes` (plural) y `upsert_session_state` lo guarda así en `producto_vigente`. [HV]

**D4 — Post-fotos de alfombras/cubrevolante el AGENTE pregunta método de pago antes de cotizar.** F14/F16 ("...en transferencia o aprovechar las 3 cuotas sin interes?") vs `paso3`: "NUNCA preguntar metodo de pago antes de cotizar" y "Ejecutar precios SIEMPRE con metodo_pago vacio". Si el cliente responde "transferencia", por REGLA DE PRECIO EXPLÍCITO va precios(transferencia) → PRECIOS manda "El valor de las alfombras para M es de $T en transferencia" → `paso4` ordena "Que te queda mas comodo?" → pregunta redundante después de que el cliente ya eligió. Si responde "dale", va precios("") → 3 mensajes que incluyen "En efectivo tenes un precio promocional" (opción que el agente no ofreció). [HV]

**D5 — Tool `precios` prohíbe cubrevolante; prompt y workflow lo exigen.** Descripción viva: "NUNCA ejecutar para cubrevolantes (precio fijo $72.500)"; enum `producto`: "fundas / tipo tapizado / alfombra". Prompt `paso3`: "Para cubrevolantes SE EJECUTA la herramienta precios igual"; `errores` #24/#25: `precios(producto="cubrevolante")`, "ese precio era de la version vieja". Workflow: rama `Leer Precio CV` → `precios_fijos` (60.000/72.400 según docs). CIERRE_SPRINT_2 dice que la oración se quitó; en el vivo sigue. [HV]

**D6 — Dos frases obligatorias distintas después de cotizar_combo.** Bloque `multi_producto`: "→ Responder TEXTUAL: '¿Te gustaría encargar el combo?'". Descripción de la tool y su propio output (`Output Success`): "Responder al cliente UNICAMENTE: '¿Querrías encargar el combo con una seña en transferencia o aprovechar las 3 cuotas sin interés?'". [HV]

**D7 — cotizar_combo "un solo mensaje" vs N mensajes, y métodos de pago.** `multi_producto` §3: "cotiza TODOS los productos del combo en UN solo mensaje"; `Componer Mensaje` devuelve N items y `Enviar Mensaje Unico` hace N POST. La tool acepta `metodo_pago` ∈ {"", cuotas, efectivo}; el bloque del prompt nunca menciona metodo_pago para combo; `transferencia`/`todos` (válidos en precios) caen al default sin aviso. Formato "$185000" sin separador de miles vs cubrevolante en precios con `toLocaleString('es-AR')`. [HV]

**D8 — `butacas`: tres definiciones incompatibles.** Tool: "Solo enviar si el cliente tiene 7 o mas butacas... Si no aplica o el cliente tiene 5 plazas, enviar string vacio". Prompt: preguntar "Cuantas butacas tiene tu {modelo}?" y pasar el dato; `butacas="2"` para individuales/delanteras. Workflow: `>= 7` → 7 asientos; `== 2` → rama muerta (`price_2ind_*` no se selecciona en `Execute a SQL query`) → el cliente que pidió "solo las 2 delanteras" recibe "El juego completo de fundas..." con precio de 5 plazas sin aviso. [HV]

**D9 — "Que te queda mas comodo?" tras un método explícito.** `paso4` no distingue si `metodo_pago` fue explícito: tras "y en efectivo?" → precios(efectivo) → PRECIOS "El valor de las alfombras para M es de $E en efectivo" → AGENTE "Que te queda mas comodo?" (pregunta por algo que el cliente ya eligió). Para fundas: → F28 (calidad), coherente. [HV]

**D10 — Sin medidas / sin match: la tool solo actúa si la query devuelve una fila.** `Tiene match *` requiere un item; con 0 filas [INF] no hay mensaje ni output → el LLM recibe vacío y el prompt no tiene regla para "output vacío" en single (solo en combo). Además la cadena "Sin Medidas Fundas" (medidas=false) documentada como cerrada en Sprint 2 no existe en el vivo: modelos con fila pero sin medidas reciben precio. La rama del prompt "FUNDAS A MEDIDA SIN MEDIDAS / 30 minutos" fue eliminada del live (sigue en PROMPT_UNIFICADO.md); hoy la frase de 30 minutos solo existe en cotizar_combo. [HV]

**D11 — Cadena de errores no mapeados en el prompt.** Outputs `ERROR: El cliente dijo la MARCA...` (fotos/precios), `ERROR: El cliente NO vio contenido de X...` (precios), `ERROR: No hay combo activo...` (combo), `ERROR: registrar_intencion requiere 2 o mas productos...` no tienen mapeo en los bloques (solo `multi_producto` habla de "ERROR:" para registrar/combo). Para "NO vio contenido" la única salida correcta es ejecutar fotos en el mismo turno (segunda tool, contra "Maximo UNA herramienta por mensaje") o responder texto. [HV]

**D12 — Marca-sin-modelo se evalúa para productos sin modelo.** `fotos(producto="diferenciacion"|"video_calidad"|"discreto"|"personalizado", modelo_vehiculo="Toyota")` → `Devolver Error Marca` sin mandar nada; la tool pide "enviar vacio" en esos casos pero no lo fuerza. [HV]

**D13 — Dos frases textuales para el video de diferenciación.** `base`/`diferenciacion`: "¿Cual se adapta mas a lo que estabas buscando?"; `reaccion_contenido`: "¿Cual de las opciones se adapta a lo que estabas buscando?" (y `diferenciacion` prohíbe "cualquier variante de 'Cual de las opciones se adapta...' sin haber ejecutado fotos"). [HV]

**D14 — `devuelve outputs` altera todas las frases "textuales".** Quita `¿` (todas las preguntas del prompt lo llevan), parte por `.` (F3, F19, F31, F35, F44, FAQ tardan/facturas/colocacion/"Como funciona la compra" → 2–5 mensajes) y borra puntos de miles (cualquier precio que el LLM repita, aunque está prohibido) y URLs (Google Maps de `faq`). La regla "Mensajes exactos entre comillas se envian TEXTUAL" no se cumple a nivel de sistema. [HV]

**D15 — Memoria: lo que el LLM "recuerda" que dijo no es lo que se envió.** `Mem Catalogo Texto` guarda "Aca te dejo el catalogo con los diseños para que elijas el que mas te gusta" (enviado: "Aca te dejo el catalogo con los diseños"); descripciones [CW] y captions no se guardan; marcadores `[CONTENIDO VISTO: x]` / `[VIDEO CALIDAD FUNDAS ENVIADO]` sí se guardan y el prompt prohíbe repetirlos; mensajes de HUMANO y COMBO no se guardan. `Guardar Human` inserta el turno antes del agente → el LLM ve el mensaje actual dos veces. [HV]

**D16 — Elección de diseño siempre cotiza fundas a medida.** `base` §Eleccion de diseno: "→ ejecutar precios(producto='fundas'...)" aunque el asesoramiento aplica "para fundas a medida y tipo tapizado" y el catálogo de tipo tapizado se manda tras cotizar TT (N4.2). Un cliente de tipo tapizado que elige "el segundo" recibe la cotización de fundas a medida (el guard `Contenido OK?` pasa porque `catalogo` es compartido), y luego F28 "Te gustaria conocer la calidad de las fundas..." [HV]

**D17 — `producto_vigente` se contamina con valores que no son productos.** FOTOS hace `upsert_session_state(telefono, producto, modelo)` para TODO `producto` (`video_calidad`, `discreto`, `personalizado`, `diferenciacion`, `tipo_tapizado`, `cubrevolantes`) [HV]; si la RPC no filtra [INF], el clasificador (que compara contra `fundas|alfombra|cubrevolantes|tipo tapizado`) pierde el producto real (`contenidoRequerido[vigente]` undefined → salta a `reaccion_contenido`/`post_cotizacion` según `productos_cotizados`), y el contexto dice "Producto vigente: video_calidad".

**D18 — Fase de prompt sin los bloques necesarios (gaps de ensamblado).** `inicio` (sin `paso3/paso4`): tipo tapizado con modelo en el primer turno cotiza sin tener F33 cargada; `diferenciacion` (sin `paso4`): idem al elegir tapizado; `cambio_producto` (sin `paso3`): "ir al Paso 3 (cotizar)" sin reglas de butacas/metodo_pago; `negacion` (sin `paso1`): no puede listar productos si el cliente acepta F43; `consulta_faq` (sin `paso2/3/4`): no avanza el flujo; `reaccion_contenido` (sin `faq`): "señales de consulta" sin datos del negocio. [HV, tabla `FASE_A_BLOQUES`]

**D19 — Régimen single "múltiples productos" vs régimen combo coexisten.** `cambio_producto` §"Multiples productos en un mismo mensaje" y `paso3_cotizar` §"Cotizacion de multiples productos" ("NUNCA ejecutar precios de multiples productos... el segundo producto SOLO se retoma cuando el cliente lo pide") se cargan junto con `multi_producto` (registrar_intencion + cotizar_combo) en `multi_producto_inicio`; `base` regla 12 dice a la vez "precios puede ejecutarse para multiples productos en un mismo turno". [HV]

**D20 — Insistencia de precio: definida pero sin acción, y la tool bloquea igual.** `base` define INSISTENCIA; `errores` #3 exime "salvo insistencia"; ningún bloque dice qué hacer; `Contenido OK?` de PRECIOS devuelve ERROR sin importar la insistencia. [HV]

**D21 — REGLA DE PRECIO EXPLÍCITO ("prioridad sobre cualquier otro paso") vs guard de contenido de la tool.** "cuanto salen las alfombras en efectivo?" sin haber visto alfombras → si el LLM obedece la regla, PRECIOS devuelve ERROR sin contenido y no manda nada. [HV]

**D22 — FOTOS "personalizado" ignora el color.** El prompt pide el color ("Contame asi veo que diseños pueden combinar bien"); la tool manda siempre las mismas 6 imágenes (3 repetidas de discreto/colores). La imagen "VIP" de discreto es el archivo de colores. [HV]

**D23 — Fallback de error del combo produce dos mensajes de derivación contradictorios.** AGENTE F51 "Perdón, estoy teniendo un problema técnico, un agente te va a atender en breve" + humano(venta) → HUMANO F38 "Perfecto, en breves un asistente del equipo se contacta con vos para coordinar tu pedido." (motivo venta en un combo; tool humano: "NO escribir ningun mensaje al cliente"). [HV]

**D24 — "Cancelar producto del combo": el prompt dice que el sistema limpia; nadie limpia.** Fase `multi_producto_cancelar` no ordena tool; ningún workflow llama `limpiar_productos_pendientes`/`remover_producto_pendiente`; `productos_pendientes` persiste hasta el TTL (60–90 min) → el turno siguiente vuelve a `multi_producto_activo`/`cancelar`. [HV]

**D25 — Motivo `cuotas` de humano es huérfano** (solo en la descripción de la tool) y el mensaje de `turno` usa "usted". [HV]

**D26 — Descripción de tipo tapizado nunca sale si el cliente ya vio el catálogo de fundas.** `IF Desc Tipo Tapizado` usa el mismo flag `catalogo` que fundas; el catálogo (link wa.me) es el mismo. Un cliente que pasó fundas → diferenciación → tipo tapizado recibe el catálogo 2 veces (F9) y nunca F11. [HV]

**D27 — PRECIOS informa datos que no están en el prompt.** "3 cuotas sin interes los dias miercoles y sabado" (msg2) y "colocacion incluida" (cubrevolante) no figuran en `faq`; si el cliente pregunta "que dias?" el LLM no tiene la respuesta (riesgo `errores` #22). [HV]

**D28 — Tool `fotos` no maneja `"tipo tapizado"` con espacio ni mayúsculas** (Switch `equals "tipo_tapizado"`, `contains "funda"` case-sensitive); un `producto` fuera de las 8 reglas termina sin output y sin mensaje. Tool `precios` `equals "tipo tapizado"` con espacio. Dos convenciones para el mismo producto, tal como las lista `base` ("tipo tapizado" para precios, "tipo_tapizado" para fotos). [HV]

**D29 — Saludo y primer turno.** El MM saluda F1 y a continuación el AGENTE responde el Paso 1 (F2/F4/F5 o fotos). El saludo depende de `COUNT(human)` en la memoria: si se limpia `n8n_chat_histories` (o si AGENTE PRUEBA 2, activo, ejecuta su comando "borrar" para ese teléfono, R7) vuelve a saludar a un cliente conocido. [HV+INF]

**D30 — Regla "Maximo UNA herramienta por mensaje" vs flujos que exigen dos.** registrar_intencion + fotos(primario) (N12.1); ERROR sin contenido + fotos (D11); "PRIMERO ejecutar fotos(video_calidad), DESPUES responder" es una sola, OK. [HV]

---

## 4. Ambigüedades del guion — preguntas concretas para el dueño

**A1 — ¿Qué significa que el cliente responda "transferencia" / "en cuotas" / "efectivo" a "Que te queda mas comodo?" o a "Quisieras encargar tus fundas mediante transferencia o aprovechar las 3 cuotas sin interes?"?** (i) Es confirmación de compra → humano(venta) y el equipo pasa CBU/alias y seña; o (ii) hay que re-cotizar con ese método (REGLA DE PRECIO EXPLÍCITO) y volver a preguntar. Hoy conviven las dos reglas. ¿Y si responde "efectivo" pero no es de CABA?

**A2 — ¿Cuándo debe usarse humano(motivo="cuotas")?** Existe el mensaje "En breves personal del equipo se va a comunicar con vos para ver posibilidades" pero ninguna regla lo dispara. ¿Es para "quiero pagar todo en cuotas sin seña"? ¿Se elimina?

**A3 — "si" / "dale" después de ver contenido (sin cotizar) y después de cotizar.** Hoy: tras contenido = "aceptación de contenido" (¿de qué, si el contenido ya se mandó?) o señal de avance → precios; tras cotizar = cierre → humano(venta). ¿Un "dale" a "Te gustaria conocer la calidad... punto de venta o mediante un video?" es elección de video, cierre, o hay que repreguntar?

**A4 — Cubrevolante sin modelo.** `paso1` dice "(o cubrevolantes sin modelo) → Paso 2", `base` dice "Para cubrevolantes tambien se necesita modelo", `errores` #25 prohíbe responder texto ante cubrevolante sin tool. El precio es fijo y no usa el modelo. ¿Se pide modelo o no?

**A5 — Insistencia de precio.** Si el cliente pide precio dos veces sin querer ver contenido, ¿se cotiza igual (hoy la tool lo bloquea) o se insiste con el contenido? ¿Y si dice "no quiero ver nada, pasame el precio"?

**A6 — "Sin medidas → conocer los demás productos".** ¿Con qué frase se ofrecen los demás productos? Hoy no hay texto y `base` prohíbe listar/sugerir. ¿Se usa F3 ("Ofrecemos...") filtrando lo ya visto?

**A7 — Residuo "Te puedo ofrecer fundas a medida, ya viste los diseños. ¿Te gustaria avanzar con las fundas?"** ¿Se elimina (como dice la NOTA) o es la respuesta para "tipo tapizado sin medidas cuando el cliente ya vio el catálogo"? ¿Y la variante eliminada "No contamos con las medidas de tus butacas... Son 30 minutos..." (que sigue en PROMPT_UNIFICADO.md y en cotizar_combo) vuelve o no?

**A8 — "¿Te gustaria conocer los demas productos?" → "si".** ¿Qué se responde? (no hay frase; `paso1` no está cargado en `negacion`).

**A9 — Post-fotos de alfombras y cubrevolante.** ¿Se mantiene la pregunta de método de pago ANTES de cotizar (F14/F16) o se cotiza directo con los 3 mensajes de "sin especificar" y después "Que te queda mas comodo?"? Las dos cosas juntas son redundantes (D4).

**A10 — Butacas.** ¿Cuáles son los valores válidos (5 / 7 / 9 / "2 individuales")? ¿Existe realmente precio para 2 fundas individuales (columnas `price_2ind_*`)? ¿Para qué modelos hay 7 asientos? ¿Se pregunta solo para Spin/Kangoo/Master/H1?

**A11 — Personalizado por color.** ¿Se espera que las fotos dependan del color? Hoy son fijas. ¿Vale la pena pedir el color?

**A12 — Diseños discretos.** ¿"VIP" es realmente la imagen de colores (`1Gj8nftQ…`)? ¿Cuáles son las 3 fotos correctas?

**A13 — Tipo tapizado: orden catálogo/cotización.** Hoy: cotiza primero y recién después ofrece el catálogo ("respetar diseño original o conocer los diseños"). Si el cliente elige un diseño del catálogo TT, ¿qué se responde? (hoy cotizaría fundas a medida, D16). ¿Y si pide ayuda para elegir en TT?

**A14 — "Como quedan" para alfombra/cubrevolante ya vistos y para tipo tapizado.** Sin frase definida.

**A15 — Qué debe pasar cuando precios no encuentra el modelo (0 filas) o cuando la fila existe pero `medidas=false`.** ¿Se cotiza igual (hoy sí), se manda "no contamos con las medidas", o se invita al taller con los "30 minutos"?

**A16 — Tipo tapizado en el primer turno** ("tipo tapizado para corolla"): ¿se cotiza en ese mismo turno (3 mensajes de precio + F33) o primero se manda el catálogo? Si es cotizar, la frase F33 no está cargada en fase `inicio`/`diferenciacion` (D18).

**A17 — Combo: frase post-cotización.** ¿"¿Te gustaría encargar el combo?" o "¿Querrías encargar el combo con una seña en transferencia o aprovechar las 3 cuotas sin interés?"? ¿El combo se cotiza solo en transferencia por defecto? ¿"Fundas y tipo tapizado" nunca es combo?

**A18 — Combo con secundario sin match.** Hoy se omite en silencio. ¿Se avisa al cliente ("alfombras: no contamos con las medidas") o se deriva?

**A19 — Combo sin modelo cuando el cliente responde con marca o con otra cosa.** ¿Cuántos turnos se espera el modelo antes de "romper" el combo? (TTL actual: 60–90 min de inactividad, y cualquier actividad lo extiende.)

**A20 — Después de derivar a humano, ¿el bot debe callarse del todo, o seguir contestando FAQ?** Hoy sigue contestando todo (D1). Si debe callarse: ¿hasta que un humano quite el label, o por tiempo? ¿Qué pasa si el cliente manda una foto de las butacas (hoy se descarta sin acuse)?

**A21 — Efectivo fuera de CABA.** PRECIOS siempre manda "En efectivo tenes un precio promocional (disponible solo colocando en CABA)". ¿Se pregunta ubicación en algún momento del guion? `errores` #16 lo prohíbe tras elegir método; `faq` lo contempla ("Podrias acercarte a nuestro taller?").

**A22 — Datos bancarios / seña.** Confirmar que NUNCA los da el bot (hoy no existen en prompt ni tools; `Herramienta pedido` OFF tenía alias de Galicia/Ciudad). ¿El 30–50 % de seña es la única respuesta autorizada?

**A23 — Formato de los mensajes del AGENTE.** ¿Está bien que se eliminen los "¿" y que se parta por punto (dirección en 2 mensajes, "Como funciona la compra" en 5, link de Maps roto)? ¿O hay que cambiar `devuelve outputs` y/o quitar puntos/URL del prompt?

**A24 — Primer mensaje.** ¿El saludo "Hola, te comunicaste con F7-Automotriz" debe ir separado de la primera respuesta (hoy: saludo a los ~7 s y luego F2 ~2 s después) o integrado? ¿Debe repetirse para un cliente que vuelve después de semanas (hoy nunca, salvo que se borre la memoria)?

**A25 — Nombre canónico y precio de cubrevolante.** ¿Definitivamente `cubrevolante` singular en todo (prompt, tool fotos, clasificador, labels)? ¿La descripción de la tool precios debe permitir cubrevolante y quitar el "$72.500"?

**A26 — Estado permanente.** `contenido_visto` y `productos_cotizados` no expiran nunca: un cliente que vuelve en 3 meses "ya vio todo y ya fue cotizado" (no se le reenvía catálogo ni se le repregunta). ¿Se quiere un TTL (p. ej. 30 días) o un reset manual?

**A27 — Audios.** ¿Se espera que el bot entienda audios? Por lectura estática (§0.1) hoy se descartan. Confirmar con un audio real antes de asumir.

---

## 5. Resumen de la secuencia canónica single (lo que el dueño diseñó, con los mensajes reales)

1. Cliente escribe → **MM**: "Hola, te comunicaste con F7-Automotriz" (solo 1ª vez) → **AGENTE** Paso 1 (F2/F3/F4/F5/F6/F7 según falte).
2. Producto + modelo → **FOTOS** manda descripción [CW] + catálogo/videos [WA] → **AGENTE** frase obligatoria (F10/F14/F16/F18). Tipo tapizado salta a 3.
3. Reacción positiva / elige diseño / pide precio → **PRECIOS** manda la cotización (3 mensajes si no pidió método; 1 si lo pidió) → **AGENTE** Paso 4: fundas → F28 (→ video: **FOTOS** 2 videos + F30 / punto de venta: F31); tapizado → F33 (→ original: **HUMANO** F41 / diseños: **FOTOS** catálogo + F10); alfombras/cubrevolante → F32; todos → F34; sin medidas → **PRECIOS** F27 + **AGENTE** F35/F36 (→ taller: **HUMANO** F40).
4. Confirmación → **HUMANO** F38 (venta) / F39 (combo). Fin del guion (el equipo coordina seña, datos y entrega; el bot, en la práctica, no se calla — D1).
5. Transversales: negación → F43/F44/F45; cambio de producto → vuelve a 2 o 3 sin preguntar; FAQ → F47/F48; "como quedan" → video/fotos o F46; 2+ productos → **REGISTRAR** (silencioso) → **FOTOS** del primario → **COMBO** N mensajes + F50/F50b → **HUMANO** F39.
