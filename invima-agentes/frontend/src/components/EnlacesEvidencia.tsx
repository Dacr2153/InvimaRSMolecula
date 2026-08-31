import { useState } from 'react';
import { agregarEnlace, eliminarEnlace } from '../api/cliente';
import type { EnlaceEvidencia } from '../api/tipos';

type Props = {
  solicitudId: string;
  enlaces: EnlaceEvidencia[];
  onCambio: (enlaces: EnlaceEvidencia[]) => void;
};

const ETIQUETA_TIPO: Record<string, string> = {
  ENSAYO_CLINICO: 'Ensayo clínico',
  AGENCIA_REFERENCIA: 'Agencia de referencia',
  PUBLICACION: 'Publicación',
  OTRO: 'Otra fuente',
};

// Evidencia que ya esta publicada y citable no deberia tener que descargarse y
// volverse a subir: el enlace le ahorra tiempo al solicitante, le da al evaluador
// la fuente original, y el agente verifica solo los identificadores que trae.
export function EnlacesEvidencia({ solicitudId, enlaces, onCambio }: Props) {
  const [url, setUrl] = useState('');
  const [titulo, setTitulo] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const agregar = async () => {
    const limpia = url.trim();
    if (!limpia) return;
    setEnviando(true);
    setError(null);
    try {
      const nuevo = await agregarEnlace(solicitudId, limpia, titulo.trim());
      onCambio([...enlaces.filter((e) => e.url !== nuevo.url), nuevo]);
      setUrl('');
      setTitulo('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo agregar el enlace.');
    } finally {
      setEnviando(false);
    }
  };

  const quitar = async (id: string) => {
    setError(null);
    try {
      await eliminarEnlace(solicitudId, id);
      onCambio(enlaces.filter((e) => e.id !== id));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo eliminar el enlace.');
    }
  };

  return (
    <div className="doc-group">
      <div className="doc-group__title">
        Evidencia por enlace <span className="chip chip--opcional">Opcional</span>
      </div>
      <p className="pane__subtitle pane__subtitle--tight">
        Si parte de la evidencia ya está publicada, basta con el enlace: no hace falta
        descargarla y volverla a subir. El evaluador llega a la fuente original y los
        identificadores de estudio se verifican automáticamente.
      </p>

      <div className="enlaces__form">
        <input
          className="input"
          type="url"
          value={url}
          placeholder="https://clinicaltrials.gov/study/NCT01204333"
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              void agregar();
            }
          }}
          aria-label="Enlace de evidencia"
        />
        <input
          className="input input--corto"
          type="text"
          value={titulo}
          placeholder="Descripción (opcional)"
          onChange={(e) => setTitulo(e.target.value)}
          aria-label="Descripción del enlace"
        />
        <button
          type="button"
          className="btn btn--secundario"
          onClick={() => void agregar()}
          disabled={enviando || !url.trim()}
        >
          {enviando ? 'Agregando…' : 'Agregar'}
        </button>
      </div>

      {error ? <div className="aviso aviso--error mt-8">{error}</div> : null}

      {enlaces.length === 0 ? (
        <p className="enlaces__vacio">Sin enlaces. Este apartado es opcional.</p>
      ) : (
        <ul className="enlaces__lista">
          {enlaces.map((e) => (
            <li className="enlaces__item" key={e.id}>
              <div className="enlaces__datos">
                <span className="chip">{ETIQUETA_TIPO[e.tipo] ?? e.tipo}</span>
                <a className="enlaces__url" href={e.url} target="_blank" rel="noreferrer">
                  {e.titulo || e.url}
                </a>
                {e.referencia ? <code className="enlaces__ref">{e.referencia}</code> : null}
              </div>
              <button
                type="button"
                className="btn btn--texto"
                onClick={() => void quitar(e.id)}
                aria-label={`Quitar ${e.titulo || e.url}`}
              >
                Quitar
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
