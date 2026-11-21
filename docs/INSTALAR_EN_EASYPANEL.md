# Instalar el agente en el servidor con Easypanel

Instalarlo **no cambia nada para los clientes**: n8n sigue atendiendo hasta que vos cambies el webhook de Chatwoot (etapa 5). Se puede dejar instalado antes y usarlo para las pruebas en paralelo (etapa 4).

Esta guía reemplaza la sección «Dejarlo corriendo en un servidor» del README del kit, que está escrita para Coolify. El Dockerfile es el mismo. Lo que cambia es que en Easypanel no hay chequeo de salud.

Investigado el 15/11/2026 sobre la documentación oficial de Easypanel. Al final están las fuentes y lo que no se pudo confirmar.

---

## Antes de empezar (una sola vez)

1. **El código en GitHub, en un repo privado.** Creá en github.com un repo **privado y vacío** (por ejemplo `agente-f7`) y pasale el link a Claude Code para que suba el proyecto. El `.env` no se sube nunca: está en `.gitignore`.
2. **Un token de GitHub para Easypanel**, que le deja leer solo ese repo:
   - En GitHub, entrá a https://github.com/settings/tokens?type=beta y tocá **Generate new token**.
   - En **Repository access**, elegí **Only select repositories** y marcá el repo del agente.
   - En **Repository permissions**, poné **Metadata: Read-only**, **Contents: Read-only** y **Webhooks: Read and write**. Este último solo hace falta para el deploy automático.
   - En Easypanel, andá a **Settings → Github**, pegá el token y esperá el aviso **«Github token updated»**.
3. **Un subdominio** para el agente, por ejemplo `agente-f7.teotec.org`. En tu DNS, creá un registro **A** que apunte a la IP del VPS. Si usás Cloudflare con la nube naranja, poné SSL/TLS en **Full** o **Full (Strict)**.
4. **Cupo de proyectos.** El plan gratis de Easypanel permite 3 proyectos. Si n8n y Chatwoot ya ocupan los lugares, el agente puede ir dentro de un proyecto existente, siempre que el agente y su base queden **en el mismo proyecto**.

## En Easypanel

| # | Dónde | Qué hacer |
|---|---|---|
| 1 | Panel → **New** | Creá el proyecto, por ejemplo `agente-f7`. Conviene un nombre corto, porque pasa a formar parte de las direcciones internas. |
| 2 | Proyecto → **New Service → Postgres** | Nombre: `db`. Cuando arranque, en la pestaña **Credentials** copiá la **URL interna**. Tiene la forma `postgres://postgres:<clave>@agente-f7_db:5432/agente-f7?sslmode=disable`. **No lo publiques** en la pestaña Expose. |
| 3 | Proyecto → **New Service → App** | Nombre: `agente`. |
| 4 | App → **Source** | Elegí **GitHub**: repo `tu-usuario/agente-f7`, la rama que vas a usar y Build Path `/`. **No uses Source → Dockerfile**: es un Dockerfile pegado en el panel y no trae el código. |
| 5 | App → **Build** | Elegí **Dockerfile** y dejá la ruta `Dockerfile`. |
| 6 | App → **Environment** | Pegá el bloque de variables que está más abajo y guardá. **Guardar no despliega.** |
| 7 | App → **Domains → Add Domain** | Host: `agente-f7.teotec.org`. Path: `/`. **HTTPS activado**. Protocolo interno HTTP y **puerto 8000**. Marcalo como primario. Si el App ya trajo un dominio automático `*.easypanel.host`, cambiale el puerto a 8000 o borralo. |
| 8 | App → **Advanced → Deploy** | **Replicas = 1, obligatorio.** El kit guarda en memoria los mensajes que está juntando y los que ya contestó: con dos copias corriendo, contesta doble o mal. |
| 9 | App → **Resources** | Dejale memoria al build: corre en el mismo servidor que n8n y Chatwoot. Un límite muy bajo corta la construcción. |
| 10 | App → **Overview → Deploy** | Si falla al construir, el error está en **Deployments**. Si arranca y después se cae, el error está en **Logs**. |
| 11 | Navegador | Abrí `https://agente-f7.teotec.org/salud`. Tiene que mostrar `"estado": "ok"`, `"modelo": "claude-sonnet-5"`, `"memoria": "postgres"`, `"agente": "f7"`, `"bandeja": "1"`, `"planilla": "ok"` y `"fotos_y_videos": 14`. Si dice `sqlite`, falta `MODO=produccion`. Si en vez de eso el servicio no arranca, mirá **Logs**: dice qué falta (por ejemplo `AGENTE=f7`, la base o una foto del catálogo). Si `planilla` dice `error`, el servidor no pudo leer la planilla de precios y el agente no va a poder cotizar. |
| 12 | Overview → **Enable Auto Deploy** (opcional) | Cada vez que se sube un cambio a GitHub, se despliega solo. |

