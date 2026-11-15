# Prompts

La versión nueva del principal unificado vive en `SYSTEM_PROMPT_F7_V1.md`, junto con `ENVIAR_MULTIMEDIA_F7.md` y `SOLICITUDES_MULTIMEDIA_F7.md`. `src/prompt-f7/ensamblar.mjs` genera sus bloques por fase; `node scripts/preparar-prompt-f7.mjs` prepara el snapshot local para importar. Alcance y estado: [SYSTEM_PROMPT_F7_V1.md](../docs/SYSTEM_PROMPT_F7_V1.md). No editar el prompt viejo para cambiar esta versión.

`PROMPT_UNIFICADO_agente_ventas.md` (2026-06-11): los 14 bloques de `BLOQUES{}` del nodo "Clasificar y Ensamblar" concatenados en orden de flujo, para lectura. Está desincronizado con el vivo en el bloque `paso4_cierre` (conserva las 3 líneas de "sin medidas → taller en CABA" que se quitaron del agente ese mismo día).

Para el agente anterior, el código extraído es `src/agent/clasificar_y_ensamblar.js` (`npm run extract`). La instancia viva sigue siendo la fuente de verdad operativa. Pendiente histórico: generar su archivo de lectura por script en vez de mantenerlo a mano (backlog 1.19).
