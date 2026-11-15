/**
 * Registro aislado de la herramienta multimedia. Consultas parametrizadas; nunca
 * interpolar datos del modelo dentro del SQL. Todos los tiempos los decide Postgres.
 * No se ejecuta ninguna consulta al importar este módulo.
 *
 * El lock dura 900 s y el workflow debe terminar antes (timeout configurado 480 s).
 * Una ejecución que cae entre POST y registro deja `enviando`: requiere conciliación.
 * Ni el lease vencido ni un nuevo owner autorizan repetir ese POST incierto.
 */
export const schema = `
CREATE TABLE IF NOT EXISTS public.f7_multimedia_locks (
  account_id bigint NOT NULL CHECK (account_id = 1),
  conversation_id bigint NOT NULL CHECK (conversation_id > 0),
  owner text NOT NULL,
  expires_at timestamptz NOT NULL,
  PRIMARY KEY (account_id, conversation_id)
);
CREATE TABLE IF NOT EXISTS public.f7_multimedia_solicitudes (
  account_id bigint NOT NULL CHECK (account_id = 1),
  conversation_id bigint NOT NULL CHECK (conversation_id > 0),
  solicitud_id text NOT NULL,
  fingerprint jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  PRIMARY KEY (account_id, conversation_id, solicitud_id)
);
CREATE TABLE IF NOT EXISTS public.f7_multimedia_envios (
  account_id bigint NOT NULL CHECK (account_id = 1),
  conversation_id bigint NOT NULL CHECK (conversation_id > 0),
  solicitud_id text NOT NULL,
  asset_id text NOT NULL,
  version text NOT NULL,
  owner text NOT NULL,
  estado text NOT NULL CHECK (estado IN ('reservado','enviando','aceptado','fallo_previo','fallido','desconocido')),
  chatwoot_message_id bigint,
  motivo varchar(160),
  intentos integer NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW(),
  PRIMARY KEY (account_id, conversation_id, solicitud_id, asset_id, version),
  FOREIGN KEY (account_id, conversation_id, solicitud_id)
    REFERENCES public.f7_multimedia_solicitudes(account_id, conversation_id, solicitud_id),
  CHECK (estado <> 'aceptado' OR (chatwoot_message_id IS NOT NULL AND chatwoot_message_id > 0))
);
ALTER TABLE public.f7_multimedia_locks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.f7_multimedia_solicitudes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.f7_multimedia_envios ENABLE ROW LEVEL SECURITY;
SELECT true AS ready;
`;

/** $1 account_id, $2 conversation_id, $3 owner (execution ID confiable). */
export const acquireLock = `
WITH claimed AS (
  INSERT INTO public.f7_multimedia_locks AS target (account_id, conversation_id, owner, expires_at)
  VALUES ($1::bigint, $2::bigint, $3::text, NOW() + INTERVAL '900 seconds')
  ON CONFLICT (account_id, conversation_id) DO UPDATE
    SET owner = EXCLUDED.owner, expires_at = EXCLUDED.expires_at
    WHERE target.expires_at <= NOW() OR target.owner = EXCLUDED.owner
  RETURNING owner, expires_at
)
SELECT EXISTS(SELECT 1 FROM claimed) AS acquired,
  (SELECT owner FROM claimed) AS owner,
  (SELECT expires_at FROM claimed) AS expires_at;
`;

/** $1 account_id, $2 conversation_id, $3 solicitud_id, $4 owner, $5 fingerprint JSON. */
export const registerRequest = `
WITH registered AS (
  INSERT INTO public.f7_multimedia_solicitudes AS target (account_id, conversation_id, solicitud_id, fingerprint)
  SELECT $1::bigint, $2::bigint, $3::text, $5::jsonb
  WHERE EXISTS (
    SELECT 1 FROM public.f7_multimedia_locks
    WHERE account_id=$1::bigint AND conversation_id=$2::bigint AND owner=$4::text AND expires_at>NOW()
  )
  ON CONFLICT (account_id, conversation_id, solicitud_id) DO UPDATE
    SET fingerprint = target.fingerprint
  RETURNING fingerprint = $5::jsonb AS compatible
)
SELECT COALESCE((SELECT compatible FROM registered), false) AS compatible;
`;

