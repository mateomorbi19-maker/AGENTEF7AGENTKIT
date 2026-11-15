# Material de F7 traído del proyecto en n8n

Copiado el 15/11/2026 desde `../Agente f7 completo` (último commit 8823f72, estado publicado al 07/11/2026). Es **material de consulta** para pasar el agente al kit: no se ejecuta desde acá. Si algo cambia en el proyecto viejo después de esta fecha, este material no se entera.

Los archivos de derivación (`logica/derivacion/`, `n8n/herramienta-derivacion-v1.json` y dos documentos de `docs/`) figuraban borrados sin confirmar en el proyecto viejo. Se sacaron del último commit, donde siguen intactos.

## Qué hay en cada carpeta

| Carpeta | Qué tiene | Para qué sirve |
|---|---|---|
| `CLAUDE_F7_n8n.md` | Las instrucciones del proyecto viejo | Las reglas comerciales y las decisiones de Mateo vigentes al 07/11 |
| `brief/` | `brief-comercial.md` (G:\Mi unidad) y el análisis del brief nuevo (20/10) | El proceso comercial de F7, contado por el dueño |
| `prompt/` | `SYSTEM_PROMPT_F7_V1.md` y los contratos de multimedia | **Fuente del prompt** (v9.4) |
| `logica/prompt-f7/` | `ensamblar.mjs` | Cómo se arma el prompt final que ve el modelo |
| `logica/unificado/` | `logica.mjs` | Filtros del evento, bandeja, buffer y estado del flujo principal |
| `logica/reinicio/` | `logica.mjs`, `sql.mjs` | El comando «borrar» y las épocas de memoria |
| `logica/precios/` | Motor de cotización, contrato (`descripcion.mjs`), transporte y SQL | **Fuente de la herramienta de precios** |
| `logica/multimedia/` | Catálogo (`catalogo.json`), selección, entrega y SQL | **Fuente de la herramienta de fotos y videos** |
| `logica/derivacion/` | Contrato (`descripcion.mjs`), motor y SQL | **Fuente del pase a Candela** |
| `n8n/` | Exports del principal (121 nodos), precios, multimedia, derivación y media-proxy | Lo que corre hoy en n8n, nodo por nodo |
| `docs/` | Traspaso del 06/11, backlog, flujo principal, cotización natural, reinicio, multimedia, derivación, tarifas de medios de pago, lectura de la planilla, catálogo de medios y planes de noviembre | Contexto y decisiones |
| `casos-reales/` | Relevamiento de Messenger (31 casos) y de mensajes cortos | Para armar pruebas fieles a los clientes |
| `media/README.md` | Cómo está organizado el material audiovisual | Los videos y fotos NO se copiaron (≈150 MB): están en Google Drive y en `../Agente f7 completo/recursos/f7-media/` |

## Qué está al día y qué no

- **Al día al 07/11:** `CLAUDE_F7_n8n.md`, `docs/CONTEXTO_CLAUDE_CODE_2026-11-06.md`, `docs/ESTADO_Y_BACKLOG.md` (§19 en adelante), el prompt, los contratos, la lógica y los exports.
- **Desactualizado:** `docs/GUION_DE_VENTA.md` describe septiembre. Ante una contradicción, valen el prompt v9.4, los contratos y las decisiones posteriores de Mateo.
- **Ojo con los casos reales:** son fragmentos de Messenger, no chats completos ni un guion de respuestas correctas. Las respuestas de la empleada no son el oráculo.

## Lo que quedó afuera a propósito

- Scripts de n8n (export, import, parches y runners de prueba contra n8n): no aplican al kit.
- Reportes de pruebas y simulaciones (`PRUEBA_*`, `PUBLICACION_*`, `REVISION_*`): son de la versión en n8n.
- Claves y `.mcp.json`: las claves van solo en el `.env` de este proyecto.
