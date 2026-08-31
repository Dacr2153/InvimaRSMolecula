-- Informes de los agentes secundarios (A2, A3, A4) por expediente.
--
-- El A1 corre inline durante la radicacion porque el enrutamiento depende de el.
-- Los otros tres corren en segundo plano: su trabajo alimenta la evaluacion, no
-- el reparto, y no tiene sentido retener al solicitante mientras terminan.
--
-- Cada fila es la corrida de UN agente sobre UN radicado. El evaluador ve el
-- estado avanzar (PENDIENTE -> EN_EJECUCION -> COMPLETADO / ERROR / OMITIDO) y
-- el payload completo queda para lectura y auditoria. OMITIDO no es un fallo:
-- significa que el expediente no trae el modulo que ese agente audita, y eso
-- tambien es informacion para el evaluador.

BEGIN;

CREATE TABLE IF NOT EXISTS informes_agentes (
    radicado      TEXT NOT NULL REFERENCES expedientes(radicado) ON DELETE CASCADE,
    agente        TEXT NOT NULL,
    nombre        TEXT NOT NULL DEFAULT '',
    estado        TEXT NOT NULL DEFAULT 'PENDIENTE'
                  CHECK (estado IN ('PENDIENTE','EN_EJECUCION','COMPLETADO','ERROR','OMITIDO')),
    iniciado_en   TIMESTAMPTZ,
    terminado_en  TIMESTAMPTZ,
    duracion_ms   INTEGER,
    modelo        TEXT NOT NULL DEFAULT '',
    resumen       JSONB NOT NULL DEFAULT '{}'::jsonb,
    payload       JSONB NOT NULL DEFAULT '{}'::jsonb,
    error         TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (radicado, agente)
);

-- Folios que alimentan a los agentes de evidencia. Sin esto, los Modulos 4, 5
-- y el PGR se archivan como adjuntos y el A4 no tiene nada que leer.
UPDATE documentos_requeridos SET folio_destino = 'modulo4_evidencia'
 WHERE id = 'm4-toxico' AND folio_destino IS NULL;
UPDATE documentos_requeridos SET folio_destino = 'modulo5_evidencia'
 WHERE id = 'm5-eficacia' AND folio_destino IS NULL;
UPDATE documentos_requeridos SET folio_destino = 'modulo7_pgr'
 WHERE id = 'pgr-plan' AND folio_destino IS NULL;

COMMIT;