### Las variables (paso 6)

Copiá los valores secretos de tu `.env`. No los pegues en ningún chat.

```
AGENTE=f7
PROVEEDOR=claude
ANTHROPIC_API_KEY=<la clave de Claude>
MODELO_CLAUDE=claude-sonnet-5
OPENAI_API_KEY=<la clave de OpenAI para los audios>
MODO=produccion
POSTGRES_DSN=<la URL interna del paso 2>
CACHE=true
MAX_TOKENS=4096
MEMORIA_MENSAJES=30
PROMPT_SISTEMA=prompts/sistema.md
CHATWOOT_URL=https://chatwoot.teotec.org
CHATWOOT_TOKEN=<token de un usuario de la cuenta que atiende>
CHATWOOT_CUENTA_ID=1
CHATWOOT_BANDEJA_ID=1
CHATWOOT_WEBHOOK_TOKEN=<el mismo de tu .env>
CHATWOOT_ETIQUETA_HUMANO=humano
BUFFER_SEGUNDOS=15
MENSAJES_POR_RESPUESTA=5
TOPE_MENSAJES_POR_DIA=0
LARGO_MAXIMO_DE_ENTRADA=2000
RESPETAR_RESUELTAS=0
SOLO_EL_PRIMER_MENSAJE=0
DESCRIBIR_IMAGENES=0
TRANSCRIBIR_AUDIOS=1
```

- **`AGENTE=f7` no puede faltar.** Sin esa línea el servidor no arranca: es a propósito, para que nunca atienda a los clientes el agente genérico del kit.
- **`CHATWOOT_BANDEJA_ID=1`** es la bandeja del WhatsApp de F7. La cuenta 1 tiene otra (la 3, «Test Bot API») y ahí el agente no contesta. Si algún día se prueba en otra cuenta, va el número de esa bandeja.
- **`CHATWOOT_CUENTA_ID=1` no hace que el agente conteste nada por sí solo.** Empieza a atender recién cuando Chatwoot le avisa (ver «El cambio»).
- **`OPENAI_API_KEY` es solo para los audios.** Si no se carga, cuando un cliente manda un audio la charla pasa a Candela (queda con «humano» y asignada a ella) sin contestarle nada.
- **`MODELO_CLAUDE` no puede faltar.** Si falta, el kit usa el modelo más caro de Claude sin avisar.
- **`PUERTO` no hace falta**, porque el Dockerfile ya usa el 8000.
- **Las de Gmail y Telegram quedan afuera:** los mails de aviso todavía no se decidieron y Telegram no se usa.

## Probarlo sin tocar a los clientes (etapa 4)

**Este paso es opcional.** Sirve si se quiere probar en el servidor antes de tocar la línea real. Si la línea todavía no atiende clientes con el agente, se puede ir directo a «El cambio».

**Regla de oro: Chatwoot le avisa a un solo agente por vez.** Si en la cuenta 1 quedan activos el webhook de n8n y el del agente nuevo, contestan los dos.

**En una cuenta de pruebas cambian tres cosas:** `CHATWOOT_CUENTA_ID` (el número de esa cuenta), `CHATWOOT_BANDEJA_ID` (el número de su bandeja, o vacío para todas) y el pase a Candela, que no se va a confirmar porque el usuario 3 no existe ahí (el agente igual queda pausado con «humano»).

1. En Chatwoot, creá una **cuenta de pruebas**. Se hace desde la consola de super admin: `https://chatwoot.teotec.org/super_admin` → Accounts.
2. Adentro, creá una bandeja de prueba: canal API, o un número de WhatsApp de prueba si tenés uno.
3. Sumá tu usuario a esa cuenta. En Easypanel, poné `CHATWOOT_CUENTA_ID` con el número de la cuenta de pruebas, que aparece en la URL como `/app/accounts/<número>/`, y hacé **Deploy**.
4. En la cuenta de pruebas, andá a **Configuración → Integraciones → Webhooks → Agregar**:
   - URL: `https://agente-f7.teotec.org/chatwoot/<CHATWOOT_WEBHOOK_TOKEN>`
   - Evento: **Mensaje creado** (solamente).

