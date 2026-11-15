// Registro aislado: nunca modifica session_state, memoria, precios ni media.
export const schema=`CREATE TABLE IF NOT EXISTS public.f7_derivaciones (
 account_id bigint NOT NULL CHECK(account_id=1), conversation_id bigint NOT NULL CHECK(conversation_id>0),
 solicitud_id text NOT NULL, owner_execution text NOT NULL,
 motivo text NOT NULL CHECK(motivo IN ('avance_compra','pago','turno','persona','posventa','revision_especial')),
 estado text NOT NULL CHECK(estado IN ('reservado','enviando','finalizado')),
 resultado jsonb, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(account_id,conversation_id,solicitud_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS f7_derivaciones_una_en_curso ON public.f7_derivaciones(account_id,conversation_id) WHERE estado IN ('reservado','enviando');
ALTER TABLE public.f7_derivaciones ENABLE ROW LEVEL SECURITY;
SELECT true AS ready;`;
export const reservar=`WITH nueva AS (
 INSERT INTO public.f7_derivaciones(account_id,conversation_id,solicitud_id,owner_execution,motivo,estado)
 VALUES($1::bigint,$2::bigint,$3::text,$4::text,$5::text,'reservado')
 ON CONFLICT DO NOTHING RETURNING *
)
SELECT true AS acquired,true AS compatible,estado,resultado FROM nueva
UNION ALL
SELECT false AS acquired,motivo=$5::text AND solicitud_id=$3::text AS compatible,estado,resultado
FROM (SELECT * FROM public.f7_derivaciones
 WHERE account_id=$1::bigint AND conversation_id=$2::bigint
 AND (solicitud_id=$3::text OR estado IN ('reservado','enviando'))
 ORDER BY (solicitud_id=$3::text) DESC LIMIT 1
) existente WHERE NOT EXISTS(SELECT 1 FROM nueva);`;
export const marcarEnvio=`WITH marcado AS (
 UPDATE public.f7_derivaciones SET estado='enviando',resultado=$5::jsonb,updated_at=now()
 WHERE account_id=$1::bigint AND conversation_id=$2::bigint AND solicitud_id=$3::text
 AND owner_execution=$4::text AND estado='reservado' RETURNING 1
) SELECT EXISTS(SELECT 1 FROM marcado) AS enabled;`;
export const registrar=`WITH registrado AS (
 UPDATE public.f7_derivaciones SET estado='finalizado',resultado=$5::jsonb,updated_at=now()
 WHERE account_id=$1::bigint AND conversation_id=$2::bigint AND solicitud_id=$3::text
 AND owner_execution=$4::text AND (estado IN ('reservado','enviando') OR (estado='finalizado' AND resultado=$5::jsonb)) RETURNING 1
) SELECT EXISTS(SELECT 1 FROM registrado) AS recorded;`;
