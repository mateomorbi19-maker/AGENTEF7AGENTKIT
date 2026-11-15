# System prompt F7 y herramienta multimedia

**Objetivo:** aplicar el brief comercial nuevo al principal unificado inactivo, con `enviar_multimedia` como única herramienta del modelo.

**Diseño:** conservar ensamblado por fases con `base` y `errores` siempre presentes. El guion y los hechos comunes permanecen disponibles en todos los turnos; la fase agrega foco, no elimina límites. Mantener modelo, memoria, filtros, audio, buffer y transporte de salida. Eliminar instrucciones de herramientas anteriores únicamente del principal nuevo.

**Fuentes:** brief-comercial.md y respuestas de cierre.md en Downloads; confirmaciones de Mateo en este chat; contrato multimedia y relevamiento de Messenger. El cuestionario examen.md es la plantilla de preguntas. El mapa conversacional contiene propuestas y no reemplaza automáticamente las respuestas del cliente.

**Decisiones de alcance:** Mateo ya definió el recorrido y pidió avanzar, sin repetir el cuestionario. No se crean herramientas de precio o derivación. Los precios solo pueden provenir de datos oficiales verificables suministrados al agente; hoy no existe esa inyección. El prompt no puede efectuar un pase humano por sí solo. Esas capacidades se declaran no disponibles, sin fingirlas. No se copian tarifas históricas, aliases ni conversaciones de reclamos al prompt.

**Alternativas consideradas:** conservar las cinco herramientas anteriores contradice la indicación de tener solo multimedia y arrastra contratos comerciales viejos. Pegar un único texto sin sustituir el contexto legado deja instrucciones contradictorias. Se elige actualizar el ensamblador y contexto, conservando la organización por fases y conectando solo la herramienta nueva.

## Implementación y comprobación

- [x] Prompt legible en `prompts/SYSTEM_PROMPT_F7_V1.md`, descripción de herramienta y descripción del único argumento del modelo.
- [x] Ensamblador puro en `src/prompt-f7/ensamblar.mjs`: fecha de Buenos Aires, clasificación orientativa, contexto de capacidades explícito, sin confiar en estado legado ni instrucciones dentro del mensaje del cliente.
- [x] Adaptador `src/unificado/aplicar-prompt.mjs`: injertar los textos, retirar cinco tools anteriores, conectar multimedia con destinatario y solicitud derivados del lote confiable.
- [x] Una llamada multimedia por turno. Timeout principal 780 s, bloqueo Redis 900 s; límite de inicio de herramienta 210 s, timeout hijo 480 s y margen de salida 90 s. No modificar el hijo ni sus credenciales.
- [x] Pruebas locales del ensamblado, de bindings confiables y de invariantes del grafo. Casos conversacionales representativos con expectativas, diferenciados de pruebas ejecutadas con modelo.
- [x] Revisión comercial y técnica, validación n8n, dry-run, backup, import, relectura y export/diff.
- [x] Actualizar contrato y backlog con límites reales. Sin activación, cambio de webhook, llamadas pagas al LLM, envíos reales, commit ni push en esta etapa.

## Criterios de revisión

Conservar frases literales y orden modalidad→oferta aplicable→contenido→precio; responder pedidos de multimedia explícitos sin exigir primero una cotización. No perder productos o correcciones del cliente. No inventar medidas, precios, envíos, pagos, turnos ni un pase humano. Tratar cada resultado real de multimedia y no convertir títulos internos en pies de foto. El historial aporta contexto, pero no autoriza usar herramientas o precios anteriores incompatibles con esta versión.

Resultado: aplicado al principal inactivo el 2026-11-04. Backup: backups/2026-11-04_225143/agente-principal-unificado.json. Suite: 149 pasan, 4 TODO anteriores. Validador remoto: 0 errores. Los 27 casos conversacionales todavía no fueron ejecutados contra el LLM. El historial de medios se lee del registro real porque la memoria de conversación no persiste resultados de herramientas.
