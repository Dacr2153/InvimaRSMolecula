-- Evidencia aportada como enlace publico, no como archivo.
--
-- Buena parte de la evidencia que sustenta un dossier ya vive publicada y
-- citable: registros de ensayos clinicos, EPAR de EMA, fichas de Drugs@FDA.
-- Obligar a adjuntarla como PDF hace que el solicitante descargue y vuelva a
-- subir lo que ya tiene URL, y que el evaluador no pueda ir a la fuente.
--
-- El enlace es OPCIONAL y no reemplaza ningun documento obligatorio: es un
-- atajo de verificacion, no un sustituto del folio.

BEGIN;

CREATE TABLE IF NOT EXISTS enlaces_evidencia (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    solicitud_id UUID NOT NULL REFERENCES solicitudes(id) ON DELETE CASCADE,
    url          TEXT NOT NULL,
    titulo       TEXT NOT NULL DEFAULT '',
    -- Clasificacion derivada del dominio de la URL. Sirve para que el agente
    -- sepa que fuente esta mirando sin adivinar por el texto.
    tipo         TEXT NOT NULL DEFAULT 'OTRO'
                 CHECK (tipo IN ('ENSAYO_CLINICO','AGENCIA_REFERENCIA','PUBLICACION','OTRO')),
    -- Identificador extraido de la URL cuando aplica (por ejemplo el NCT).
    referencia   TEXT NOT NULL DEFAULT '',
    creado_en    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (solicitud_id, url)
);

CREATE INDEX IF NOT EXISTS ix_enlaces_solicitud ON enlaces_evidencia(solicitud_id);

COMMIT;
