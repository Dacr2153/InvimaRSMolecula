-- Amplia que folios del expediente alimentan al agente A1.
--
-- Hasta aqui solo tres documentos tenian folio_destino, y entre ellos NO estaba
-- el certificado BPM/CPP. Eso dejaba al agente sin ver el CPP de MHRA ni las
-- aprobaciones de agencias de referencia, que son justamente el insumo del
-- reliance regulatorio: el agente contrastaba contra lo que el solicitante
-- declaro en el formulario, no contra el certificado que lo respalda.
--
-- Se agregan los folios del Modulo 1 y el comprobante de pago. Los modulos 2 a 5
-- se dejan como adjuntos a proposito: son insumo de los agentes de calidad y
-- evidencia clinica, y meterlos aqui solo inflaria el prompt del A1 sin que los
-- use.

BEGIN;

UPDATE documentos_requeridos SET folio_destino = 'modulo1_poder'
 WHERE id = 'm1-poder' AND folio_destino IS NULL;

UPDATE documentos_requeridos SET folio_destino = 'modulo1_bpm_cpp'
 WHERE id = 'm1-bpm' AND folio_destino IS NULL;

UPDATE documentos_requeridos SET folio_destino = 'modulo1_pago'
 WHERE id = 'pago-comprobante' AND folio_destino IS NULL;

COMMIT;
