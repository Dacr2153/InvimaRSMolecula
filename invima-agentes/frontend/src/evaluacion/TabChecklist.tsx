import { useCallback, useEffect, useState } from 'react';
import {
  crearItemChecklist,
  eliminarItemChecklist,
  marcarItemChecklist,
  obtenerChecklist,
} from '../api/cliente';
import { Cargando, ErrorVista, VistaVacia } from '../components/EstadoCarga';
import type { ItemChecklist } from '../api/tipos';

type Props = { radicado: string; usuario: string };

export function TabChecklist({ radicado, usuario }: Props) {
  const [items, setItems] = useState<ItemChecklist[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorAccion, setErrorAccion] = useState<string | null>(null);
  const [intento, setIntento] = useState(0);
  const [nuevo, setNuevo] = useState('');
  const [agregando, setAgregando] = useState(false);
  const [enCurso, setEnCurso] = useState<string | null>(null);

  const reintentar = useCallback(() => setIntento((n) => n + 1), []);

  useEffect(() => {
    let vivo = true;
    const controlador = new AbortController();
    setItems(null);
    setError(null);
    obtenerChecklist(radicado, controlador.signal)
      .then((r) => {
        if (vivo) setItems(r);
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

  const alternar = async (item: ItemChecklist) => {
    setEnCurso(item.id);
    setErrorAccion(null);
    try {
      const actualizado = await marcarItemChecklist(
        radicado,
        item.id,
        !item.verificado,
        usuario || 'sin identificar',
      );
      setItems((prev) => (prev ? prev.map((x) => (x.id === item.id ? actualizado : x)) : prev));
    } catch (e) {
      setErrorAccion(e instanceof Error ? e.message : 'No se pudo actualizar el criterio.');
    } finally {
      setEnCurso(null);
    }
  };

  const quitar = async (item: ItemChecklist) => {
    setEnCurso(item.id);
    setErrorAccion(null);
    try {
      await eliminarItemChecklist(radicado, item.id);
      setItems((prev) => (prev ? prev.filter((x) => x.id !== item.id) : prev));
    } catch (e) {
      setErrorAccion(e instanceof Error ? e.message : 'No se pudo quitar el criterio.');
    } finally {
      setEnCurso(null);
    }
  };

  const agregar = async () => {
    const texto = nuevo.trim();
    if (!texto) return;
    setAgregando(true);
    setErrorAccion(null);
    try {
      const creado = await crearItemChecklist(radicado, texto);
      setItems((prev) => (prev ? [...prev, creado] : [creado]));
      setNuevo('');
    } catch (e) {
      setErrorAccion(e instanceof Error ? e.message : 'No se pudo agregar el criterio.');
    } finally {
      setAgregando(false);
    }
  };

  return (
    <div className="pane--mid">
      <h2 className="tab__titulo">Criterios de evaluación</h2>
      <p className="tab__subtitulo">
        Lista de verificación de calidad para esta molécula. Agrega o retira criterios según el caso.
      </p>

      {errorAccion ? (
        <div className="aviso aviso--danger mb-24" role="alert">
          {errorAccion}
        </div>
      ) : null}

      {error ? (
        <ErrorVista mensaje={error} onReintentar={reintentar} titulo="No se pudo cargar el checklist" />
      ) : items === null ? (
        <Cargando mensaje="Cargando criterios…" />
      ) : (
        <>
          {items.length === 0 ? (
            <VistaVacia mensaje="Todavía no hay criterios. Agrega el primero abajo." />
          ) : null}

          <ul className="checklist">
            {items.map((c) => (
              <li className="checklist__item" key={c.id}>
                <button
                  type="button"
                  className={`checklist__caja${c.verificado ? ' checklist__caja--marcada' : ''}`}
                  aria-pressed={c.verificado}
                  aria-label={`Marcar como verificado: ${c.texto}`}
                  disabled={enCurso === c.id}
                  onClick={() => void alternar(c)}
                >
                  {c.verificado ? '✓' : ''}
                </button>
                <span className={`checklist__texto${c.verificado ? ' checklist__texto--verificado' : ''}`}>
                  {c.texto}
                  {c.verificado && c.verificadoPor ? (
                    <span className="checklist__firma">verificado por {c.verificadoPor}</span>
                  ) : null}
                </span>
                <button
                  type="button"
                  className="checklist__quitar"
                  aria-label={`Quitar criterio: ${c.texto}`}
                  disabled={enCurso === c.id}
                  onClick={() => void quitar(c)}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>

          <form
            className="fila-agregar"
            onSubmit={(e) => {
              e.preventDefault();
              void agregar();
            }}
          >
            <label className="sr-only" htmlFor="nuevo-criterio">
              Nuevo criterio de evaluación
            </label>
            <input
              id="nuevo-criterio"
              className="form-field__input"
              type="text"
              value={nuevo}
              placeholder="Nuevo criterio de evaluación..."
              onChange={(e) => setNuevo(e.target.value)}
            />
            <button type="submit" className="btn-primario" disabled={agregando || !nuevo.trim()}>
              {agregando ? 'Agregando…' : 'Agregar'}
            </button>
          </form>
        </>
      )}
    </div>
  );
}
