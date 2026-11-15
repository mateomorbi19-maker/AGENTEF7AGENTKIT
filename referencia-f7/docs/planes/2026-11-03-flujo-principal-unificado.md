# Flujo principal F7 unificado — plan de implementación

**Objetivo:** reunir recepción Chatwoot, filtros, audio, buffer Redis, agente y envío en un solo workflow; conservar las herramientas como workflows separados.

**Alcance aprobado:** reutilizar los nodos existentes; Mateo autorizó además corregir la concurrencia y el plazo de 15 segundos del buffer. Prompt y herramientas comerciales se desarrollan en la siguiente etapa.

**Base:** n8n vivo, `Memory Manager - F7 v3` y `Agente de ventas V2.10`. El export y diff confirmaron únicamente las diferencias locales de Fase 0 ya documentadas. Se toman de ellas solo F1/F2/F7/F8/F9 (técnicas), sin importar F3–F6 (guion/herramientas).

## Diseño

- Crear un workflow nuevo inactivo. Ruta y claves Redis propias; los anteriores permanecen intactos.
- Quitar el Execute Workflow del Memory Manager y el trigger del agente. Adaptar referencias a `Preparar Datos` conservando `texto`, `key`, `telefono`, `conversation_id`.
- Admitir mensajes de contacto entrantes, públicos, con texto o audio; ignorar eventos ajenos, ecos y conversaciones con label `humano`.
- Conservar descarga y transcripción con las credenciales existentes. Unificar variantes del payload y declarar el binario de audio.
- Cola Redis por cuenta/conversación. Exclusión por conversación desde consumo hasta final de respuesta. GET + INCR elige un consumidor; TTL de 900 s y timeout del workflow de 300 s. El dueño espera 15 s desde la última incorporación y consume N elementos mediante POP tail, sin borrar entradas posteriores.
- Conservar modelo, memoria, prompt, herramientas, saludo y ritmo de 2 s entre fragmentos. Corregir split para conservar puntos de importes y enlaces, y serializar el body JSON.
- Liberar exclusión en salida normal y errores controlados. Documentar que un corte de infraestructura exige recuperación; no prometer exactamente una vez ante caída luego de enviar.

## Trabajo y verificación

- [x] Probar normalización, filtros, split y serialización con casos de texto/audio.
- [x] Simular intercalados del buffer, consumo de lote y liberación del lock.
- [x] Generar JSON reproducible, sin secretos, desde fuentes vivas respaldadas en `backups/`.
- [x] Verificar grafo, credenciales, herramientas y prompt contra las fuentes.
- [x] Ejecutar suite local y validador n8n; crear inactivo y releer lo guardado.
- [ ] Probar runtime aislado. Pendiente: token MCP oficial no configurado; Computer Use terminó al no poder verificar URL de Chrome.
- [x] Registrar resultado, limitaciones y activación pendiente en el backlog.

La activación, cambio del webhook de Chatwoot y prueba desde WhatsApp real quedan a cargo de Mateo según AGENTS.md. No se commitea ni pushea.