/** $1 account_id, $2 conversation_id, $3 solicitud_id, $4 asset_id, $5 version, $6 owner. */
export const claimAsset = `
WITH claimed AS (
  INSERT INTO public.f7_multimedia_envios AS target
    (account_id, conversation_id, solicitud_id, asset_id, version, owner, estado)
  SELECT $1::bigint, $2::bigint, $3::text, $4::text, $5::text, $6::text, 'reservado'
  WHERE EXISTS (
    SELECT 1 FROM public.f7_multimedia_locks
    WHERE account_id=$1::bigint AND conversation_id=$2::bigint AND owner=$6::text AND expires_at>NOW()
  )
  ON CONFLICT (account_id, conversation_id, solicitud_id, asset_id, version) DO UPDATE
    SET owner=EXCLUDED.owner, estado='reservado', chatwoot_message_id=NULL, motivo=NULL,
        intentos=target.intentos+1, updated_at=NOW()
    WHERE target.estado='fallo_previo'
  RETURNING estado, chatwoot_message_id
)
SELECT EXISTS(SELECT 1 FROM claimed) AS acquired,
  COALESCE((SELECT estado FROM claimed),
    (SELECT estado FROM public.f7_multimedia_envios WHERE account_id=$1::bigint AND conversation_id=$2::bigint AND solicitud_id=$3::text AND asset_id=$4::text AND version=$5::text),
    'sin_registro') AS estado,
  (SELECT chatwoot_message_id FROM public.f7_multimedia_envios WHERE account_id=$1::bigint AND conversation_id=$2::bigint AND solicitud_id=$3::text AND asset_id=$4::text AND version=$5::text) AS chatwoot_message_id;
`;

/** Mismos seis parámetros de claimAsset. Se confirma ANTES de hacer el POST. */
export const markSending = `
WITH marked AS (
  UPDATE public.f7_multimedia_envios
  SET estado='enviando', updated_at=NOW()
  WHERE account_id=$1::bigint AND conversation_id=$2::bigint AND solicitud_id=$3::text
    AND asset_id=$4::text AND version=$5::text AND owner=$6::text AND estado='reservado'
    AND EXISTS (
      SELECT 1 FROM public.f7_multimedia_locks
      WHERE account_id=$1::bigint AND conversation_id=$2::bigint AND owner=$6::text AND expires_at>NOW()
    )
  RETURNING 1
)
SELECT EXISTS(SELECT 1 FROM marked) AS enabled;
`;

/**
 * $1..$6 como claimAsset, $7 estado, $8 message_id/null, $9 motivo propio/null.
 * fallo_previo solo desde reservado; después del POST, toda falla es terminal o incierta.
 * Repetir la escritura con el mismo resultado es seguro si se perdió la respuesta SQL.
 */
export const recordResult = `
WITH recorded AS (
  UPDATE public.f7_multimedia_envios
  SET estado=$7::text, chatwoot_message_id=$8::bigint, motivo=LEFT($9::text,160), updated_at=NOW()
  WHERE account_id=$1::bigint AND conversation_id=$2::bigint AND solicitud_id=$3::text
    AND asset_id=$4::text AND version=$5::text AND owner=$6::text
    AND $7::text IN ('aceptado','fallo_previo','fallido','desconocido')
    AND ($7::text<>'aceptado' OR $8::bigint>0)
    AND (
      (estado='reservado' AND $7::text='fallo_previo') OR
      (estado='enviando' AND $7::text IN ('aceptado','fallido','desconocido')) OR
      (estado=$7::text AND chatwoot_message_id IS NOT DISTINCT FROM $8::bigint)
    )
    AND EXISTS (
      SELECT 1 FROM public.f7_multimedia_locks
      WHERE account_id=$1::bigint AND conversation_id=$2::bigint AND owner=$6::text AND expires_at>NOW()
    )
  RETURNING 1
)
SELECT EXISTS(SELECT 1 FROM recorded) AS recorded;
`;

/** $1 account_id, $2 conversation_id, $3 owner. Nunca libera el lock de otra ejecución. */
export const releaseLock = `
WITH released AS (
  DELETE FROM public.f7_multimedia_locks
  WHERE account_id=$1::bigint AND conversation_id=$2::bigint AND owner=$3::text
  RETURNING 1
)
SELECT EXISTS(SELECT 1 FROM released) AS released;
`;
