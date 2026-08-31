import { useCallback, useEffect, useState } from 'react';
import { crearConsulta, obtenerConsultas, obtenerConsultasSugeridas } from '../api/cliente';
import { Cargando, ErrorVista } from '../components/EstadoCarga';
import type { Consulta, ConsultaSugerida } from '../api/tipos';

type Props = { radicado: string; usuario: string };

export function TabConsultas({ radicado, usuario }: Props) {
  const [sugeridas, setSugeridas] = useState<ConsultaSugerida[]>([]);
  const [hilo, setHilo] = useState<Consulta[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorPregunta, setErrorPregunta] = useState<string | null>(null);
  const [intento, setIntento] = useState(0);
  const [texto, setTexto] = useState('');
  const [preguntando, setPreguntando] = useState(false);

  const reintentar = useCallback(() => setIntento((n) => n + 1), []);

  useEffect(() => {
    let vivo = true;
    const controlador = new AbortController();
    setHilo(null);
    setError(null);
    Promise.all([
      obtenerConsultas(radicado, controlador.signal),
      obtenerConsultasSugeridas(controlador.signal).catch(() => [] as ConsultaSugerida[]),
    ])
      .then(([consultas, chips]) => {
        if (!vivo) return;
        setHilo(consultas);
        setSugeridas(chips);
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

  const preguntar = async (pregunta: string) => {
    const limpia = pregunta.trim();
    if (!limpia) return;
    setPreguntando(true);
    setErrorPregunta(null);
    try {
      const consulta = await crearConsulta(radicado, limpia, usuario || undefined);
      setHilo((prev) => (prev ? [...prev, consulta] : [consulta]));
      setTexto('');
    } catch (e) {
      setErrorPregunta(e instanceof Error ? e.message : 'No se pudo enviar la consulta.');
    } finally {
      setPreguntando(false);
    }
  };

  return (
    <div className="pane--mid">
      <h2 className="tab__titulo">Consultas sobre el proceso de calidad</h2>
      <p className="tab__subtitulo">
        Pregunta sobre criterios técnicos del proceso de evaluación de calidad. Cada respuesta se muestra
        junto a la cita del corpus normativo que la sustenta.
      </p>

      {sugeridas.length > 0 ? (
        <div className="chips">
          {sugeridas.map((q) => (
            <button
              type="button"
              className="chip"
              key={q.id}
              disabled={preguntando}
              onClick={() => void preguntar(q.pregunta)}
            >
              {q.pregunta}
            </button>
          ))}
        </div>
      ) : null}

      {errorPregunta ? (
        <div className="aviso aviso--danger mb-24" role="alert">
          {errorPregunta}
        </div>
      ) : null}

      {error ? (
        <ErrorVista mensaje={error} onReintentar={reintentar} titulo="No se pudieron cargar las consultas" />
      ) : hilo === null ? (
        <Cargando mensaje="Cargando consultas…" />
      ) : (
        <div className="hilo">
          {hilo.map((c) => (
            <div className="hilo__item" key={c.id}>
              <div className="hilo__pregunta">{c.pregunta}</div>
              {c.encontrada ? (
                <>
                  <div className="hilo__respuesta">{c.respuesta}</div>
                  {/* La cita es obligatoria: una respuesta sin su fuente no se puede mostrar. */}
                  <div className="hilo__cita">
                    {c.cita ? c.cita : 'Respuesta sin cita: no se puede acreditar la fuente.'}
                    {c.url ? (
                      <>
                        {' · '}
                        <a href={c.url} target="_blank" rel="noreferrer noopener">
                          ver fuente
                        </a>
                      </>
                    ) : null}
                  </div>
                </>
              ) : (
                <div className="hilo__respuesta hilo__respuesta--sin-corpus">
                  No hay una entrada en el corpus normativo para esa consulta. El sistema no genera una
                  respuesta cuando no puede citarla.
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <form
        className="fila-agregar"
        onSubmit={(e) => {
          e.preventDefault();
          void preguntar(texto);
        }}
      >
        <label className="sr-only" htmlFor="nueva-consulta">
          Escribe tu pregunta sobre calidad
        </label>
        <input
          id="nueva-consulta"
          className="form-field__input"
          type="text"
          value={texto}
          placeholder="Escribe tu pregunta sobre calidad..."
          onChange={(e) => setTexto(e.target.value)}
        />
        <button type="submit" className="btn-primario" disabled={preguntando || !texto.trim()}>
          {preguntando ? 'Consultando…' : 'Preguntar'}
        </button>
      </form>
    </div>
  );
}
