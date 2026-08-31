-- Esquema del sistema de radicacion de Registro Sanitario de Molecula.
--
-- Dos zonas con reglas distintas:
--
--   1. La zona de RADICACION (solicitudes, documentos, pagos) es mutable: el
--      solicitante arma su expediente y lo corrige hasta que radica.
--   2. La zona de EXPEDIENTE (expedientes, eventos_auditoria) es el registro
--      administrativo. `eventos_auditoria` es append-only por trigger: no se
--      actualiza ni se borra, ni siquiera por el dueno de la base.
--
-- El campo `payload` de expedientes guarda el JSON completo que produce el A1,
-- con el `origen` y la `traza` de cada dato. No se normaliza a columnas a
-- proposito: el payload es la unidad que el evaluador lee y que debe poder
-- reconstruirse identica anos despues.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------- catalogos --

CREATE TABLE IF NOT EXISTS tipos_tramite (
    id          TEXT PRIMARY KEY,
    etiqueta    TEXT NOT NULL,
    descripcion TEXT NOT NULL DEFAULT '',
    orden       INT  NOT NULL DEFAULT 0,
    activo      BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS tipos_producto (
    id          TEXT PRIMARY KEY,
    etiqueta    TEXT NOT NULL,
    descripcion TEXT NOT NULL DEFAULT '',
    orden       INT  NOT NULL DEFAULT 0,
    activo      BOOLEAN NOT NULL DEFAULT TRUE
);

-- Espejo de data/referencia/tarifas.csv. La fuente de verdad sigue siendo el
-- CSV que lee el motor de validacion: aqui se replica solo para que el
-- solicitante pueda escoger el codigo en el formulario.
CREATE TABLE IF NOT EXISTS tarifas (
    codigo   TEXT PRIMARY KEY,
    concepto TEXT NOT NULL,
    valor    NUMERIC(14,2) NOT NULL,
    vigencia INT NOT NULL DEFAULT 2026
);

CREATE TABLE IF NOT EXISTS metodos_pago (
    id       TEXT PRIMARY KEY,
    etiqueta TEXT NOT NULL,
    orden    INT NOT NULL DEFAULT 0
);

-- Estructura documental CTD. Define que se le pide al solicitante en el paso 3.
CREATE TABLE IF NOT EXISTS modulos_ctd (
    id       TEXT PRIMARY KEY,
    titulo   TEXT NOT NULL,
    orden    INT  NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS documentos_requeridos (
    id            TEXT PRIMARY KEY,
    modulo_id     TEXT NOT NULL REFERENCES modulos_ctd(id),
    nombre        TEXT NOT NULL,
    obligatorio   BOOLEAN NOT NULL DEFAULT TRUE,
    orden         INT NOT NULL DEFAULT 0,
    -- Nombre del folio que el parser espera dentro de la carpeta del dossier.
    -- Null = el documento se adjunta pero no alimenta al A1 todavia.
    folio_destino TEXT
);

-- --------------------------------------------------------------- solicitante --

CREATE TABLE IF NOT EXISTS solicitantes (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    razon_social TEXT NOT NULL,
    nit          TEXT NOT NULL UNIQUE,
    correo       TEXT NOT NULL DEFAULT '',
    creado_en    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------- radicacion --

-- Una solicitud en construccion. Vive mientras el solicitante llena el wizard.
-- Al radicar se congela (estado RADICADA) y nace el expediente.
CREATE TABLE IF NOT EXISTS solicitudes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    solicitante_id  UUID NOT NULL REFERENCES solicitantes(id),
    estado          TEXT NOT NULL DEFAULT 'BORRADOR'
                    CHECK (estado IN ('BORRADOR','RADICADA','ANULADA')),
    tipo_tramite    TEXT REFERENCES tipos_tramite(id),
    tipo_producto   TEXT REFERENCES tipos_producto(id),

    -- Paso 2: lo que el solicitante DECLARA. No es lo que el agente extrae.
    -- La diferencia entre ambos es justamente lo que se le muestra al evaluador.
    datos_declarados JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Paso 4
    tarifa_codigo   TEXT REFERENCES tarifas(codigo),
    metodo_pago     TEXT REFERENCES metodos_pago(id),
    comprobante     TEXT,
    valor_pagado    NUMERIC(14,2),
    fecha_pago      DATE,

    radicado        TEXT UNIQUE,
    radicada_en     TIMESTAMPTZ,
    creada_en       TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizada_en  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_solicitudes_solicitante ON solicitudes(solicitante_id);
CREATE INDEX IF NOT EXISTS ix_solicitudes_estado ON solicitudes(estado);

-- Un archivo cargado contra una casilla del checklist documental.
CREATE TABLE IF NOT EXISTS documentos_cargados (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    solicitud_id   UUID NOT NULL REFERENCES solicitudes(id) ON DELETE CASCADE,
    requerido_id   TEXT NOT NULL REFERENCES documentos_requeridos(id),
    nombre_archivo TEXT NOT NULL,
    ruta_relativa  TEXT NOT NULL,
    tamano_bytes   BIGINT NOT NULL,
    tipo_mime      TEXT NOT NULL DEFAULT 'application/octet-stream',
    -- SHA-256 del contenido. Permite probar anos despues que el folio evaluado
    -- es byte por byte el que se radico.
    sha256         TEXT NOT NULL,
    cargado_en     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (solicitud_id, requerido_id)
);

CREATE INDEX IF NOT EXISTS ix_documentos_solicitud ON documentos_cargados(solicitud_id);

-- ---------------------------------------------------------------- expediente --

-- Espejo exacto de RepositorioExpedientePort. Las mismas columnas que el
-- adaptador SQLite, para que cambiar de motor sea cambiar de adaptador.
CREATE TABLE IF NOT EXISTS expedientes (
    radicado          TEXT PRIMARY KEY,
    solicitud_id      UUID REFERENCES solicitudes(id),
    fecha_radicacion  DATE NOT NULL,
    estado            TEXT NOT NULL,
    decision_humana   JSONB,
    eventos           JSONB NOT NULL DEFAULT '[]'::jsonb,
    payload           JSONB NOT NULL DEFAULT '{}'::jsonb,
    carpeta_dossier   TEXT NOT NULL DEFAULT '',
    actualizado_en    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_expedientes_estado ON expedientes(estado);

-- Bitacora append-only. Es el equivalente en base de data/auditoria.jsonl.
CREATE TABLE IF NOT EXISTS eventos_auditoria (
    id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    momento   TIMESTAMPTZ NOT NULL DEFAULT now(),
    radicado  TEXT NOT NULL,
    tipo      TEXT NOT NULL,
    accion    TEXT NOT NULL,
    resultado TEXT NOT NULL,
    actor     TEXT NOT NULL DEFAULT 'SISTEMA',
    detalles  JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS ix_eventos_radicado ON eventos_auditoria(radicado, momento);

-- La trazabilidad no sirve si se puede editar. El trigger lo impide a nivel de
-- motor, no de aplicacion: aunque alguien entre por psql con el rol dueno, un
-- UPDATE o un DELETE sobre la bitacora falla.
CREATE OR REPLACE FUNCTION bitacora_inmutable() RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION
        'eventos_auditoria es append-only: % no esta permitido sobre la bitacora '
        '(trazabilidad exigida por el art. 7.3, Resolucion 2026025611)', TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tg_bitacora_inmutable ON eventos_auditoria;
CREATE TRIGGER tg_bitacora_inmutable
    BEFORE UPDATE OR DELETE ON eventos_auditoria
    FOR EACH ROW EXECUTE FUNCTION bitacora_inmutable();

COMMIT;