## El cambio (etapa 5): lo hacés vos, cuando lo apruebes

1. Antes del cambio, `/salud` tiene que mostrar todo lo del paso 11. El agente nuevo arranca sin historial: no conoce lo que se habló con el de n8n (cada conversación empieza con el saludo).
2. En la cuenta 1 de Chatwoot, andá a **Configuración → Integraciones → Webhooks** y **editá el webhook que hoy apunta a n8n** (no agregues otro al lado):
   - URL: `https://agente-f7.teotec.org/chatwoot/<CHATWOOT_WEBHOOK_TOKEN>` (con tu dominio y tu token).
   - Evento: **Mensaje creado** (solamente).
   Antes de guardar, copiá la URL vieja de n8n en un lugar seguro: es la que hace falta para volver atrás.
3. En n8n, **desactivá** el flujo principal. **No lo borres.**
4. Desde tu WhatsApp, escribile a la línea: primero `borrar` (tiene que contestar «Ya borre mi memoria…») y después una consulta común.

**Para volver atrás:** poné de nuevo la URL de n8n en ese webhook y reactivá el flujo principal. Es un minuto.

**Si el agente no contesta:** mirá **Logs** del App en Easypanel. Cada mensaje que entra deja una línea con el número de conversación, y si algo falla deja el error. Cuando algo falla, el cliente no ve el error: la conversación queda con la etiqueta «humano» y asignada a Candela. Para devolvérsela al agente, sacale la etiqueta o escribí `borrar` desde ese chat.

## Cuidados

- **No actives Security (Basic Auth) ni Maintenance** en el dominio del agente: los webhooks de Chatwoot dejarían de llegar.
- **No sumes réplicas ni «zero-downtime».** Por un momento correrían dos agentes a la vez.
- **No pongas claves en el Dockerfile.** Easypanel pasa las variables también a la construcción, y avisa que eso no es seguro para secretos. El Dockerfile del kit no lo hace: dejalo así.
- **La clave del webhook viaja en la URL.** Probablemente quede escrita en los registros del proxy de Easypanel (no está confirmado). Que el panel solo lo vea quien tiene que verlo. Si alguien más tuvo acceso, generá una clave nueva.
- **No hay chequeo de salud automático:** Easypanel no lo ofrece. Mirá `/salud` a mano o con un monitor externo. **No agregues HEALTHCHECK al Dockerfile:** hay un error abierto de Easypanel que traba las actualizaciones.
- **Los registros guardan 10 MB × 3 archivos.** Lo más viejo se pierde.
- **Error conocido con el token de GitHub:** con tokens nuevos, Easypanel a veces dice «Github token is not valid». Lo único publicado que lo resuelve es reiniciar o actualizar el servidor.

## Día a día

En **Overview** del App:
- **Logs:** el registro en vivo.
- **Restart:** reinicia sin reconstruir.
- **Force Rebuild:** reconstruye de cero.
- **Shell:** una terminal dentro del contenedor.
- **Stop / Start:** apaga o prende el agente.

## Lo que no se pudo confirmar

- **Si un proyecto ve a otro por la red interna.** La doc no lo dice. Por eso la base va en el mismo proyecto que el agente, y Chatwoot se usa por su dirección pública con https.
- **El puerto que trae por defecto un dominio nuevo.** Revisá que diga 8000.
- **Cómo trata Easypanel un HEALTHCHECK del Dockerfile.**
- **Los tiempos de espera y el tamaño máximo de los pedidos en el proxy.** No afecta al kit: contesta enseguida y descarta pedidos de más de 512 KB.

## Fuentes

- https://easypanel.io/docs/services/app (Source, Build, Environment, Domains, Deploy, Resources, Overview, Deployments)
- https://easypanel.io/docs/code-sources/github
- https://easypanel.io/docs/services/postgres
- https://easypanel.io/docs/builders
- https://easypanel.io/docs/guides/custom-service-domain
- https://easypanel.io/pricing
- https://my.easypanel.io/feedback/post/healthchecks-break-easypanel
- Del kit: `Dockerfile`, `README.md` (líneas 1026–1122) y `src/agente/web/webhook.py` (la ruta `/salud`).
