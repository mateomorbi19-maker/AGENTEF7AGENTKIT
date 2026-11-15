// Tabla aislada: no modifica session_state ni historial comercial legado.
export const schema = `CREATE TABLE IF NOT EXISTS public.f7_cotizaciones_envios (
 account_id bigint NOT NULL CHECK(account_id=1), conversation_id bigint NOT NULL CHECK(conversation_id>0),
 solicitud_id text NOT NULL, owner_execution text NOT NULL, pedido jsonb NOT NULL, resultado jsonb NOT NULL,
 estado text NOT NULL CHECK(estado IN ('reservado','enviando','aceptado','fallido','desconocido','control_humano')),
 chatwoot_message_id bigint, motivo text, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(account_id,conversation_id,solicitud_id),
 CHECK(estado <> 'aceptado' OR (chatwoot_message_id IS NOT NULL AND chatwoot_message_id > 0))
);
ALTER TABLE public.f7_cotizaciones_envios ENABLE ROW LEVEL SECURITY;
SELECT true AS ready;`;

export const reservar = `WITH nueva AS (
 INSERT INTO public.f7_cotizaciones_envios(account_id,conversation_id,solicitud_id,owner_execution,pedido,resultado,estado)
 VALUES($1::bigint,$2::bigint,$3::text,$4::text,$5::jsonb,$6::jsonb,'reservado')
 ON CONFLICT DO NOTHING RETURNING *
)
SELECT true AS acquired,true AS compatible,estado,resultado,chatwoot_message_id FROM nueva
UNION ALL
SELECT false AS acquired,pedido=$5::jsonb AS compatible,estado,resultado,chatwoot_message_id
FROM public.f7_cotizaciones_envios
WHERE account_id=$1::bigint AND conversation_id=$2::bigint AND solicitud_id=$3::text
AND NOT EXISTS(SELECT 1 FROM nueva);`;

export const marcarEnvio = `WITH marcado AS (
 UPDATE public.f7_cotizaciones_envios SET estado='enviando',updated_at=now()
 WHERE account_id=$1::bigint AND conversation_id=$2::bigint AND solicitud_id=$3::text
 AND owner_execution=$4::text AND estado='reservado' RETURNING 1
) SELECT EXISTS(SELECT 1 FROM marcado) AS enabled;`;

export const registrar = `WITH registrado AS (
 UPDATE public.f7_cotizaciones_envios SET estado=$5::text,chatwoot_message_id=$6::bigint,motivo=$7::text,updated_at=now()
 WHERE account_id=$1::bigint AND conversation_id=$2::bigint AND solicitud_id=$3::text
 AND owner_execution=$4::text AND estado IN ('reservado','enviando',$5::text) RETURNING 1
) SELECT EXISTS(SELECT 1 FROM registrado) AS recorded;`;
