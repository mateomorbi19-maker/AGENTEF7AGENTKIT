// SQL parametrizado. Importar este módulo no ejecuta DB ni red.
// epoch es el ID decimal del último comando; '0' es la sesión inicial de la conversación (desde 2026-11-06 ya no usa el teléfono como key).
// No se elimina memoria física: la nueva key desvincula el historial anterior.
// listo habilita eventos posteriores; no acredita entrega del ACK.
// Un ACK enviando/desconocido no se reintenta automáticamente.
export const SCHEMA = `-- Reinicio de contexto comercial; no elimina chats ni evidencia histórica.
CREATE TABLE IF NOT EXISTS public.f7_reinicios_conversacion (
  account_id bigint NOT NULL CHECK (account_id = 1),
  conversation_id bigint NOT NULL CHECK (conversation_id > 0),
  epoch text NOT NULL CHECK (epoch ~ '^[1-9][0-9]{0,31}$'),
  previous_epoch text NOT NULL DEFAULT '0' CHECK (previous_epoch ~ '^(0|[1-9][0-9]{0,31})$'),
  owner_execution text NOT NULL CHECK (length(owner_execution) BETWEEN 1 AND 200),
  listo boolean NOT NULL DEFAULT false,
  ack_estado text NOT NULL DEFAULT 'pendiente' CHECK (ack_estado IN ('pendiente','enviando','aceptado','fallido','desconocido')),
  ack_message_id bigint,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (account_id, conversation_id),
  CHECK (previous_epoch::numeric < epoch::numeric),
  CHECK ((ack_estado = 'aceptado' AND ack_message_id IS NOT NULL AND ack_message_id > 0) OR (ack_estado <> 'aceptado' AND ack_message_id IS NULL)),
  CHECK ((NOT listo AND ack_estado = 'pendiente') OR (listo AND ack_estado <> 'pendiente'))
);
ALTER TABLE public.f7_reinicios_conversacion ENABLE ROW LEVEL SECURITY;

-- La lectura posterior al UPSERT usa un snapshot nuevo en READ COMMITTED.
-- Evita el vacío posible de INSERT ON CONFLICT + SELECT en un mismo CTE.
CREATE OR REPLACE FUNCTION public.f7_recibir_evento_reinicio(
  p_account_id bigint, p_conversation_id bigint, p_message_id text,
  p_telefono text, p_es_comando boolean, p_owner_execution text
) RETURNS TABLE (
  epoch text, previous_epoch text, session_key text, buffer_key text, lock_key text,
  previous_buffer_key text, es_comando boolean, aplicar_reinicio boolean, vigente boolean, listo boolean
) LANGUAGE plpgsql VOLATILE SECURITY INVOKER
SET search_path = pg_catalog, public
AS $f7_reinicio$
DECLARE
  estado public.f7_reinicios_conversacion%ROWTYPE;
  aplicado boolean := false;
  prefijo text;
  sufijo text;
BEGIN
  IF p_account_id IS DISTINCT FROM 1 OR p_conversation_id IS NULL OR p_conversation_id <= 0
    OR p_message_id IS NULL OR p_message_id !~ '^[1-9][0-9]{0,31}$'
    OR p_telefono IS NULL OR length(p_telefono) = 0
    OR p_es_comando IS NULL OR p_owner_execution IS NULL
    OR length(p_owner_execution) NOT BETWEEN 1 AND 200 THEN
    RAISE EXCEPTION 'Entrada de reinicio inválida' USING ERRCODE = '22023';
  END IF;

  IF p_es_comando THEN
    INSERT INTO public.f7_reinicios_conversacion AS destino
      (account_id, conversation_id, epoch, previous_epoch, owner_execution)
    VALUES (p_account_id, p_conversation_id, p_message_id, '0', p_owner_execution)
    ON CONFLICT (account_id, conversation_id) DO UPDATE SET
      previous_epoch = destino.epoch,
      epoch = EXCLUDED.epoch,
      owner_execution = EXCLUDED.owner_execution,
      listo = false,
      ack_estado = 'pendiente',
      ack_message_id = NULL,
      updated_at = now()
    WHERE EXCLUDED.epoch::numeric > destino.epoch::numeric
    RETURNING destino.* INTO estado;
    aplicado := FOUND;
  END IF;

  IF NOT aplicado THEN
    SELECT r.* INTO estado FROM public.f7_reinicios_conversacion r
    WHERE r.account_id = p_account_id AND r.conversation_id = p_conversation_id;
  END IF;

  epoch := COALESCE(estado.epoch, '0');
  previous_epoch := COALESCE(estado.previous_epoch, '0');
  prefijo := 'f7:unificado:v1:' || p_account_id::text || ':' || p_conversation_id::text;
  sufijo := CASE WHEN epoch = '0' THEN '' ELSE ':epoch:' || epoch END;
  -- Sin reset la memoria también es propia de la conversación: no se lee el historial por teléfono de bots anteriores.
  session_key := prefijo || ':memoria:' || epoch;
  buffer_key := prefijo || ':buffer' || sufijo;
  lock_key := prefijo || ':lock' || sufijo;
  previous_buffer_key := prefijo || ':buffer' || CASE WHEN previous_epoch = '0' THEN '' ELSE ':epoch:' || previous_epoch END;
  es_comando := p_es_comando;
  aplicar_reinicio := aplicado;
  vigente := CASE WHEN p_es_comando THEN p_message_id = epoch ELSE p_message_id::numeric > epoch::numeric END;
  listo := COALESCE(estado.listo, true);
  RETURN NEXT;
END;
$f7_reinicio$;
SELECT true AS ready;`;
// $1 cuenta, $2 conversación, $3 message ID, $4 teléfono, $5 comando, $6 ejecución.
export const RECIBIR_EVENTO = `SELECT * FROM public.f7_recibir_evento_reinicio(
  $1::bigint, $2::bigint, $3::text, $4::text, $5::boolean, $6::text
);`;
// $1 cuenta, $2 conversación, $3 message ID original. Nunca usar un ID del modelo.
// posterior permite encolar durante un reset; permitido exige además listo para consumir/actuar.
export const VIGENCIA = `WITH actual AS (
  SELECT epoch, listo FROM public.f7_reinicios_conversacion
  WHERE account_id = $1::bigint AND conversation_id = $2::bigint
), estado AS (
  SELECT COALESCE((SELECT epoch FROM actual), '0') AS epoch,
    COALESCE((SELECT listo FROM actual), true) AS listo
), corte AS (
  SELECT CASE WHEN $1::bigint = 1 AND $2::bigint > 0
      AND $3::text ~ '^[1-9][0-9]{0,31}$'
    THEN $3::numeric > epoch::numeric ELSE false END AS posterior,
    epoch, listo
  FROM estado
)
SELECT posterior AND listo AS permitido, posterior, epoch, listo
FROM corte;`;
// $1 cuenta, $2 conversación, $3 reset ID, $4 ejecución dueña. Reclama ACK una sola vez.
export const MARCAR_LISTO = `WITH marcado AS (
  UPDATE public.f7_reinicios_conversacion
  SET listo = true, ack_estado = 'enviando', updated_at = now()
  WHERE account_id = $1::bigint AND conversation_id = $2::bigint
    AND epoch = $3::text AND owner_execution = $4::text
    AND listo = false AND ack_estado = 'pendiente'
  RETURNING 1
)
SELECT EXISTS (SELECT 1 FROM marcado) AS enabled;`;
// $1..$4 como MARCAR_LISTO; $5 aceptado|fallido|desconocido, $6 ID positivo sólo si aceptado.
export const REGISTRAR_ACK = `WITH registrado AS (
  UPDATE public.f7_reinicios_conversacion
  SET ack_estado = $5::text, ack_message_id = $6::bigint, updated_at = now()
  WHERE account_id = $1::bigint AND conversation_id = $2::bigint
    AND epoch = $3::text AND owner_execution = $4::text AND listo = true
    AND $5::text IN ('aceptado','fallido','desconocido')
    AND (($5::text = 'aceptado' AND $6::bigint > 0)
      OR ($5::text <> 'aceptado' AND $6::bigint IS NULL))
    AND (ack_estado = 'enviando'
      OR (ack_estado = $5::text AND ack_message_id IS NOT DISTINCT FROM $6::bigint))
  RETURNING 1
)
SELECT EXISTS (SELECT 1 FROM registrado) AS recorded;`;

