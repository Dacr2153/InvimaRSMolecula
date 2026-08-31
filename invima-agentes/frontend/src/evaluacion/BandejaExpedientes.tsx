import { useCallback, useEffect, useState } from 'react';
import { listarExpedientes } from '../api/cliente';
import { Cargando, ErrorVista, VistaVacia } from '../components/EstadoCarga';
import { EstadoBadge } from '../components/EstadoBadge';
import { SelectorRol } from '../components/SelectorRol';
import { colorDiasEnCola } from '../formato';
import { navegar } from '../router';
import type { ItemBandeja } from '../api/tipos';

export function BandejaExpedientes() {
  const [items, setItems] = useState<ItemBandeja[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [intento, setIntento] = useState(0);

  const reintentar = useCallback(() => setIntento((n) => n + 1), []);

  useEffect(() => {
    let vivo = true;
    const controlador = new AbortController();
    setItems(null);
    setError(null);
    listarExpedientes(controlador.signal)
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
  }, [intento]);

  return (
    <div className="bandeja">
      <div className="bandeja__barra">
        <SelectorRol rol="evaluador" />
      </div>

      <div className="bandeja__eyebrow">EVALUACIÓN TÉCNICA</div>
      <h1 className="bandeja__titulo">Bandeja de evaluación</h1>
      <p className="bandeja__subtitulo">
        Expedientes radicados, pagados y distribuidos, pendientes de evaluación farmacológica/calidad.
      </p>

      {error ? (
        <ErrorVista mensaje={error} onReintentar={reintentar} titulo="No se pudo cargar la bandeja" />
      ) : items === null ? (
        <Cargando mensaje="Cargando expedientes…" />
      ) : items.length === 0 ? (
        <VistaVacia mensaje="No hay expedientes en la bandeja." />
      ) : (
        <div className="tabla">
          <div className="tabla__encabezado" role="row">
            <div>RADICADO</div>
            <div>PRODUCTO</div>
            <div>TITULAR</div>
            <div>TRÁMITE</div>
            <div>EN COLA</div>
            <div>ESTADO</div>
            <div />
          </div>
          {items.map((e) => (
            <div className="tabla__fila" key={e.radicado} role="row">
              <div className="tabla__radicado">{e.radicado}</div>
              <div>
                {e.producto}
                <div className="tabla__sub">{e.principioActivo}</div>
              </div>
              <div>{e.titular}</div>
              <div>{e.tramite}</div>
              <div className="tabla__cola" style={{ color: colorDiasEnCola(e.diasEnCola) }}>
                {e.diasEnCola} {e.diasEnCola === 1 ? 'día' : 'días'}
              </div>
              <div>
                <EstadoBadge estado={e.estado} etiqueta={e.estadoLabel} />
              </div>
              <div>
                <button
                  type="button"
                  className="btn-abrir"
                  onClick={() => navegar(`/evaluacion/${encodeURIComponent(e.radicado)}`)}
                >
                  Abrir
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
