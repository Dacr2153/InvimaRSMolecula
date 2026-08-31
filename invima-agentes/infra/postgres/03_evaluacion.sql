-- Zona de evaluacion tecnica. Todo lo que el evaluador produce mientras estudia
-- un expediente: su checklist, las fuentes que decide vincular y sus consultas.
--
-- Nada de esto es una decision. La decision vive en expedientes.decision_humana
-- y solo la escribe RegistrarDecisionHumana, que exige nombre y timestamp.

BEGIN;

CREATE TABLE IF NOT EXISTS evaluadores (
    id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario  TEXT NOT NULL UNIQUE,
    nombre   TEXT NOT NULL,
    grupo    TEXT NOT NULL DEFAULT 'FARMACOLOGIA'
);

-- Criterios de verificacion. El evaluador parte de una plantilla y la ajusta:
-- por eso el texto se copia a la fila en vez de referenciar la plantilla.
CREATE TABLE IF NOT EXISTS checklist_items (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    radicado     TEXT NOT NULL REFERENCES expedientes(radicado) ON DELETE CASCADE,
    texto        TEXT NOT NULL,
    verificado   BOOLEAN NOT NULL DEFAULT FALSE,
    origen       TEXT NOT NULL DEFAULT 'PLANTILLA'
                 CHECK (origen IN ('PLANTILLA','EVALUADOR','AGENTE')),
    orden        INT NOT NULL DEFAULT 0,
    creado_en    TIMESTAMPTZ NOT NULL DEFAULT now(),
    verificado_por TEXT,
    verificado_en  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_checklist_radicado ON checklist_items(radicado, orden);

CREATE TABLE IF NOT EXISTS checklist_plantilla (
    id     TEXT PRIMARY KEY,
    texto  TEXT NOT NULL,
    orden  INT NOT NULL DEFAULT 0
);

-- Una fuente externa que el agente encontro. Se guarda tal como vino, con su
-- URL, y aparte si el evaluador la vinculo. Vincular es un acto del evaluador:
-- el agente propone, la persona incorpora.
CREATE TABLE IF NOT EXISTS fuentes_externas (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    radicado    TEXT NOT NULL REFERENCES expedientes(radicado) ON DELETE CASCADE,
    fuente      TEXT NOT NULL,
    titulo      TEXT NOT NULL,
    tipo        TEXT NOT NULL DEFAULT '',
    pais        TEXT NOT NULL DEFAULT '',
    fecha       TEXT NOT NULL DEFAULT '',
    url         TEXT NOT NULL DEFAULT '',
    encontrada  BOOLEAN NOT NULL DEFAULT TRUE,
    observaciones TEXT NOT NULL DEFAULT '',
    vinculada     BOOLEAN NOT NULL DEFAULT FALSE,
    vinculada_por TEXT,
    vinculada_en  TIMESTAMPTZ,
    UNIQUE (radicado, fuente, titulo)
);

CREATE INDEX IF NOT EXISTS ix_fuentes_radicado ON fuentes_externas(radicado);

-- Corpus normativo para la pestana de consultas. Recupera y cita; no genera
-- criterio. Cada respuesta obliga a mostrar de donde salio.
CREATE TABLE IF NOT EXISTS corpus_normativo (
    id        TEXT PRIMARY KEY,
    pregunta  TEXT NOT NULL,
    respuesta TEXT NOT NULL,
    cita      TEXT NOT NULL,
    url       TEXT NOT NULL DEFAULT '',
    etiquetas TEXT NOT NULL DEFAULT '',
    sugerida  BOOLEAN NOT NULL DEFAULT FALSE,
    orden     INT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS consultas (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    radicado   TEXT NOT NULL REFERENCES expedientes(radicado) ON DELETE CASCADE,
    usuario    TEXT NOT NULL DEFAULT '',
    pregunta   TEXT NOT NULL,
    respuesta  TEXT NOT NULL,
    cita       TEXT NOT NULL DEFAULT '',
    url        TEXT NOT NULL DEFAULT '',
    encontrada BOOLEAN NOT NULL DEFAULT TRUE,
    momento    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_consultas_radicado ON consultas(radicado, momento);

COMMIT;
