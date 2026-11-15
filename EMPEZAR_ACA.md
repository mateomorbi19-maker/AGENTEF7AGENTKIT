# Empezar acá

En esta carpeta está el agente de F7 en su versión de código, armado sobre el Agent Kit. El agente de n8n sigue atendiendo a los clientes hasta que vos hagas el cambio.

## 1. Cargá las tres claves (una sola vez)

Abrí el archivo `.env` de esta carpeta con el Bloc de notas y completá estas tres líneas:

| Línea | Qué va | De dónde la sacás |
|---|---|---|
| `ANTHROPIC_API_KEY=` | La clave de Claude con saldo, la misma que usa hoy n8n | console.anthropic.com → API Keys, o donde la tengas guardada |
| `OPENAI_API_KEY=` | La clave de OpenAI que transcribe los audios | platform.openai.com → API keys |
| `CHATWOOT_TOKEN=` | El token de tu usuario de Chatwoot | Chatwoot → tu perfil → Configuración del perfil → Token de acceso |

Pegá cada valor después del `=`, sin espacios ni comillas, y guardá el archivo. Ese archivo no se sube a GitHub. No lo pegues en ningún chat.

## 2. Probalo en tu compu

Hacé doble clic en `abrir-web-de-pruebas.cmd` y abrí http://localhost:8000.

Por ahora responde con la personalidad de ejemplo del kit: el guion de F7 se carga en la etapa 2. Esta prueba confirma que tu clave anda.

## 3. Lo que sigue

1. ~~Base del proyecto~~ (hecha).
2. Pasarle F7: el mismo guion y lo que hoy hace n8n alrededor del modelo.
3. Las tres herramientas en código: precios, fotos y videos, pase a Candela.
4. Pruebas sin clientes, en tu compu y después en el servidor en paralelo.
5. El cambio: lo hacés vos cuando lo apruebes, y n8n queda apagado pero no borrado.

**Cómo instalarlo en el servidor con Easypanel:** [docs/INSTALAR_EN_EASYPANEL.md](docs/INSTALAR_EN_EASYPANEL.md).

**Qué hay que pasar de n8n y cómo va cada parte:** [docs/MAPA_MIGRACION.md](docs/MAPA_MIGRACION.md).
