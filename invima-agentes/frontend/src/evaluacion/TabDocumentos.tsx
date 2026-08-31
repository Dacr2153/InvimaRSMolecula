import { useState } from 'react';
import { VistaVacia } from '../components/EstadoCarga';
import { abreviarSha, formatearBytes, formatearFecha } from '../formato';
import type { DocumentoExpediente } from '../api/tipos';

export function TabDocumentos({ documentos }: { documentos: DocumentoExpediente[] }) {
  const [abiertos, setAbiertos] = useState<Record<string, boolean>>({});

  const alternar = (id: string) => setAbiertos((s) => ({ ...s, [id]: !s[id] }));

  return (
    <div className="pane--wide">
      <h2 className="tab__titulo">Documentos aportados por el solicitante</h2>
      <p className="tab__subtitulo">
        Dossier presentado por la farmacéutica en la radicación, incluyendo evidencia de que la molécula
        fue probada en otros países.
      </p>

      {documentos.length === 0 ? (
        <VistaVacia mensaje="El expediente no tiene documentos cargados." />
      ) : (
        documentos.map((d) => {
          const abierto = !!abiertos[d.requeridoId];
          return (
            <button
              type="button"
              key={d.requeridoId}
              className={`tarjeta-doc${abierto ? ' tarjeta-doc--abierta' : ''}`}
              aria-expanded={abierto}
              onClick={() => alternar(d.requeridoId)}
            >
              <div className="tarjeta-doc__cabecera">
                <span className="tarjeta-doc__nombre">{d.nombre}</span>
                <span className="doc-badge doc-badge--loaded">APORTADO</span>
              </div>
              <div className="tarjeta-doc__meta">
                {d.modulo} · {d.nombreArchivo} · {formatearBytes(d.tamanoBytes)} · Cargado{' '}
                {formatearFecha(d.cargadoEn)}
              </div>
              {abierto ? (
                <div className="tarjeta-doc__detalle">
                  <div className="tarjeta-doc__sha">
                    sha256 {abreviarSha(d.sha256)}
                    <span className="tarjeta-doc__sha-nota">prueba de integridad del folio</span>
                  </div>
                  <div className="tarjeta-doc__sha-completo">{d.sha256}</div>
                </div>
              ) : null}
            </button>
          );
        })
      )}
    </div>
  );
}
