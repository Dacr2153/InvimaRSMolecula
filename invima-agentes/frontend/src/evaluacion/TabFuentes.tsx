import { useCallback, useEffect, useState } from 'react';
import { obtenerFuentes, vincularFuente } from '../api/cliente';
import { Cargando, ErrorVista, VistaVacia } from '../components/EstadoCarga';
import type { FuenteExterna } from '../api/tipos';

type Props = { radicado: string; usuario: string };

export function TabFuentes({ radicado, usuario }: Props) {
  const [fuentes, setFuentes] = useState<FuenteExterna[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [intento, setIntento] = useState(0);
  const [enCurso, setEnCurso] = useState<string | null>(null);
  const [errorVinculo, setErrorVinculo] = useState<string | null>(null);

  const reintentar = useCallback(() => setIntento((n) => n + 1), []);

  useEffect(() => {
    let vivo = true;
    const controlador = new AbortController();
    setFuentes(null);
    setError(null);
    obtenerFuentes(radicado, controlador.signal)
      .then((r) => {
        if (vivo) setFuentes(r);
      })
      .catch((e: unknown) => {
        if (!vivo) return;
        if (e instanceof DOMException && e.name === 'AbortError') return;
        setError(e instanceof Error ? e.message : 'Error desconocido.');
      });
    return () => {
      vivo = false;
      controlador.abort();
    };
  }, [radicado, intento]);

  const alternarVinculo = async (f: FuenteExterna) => {
    setEnCurso(f.id);
    setErrorVinculo(null);
    try {
      const actualizada = await vincularFuente(radicado, f.id, !f.vinculada, usuario || 'sin identificar');
      setFuentes((prev) => (prev ? prev.map((x) => (x.id === f.id ? actualizada : x)) : prev));
    } catch (e) {
      setErrorVinculo(e instanceof Error ? e.message : 'No se pudo vincular la fuente.');
    } finally {
      setEnCurso(null);
    }
  };

  return (
    <div className="pane--wide">
      <h2 className="tab__titulo">Fuentes externas encontradas por el agente</h2>
      <p className="tab__subtitulo">
        Documentos regulatorios relacionados con la molécula, ubicados automáticamente en plataformas
        externas.
      </p>

      <div className="aviso aviso--warn mb-24">
        Resultados generados por el agente de búsqueda — requieren validación manual antes de usarse como
        evidencia.
      </div>

      {errorVinculo ? (
        <div className="aviso aviso--danger mb-24" role="alert">
          {errorVinculo}
        </div>
      ) : null}

      {error ? (
        <ErrorVista mensaje={error} onReintentar={reintentar} titulo="No se pudieron cargar las fuentes" />
      ) : fuentes === null ? (
        <Cargando mensaje="Consultando fuentes…" />
      ) : fuentes.length === 0 ? (
        <VistaVacia mensaje="El agente no reportó fuentes externas para esta molécula." />
      ) : (
        fuentes.map((f) => (
          <div className={`fuente${f.encontrada ? '' : ' fuente--no-encontrada'}`} key={f.id}>
            <div className="fuente__cabecera">
              <div>
                <span className="fuente__origen">{f.fuente}</span>
                <div className="fuente__titulo">{f.titulo}</div>
              </div>
              {f.encontrada ? (
                <button
                  type="button"
                  className={`btn-vincular${f.vinculada ? ' btn-vincular--activo' : ''}`}
                  aria-pressed={f.vinculada}
                  disabled={enCurso === f.id}
                  onClick={() => void alternarVinculo(f)}
                >
                  {enCurso === f.id ? 'Guardando…' : f.vinculada ? 'Vinculado ✓' : 'Vincular al expediente'}
                </button>
              ) : (
                <span className="fuente__etiqueta-sin">Sin consultar</span>
              )}
            </div>

            <div className="fuente__meta">
              {f.tipo} · País/región: {f.pais} · {f.fecha}
            </div>

            {f.encontrada ? null : (
              <div className="fuente__nota">
                No se consultó esta fuente: el sistema corrió sin acceso a red. Esto no es un hallazgo; solo
                se ofrece el enlace de consulta.
              </div>
            )}

            {f.observaciones ? <div className="fuente__observaciones">{f.observaciones}</div> : null}

            {f.url ? (
              <a className="fuente__enlace" href={f.url} target="_blank" rel="noreferrer noopener">
                Abrir la fuente en {f.fuente}
              </a>
            ) : null}
          </div>
        ))
      )}
    </div>
  );
}
