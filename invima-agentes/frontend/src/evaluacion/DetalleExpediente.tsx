import { useCallback, useEffect, useState } from 'react';
import { obtenerExpediente } from '../api/cliente';
import { Cargando, ErrorVista } from '../components/EstadoCarga';
import { EstadoBadge } from '../components/EstadoBadge';
import { SelectorRol } from '../components/SelectorRol';
import { navegar } from '../router';
import { TabDocumentos } from './TabDocumentos';
import { TabFuentes } from './TabFuentes';
import { TabChecklist } from './TabChecklist';
import { TabConsultas } from './TabConsultas';
import { TabAgentes } from './TabAgentes';
import { PanelDecision } from './PanelDecision';
import type { ExpedienteDetalle } from '../api/tipos';

type IdPestana = 'agentes' | 'documentos' | 'fuentes' | 'checklist' | 'consultas';

const PESTANAS: { id: IdPestana; etiqueta: string }[] = [
  { id: 'agentes', etiqueta: 'Informe de agentes' },
  { id: 'documentos', etiqueta: 'Documentos del solicitante' },
  { id: 'fuentes', etiqueta: 'Fuentes externas (agente)' },
  { id: 'checklist', etiqueta: 'Checklist de evaluación' },
  { id: 'consultas', etiqueta: 'Consultas de calidad' },
];

const CLAVE_USUARIO = 'invima.evaluador';

function leerUsuarioGuardado(): string {
  try {
    return window.localStorage.getItem(CLAVE_USUARIO) ?? '';
  } catch {
    return '';
  }
}

export function DetalleExpediente({ radicado }: { radicado: string }) {
  const [detalle, setDetalle] = useState<ExpedienteDetalle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [intento, setIntento] = useState(0);
  const [pestana, setPestana] = useState<IdPestana>('agentes');
  const [usuario, setUsuario] = useState<string>(leerUsuarioGuardado);

  const recargar = useCallback(() => setIntento((n) => n + 1), []);

  const cambiarUsuario = useCallback((v: string) => {
    setUsuario(v);
    try {
      window.localStorage.setItem(CLAVE_USUARIO, v);
    } catch {
      // sin almacenamiento local la sesion sigue funcionando en memoria
    }
  }, []);

  useEffect(() => {
    let vivo = true;
    const controlador = new AbortController();
    setDetalle(null);
    setError(null);
    obtenerExpediente(radicado, controlador.signal)
      .then((r) => {
        if (vivo) setDetalle(r);
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

  if (error) {
    return (
      <div className="pantalla-centrada">
        <ErrorVista
          titulo={`No se pudo abrir el expediente ${radicado}`}
          mensaje={error}
          onReintentar={recargar}
        />
        <button type="button" className="btn-secundario" onClick={() => navegar('/evaluacion')}>
          ← Volver a la bandeja
        </button>
      </div>
    );
  }

  if (!detalle) {
    return (
      <div className="pantalla-centrada">
        <Cargando mensaje={`Abriendo el expediente ${radicado}…`} />
      </div>
    );
  }

  return (
    <div className="expediente">
      <header className="expediente__cabecera">
        <div className="expediente__identidad">
          <button type="button" className="btn-volver" onClick={() => navegar('/evaluacion')}>
            ← Bandeja
          </button>
          <div>
            <div className="expediente__titulo">
              {detalle.producto} <span className="expediente__radicado">· {detalle.radicado}</span>
            </div>
            <div className="expediente__titular">Titular: {detalle.titular}</div>
          </div>
        </div>
        <div className="expediente__cabecera-derecha">
          <SelectorRol rol="evaluador" />
          <EstadoBadge estado={detalle.estado} etiqueta={detalle.estadoLabel} tamano="md" />
        </div>
      </header>

      <div className="expediente__cuerpo">
        <nav className="expediente__tabs" aria-label="Secciones del expediente">
          {PESTANAS.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`tab-item${pestana === t.id ? ' tab-item--activa' : ''}`}
              aria-current={pestana === t.id ? 'page' : undefined}
              onClick={() => setPestana(t.id)}
            >
              {t.etiqueta}
            </button>
          ))}
        </nav>

        <div className="expediente__panel">
          <div className="expediente__contenido">
            {pestana === 'agentes' && <TabAgentes radicado={detalle.radicado} />}
            {pestana === 'documentos' && <TabDocumentos documentos={detalle.documentos} />}
            {pestana === 'fuentes' && <TabFuentes radicado={detalle.radicado} usuario={usuario} />}
            {pestana === 'checklist' && <TabChecklist radicado={detalle.radicado} usuario={usuario} />}
            {pestana === 'consultas' && <TabConsultas radicado={detalle.radicado} usuario={usuario} />}
          </div>

          <PanelDecision
            radicado={detalle.radicado}
            puedeDecidir={detalle.puedeDecidir}
            decision={detalle.decisionHumana}
            usuario={usuario}
            onUsuario={cambiarUsuario}
            onDecidido={recargar}
          />
        </div>
      </div>
    </div>
  );
}
