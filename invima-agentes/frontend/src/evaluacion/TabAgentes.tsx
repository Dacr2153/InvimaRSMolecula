import { useEffect, useRef, useState } from 'react';
import { obtenerInformesAgentes } from '../api/cliente';
import { Cargando, ErrorVista } from '../components/EstadoCarga';
import type { InformeAgente } from '../api/tipos';

// Mientras haya agentes sin terminar se consulta cada pocos segundos: el
// evaluador ve el tablero avanzar sin recargar la pagina.
const INTERVALO_MS = 4000;

const ETIQUETA_ESTADO: Record<string, string> = {
  PENDIENTE: 'En cola',
  EN_EJECUCION: 'Procesando…',
  COMPLETADO: 'Completado',
  ERROR: 'Error',
  OMITIDO: 'Sin insumo',
};

const ORDEN_SEVERIDAD = ['CRITICA', 'ALTA', 'MEDIA', 'BAJA', 'INFORMATIVA'];

function claseSeveridad(severidad: string): string {
  const s = severidad.toUpperCase();
  if (s.includes('CRIT')) return 'sev sev--critica';
  if (s.includes('ALTA')) return 'sev sev--alta';
  if (s.includes('MEDIA')) return 'sev sev--media';
  return 'sev sev--baja';
}

function duracion(ms: number | null | undefined): string {
  if (ms == null) return '';
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

type Hallazgo = {
  parametro?: string;
  tipo?: string;
  severidad?: string;
  observacion?: string;
  mensaje?: string;
  trazabilidad?: { descripcion?: string } | null;
};

// A2 reporta "alertas" {tipo, severidad, mensaje}; A3/A4 reportan "hallazgos"
// {parametro, severidad, observacion, trazabilidad}. Se unifican para la tabla.
function hallazgosDe(informe: InformeAgente): Hallazgo[] {
  const p = informe.payload as Record<string, unknown>;
  const crudos = (p.hallazgos ?? p.alertas ?? []) as Hallazgo[];
  return [...crudos].sort((a, b) => {
    const ia = ORDEN_SEVERIDAD.indexOf((a.severidad ?? '').toUpperCase());
    const ib = ORDEN_SEVERIDAD.indexOf((b.severidad ?? '').toUpperCase());
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });
}

function FilaResumen({ informe }: { informe: InformeAgente }) {
  const r = informe.resumen;
  const piezas: string[] = [];
  if (r.estatus_molecula) piezas.push(String(r.estatus_molecula));
  if (r.ruta_recomendada) piezas.push(`Ruta ${String(r.ruta_recomendada)}`);
  if (r.estado_dictamen) piezas.push(String(r.estado_dictamen).split('_').join(' '));
  if (r.clasificacion) piezas.push(String(r.clasificacion));
  if (typeof r.hallazgos === 'number') piezas.push(`${r.hallazgos} hallazgo(s)`);
  if (typeof r.consultas_externas === 'number')
    piezas.push(`${r.consultas_externas} consulta(s) a fuentes externas`);
  if (typeof r.cobertura_verificable === 'number')
    piezas.push(`${r.cobertura_verificable}% contrastado contra límites declarados`);
  if (typeof r.contenido_sospechoso === 'number' && r.contenido_sospechoso > 0)
    piezas.push(`⚠ ${r.contenido_sospechoso} contenido(s) sospechoso(s) neutralizado(s)`);
  if (piezas.length === 0) return null;
  return <div className="agente__resumen">{piezas.join(' · ')}</div>;
}

function TarjetaAgente({ informe }: { informe: InformeAgente }) {
  const [abierto, setAbierto] = useState(false);
  const hallazgos = informe.estado === 'COMPLETADO' ? hallazgosDe(informe) : [];
  const visibles = abierto ? hallazgos : hallazgos.slice(0, 4);
  const porSeveridad = (informe.resumen.por_severidad ?? {}) as Record<string, number>;

  return (
    <article className={`agente agente--${informe.estado.toLowerCase()}`}>
      <header className="agente__cabecera">
        <div>
          <span className="agente__sigla">{informe.agente}</span>
          <span className="agente__nombre">{informe.nombre}</span>
        </div>
        <div className="agente__meta">
          {informe.duracionMs != null && (
            <span className="agente__duracion">{duracion(informe.duracionMs)}</span>
          )}
          <span className={`agente__estado agente__estado--${informe.estado.toLowerCase()}`}>
            {informe.estado === 'EN_EJECUCION' && <span className="spinner" aria-hidden="true" />}
            {ETIQUETA_ESTADO[informe.estado] ?? informe.estado}
          </span>
        </div>
      </header>

      {informe.modelo ? <div className="agente__modelo">Motor: {informe.modelo}</div> : null}
      <FilaResumen informe={informe} />

      {Object.keys(porSeveridad).length > 0 && (
        <div className="agente__severidades">
          {ORDEN_SEVERIDAD.filter((s) => porSeveridad[s]).map((s) => (
            <span key={s} className={claseSeveridad(s)}>
              {s}: {porSeveridad[s]}
            </span>
          ))}
        </div>
      )}

      {informe.estado === 'ERROR' && (
        <div className="aviso aviso--error">{informe.error}</div>
      )}
      {informe.estado === 'OMITIDO' && (
        <div className="aviso aviso--warn">{informe.error}</div>
      )}

      {visibles.length > 0 && (
        <table className="agente__hallazgos">
          <thead>
            <tr>
              <th>Severidad</th>
              <th>Hallazgo</th>
              <th>Observación</th>
            </tr>
          </thead>
          <tbody>
            {visibles.map((h, i) => (
              <tr key={i}>
                <td>
                  <span className={claseSeveridad(h.severidad ?? '')}>{h.severidad ?? '—'}</span>
                </td>
                <td className="agente__parametro">{h.parametro ?? h.tipo ?? '—'}</td>
                <td>
                  {h.observacion ?? h.mensaje ?? ''}
                  {h.trazabilidad?.descripcion ? (
                    <div className="agente__traza">{h.trazabilidad.descripcion}</div>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {hallazgos.length > 4 && (
        <button type="button" className="btn btn--texto" onClick={() => setAbierto(!abierto)}>
          {abierto ? 'Ver menos' : `Ver los ${hallazgos.length} hallazgos`}
        </button>
      )}
    </article>
  );
}

export function TabAgentes({ radicado }: { radicado: string }) {
  const [informes, setInformes] = useState<InformeAgente[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const temporizador = useRef<number | null>(null);

  useEffect(() => {
    let vivo = true;

    const cargar = async () => {
      try {
        const datos = await obtenerInformesAgentes(radicado);
        if (!vivo) return;
        setInformes(datos);
        setError(null);
        const activos = datos.some(
          (i) => i.estado === 'PENDIENTE' || i.estado === 'EN_EJECUCION',
        );
        if (activos) temporizador.current = window.setTimeout(() => void cargar(), INTERVALO_MS);
      } catch (e) {
        if (!vivo) return;
        setError(e instanceof Error ? e.message : 'No se pudo cargar el informe.');
      }
    };
    void cargar();

    return () => {
      vivo = false;
      if (temporizador.current !== null) window.clearTimeout(temporizador.current);
    };
  }, [radicado]);

  if (error) return <ErrorVista mensaje={error} />;
  if (informes === null) return <Cargando mensaje="Cargando informe de agentes…" />;

  const enCurso = informes.filter(
    (i) => i.estado === 'PENDIENTE' || i.estado === 'EN_EJECUCION',
  ).length;

  return (
    <section>
      <div className="agentes__intro">
        <p>
          Trabajo de los agentes sobre este expediente. Cada hallazgo cita su fuente;
          ninguno constituye concepto técnico ni decisión: la evaluación y la firma
          corresponden al servidor público competente.
        </p>
        {enCurso > 0 && (
          <p className="agentes__encurso">
            <span className="spinner" aria-hidden="true" /> {enCurso} agente(s) en
            ejecución — el tablero se actualiza solo.
          </p>
        )}
      </div>
      <div className="agentes__lista">
        {informes.map((i) => (
          <TarjetaAgente key={i.agente} informe={i} />
        ))}
      </div>
    </section>
  );
}
