import { formatearFecha } from '../formato';
import type { ResultadoRadicacion } from '../api/tipos';

const PROXIMOS_PASOS = [
  '1. El equipo de radicación validará integridad y legibilidad del expediente.',
  '2. Recibirás una notificación cuando el expediente sea clasificado y distribuido a los grupos evaluadores.',
  '3. Podrás consultar el estado del radicado en cualquier momento con el número asignado.',
];

export function StepConfirmacion({ resultado }: { resultado: ResultadoRadicacion | null }) {
  if (!resultado) {
    return (
      <section className="pane--mid">
        <h1 className="pane__title">Sin resultado de radicación</h1>
        <p className="pane__subtitle">
          Vuelve al paso de pago y confirma la radicación para obtener el número de radicado.
        </p>
      </section>
    );
  }

  const suspendido = resultado.suspendido;
  const inconsistencias = resultado.validacionPago?.inconsistencias ?? [];

  return (
    <section className="pane--mid">
      <div className="done-head">
        {suspendido ? (
          <div className="done-check done-check--warn" aria-hidden="true">
            !
          </div>
        ) : (
          <div className="done-check" aria-hidden="true">
            ✓
          </div>
        )}
        <h1 className="pane__title" style={{ marginBottom: 0 }}>
          {suspendido ? 'Radicado con inconsistencia de pago' : 'Solicitud radicada'}
        </h1>
      </div>
      <p className="pane__subtitle" style={{ marginBottom: 24 }}>
        {suspendido
          ? 'El expediente quedó radicado pero suspendido: los datos del pago declarado no coinciden con la base transaccional. Un servidor público debe revisarlo antes de continuar.'
          : 'El expediente ha sido recibido y quedará pendiente de validación humana.'}
      </p>

      <div className={`receipt${suspendido ? ' receipt--warn' : ''}`}>
        <div className="receipt__label">Número de radicado</div>
        <div className="receipt__number">{resultado.radicado}</div>
        <div className="receipt__grid">
          <div>
            <div className="receipt__key">Fecha de radicación</div>
            <div>{formatearFecha(resultado.fechaRadicacion)}</div>
          </div>
          <div>
            <div className="receipt__key">Tipo de trámite</div>
            <div>{resultado.tipoTramite}</div>
          </div>
          <div>
            <div className="receipt__key">Tipo de producto</div>
            <div>{resultado.tipoProducto}</div>
          </div>
          <div>
            <div className="receipt__key">Estado</div>
            <div className={suspendido ? 'receipt__state receipt__state--warn' : 'receipt__state'}>
              {resultado.estado}
            </div>
          </div>
        </div>
      </div>

      {suspendido ? (
        <div className="panel-inconsistencias">
          <div className="panel-inconsistencias__titulo">Inconsistencias detectadas en el pago</div>
          {resultado.validacionPago?.resultado ? (
            <p className="panel-inconsistencias__resumen">{resultado.validacionPago.resultado}</p>
          ) : null}
          {inconsistencias.length > 0 ? (
            <ul className="lista-inconsistencias">
              {inconsistencias.map((inc, i) => (
                <li className="inconsistencia" key={`${inc.campo}-${i}`}>
                  <div className="inconsistencia__campo">{inc.campo}</div>
                  <div className="inconsistencia__par">
                    <span className="inconsistencia__clave">Esperado</span>
                    <span className="inconsistencia__valor">{String(inc.esperado ?? '—')}</span>
                  </div>
                  <div className="inconsistencia__par">
                    <span className="inconsistencia__clave">Encontrado</span>
                    <span className="inconsistencia__valor">{String(inc.encontrado ?? '—')}</span>
                  </div>
                  {inc.mensaje ? <div className="inconsistencia__mensaje">{inc.mensaje}</div> : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="panel-inconsistencias__resumen">
              El servidor no detalló los campos en conflicto.
            </p>
          )}
        </div>
      ) : null}

      {resultado.advertencia ? <div className="aviso aviso--warn mb-24">{resultado.advertencia}</div> : null}

      {!suspendido ? (
        <>
          <div className="field-label">Próximos pasos</div>
          <div className="next-steps">
            {PROXIMOS_PASOS.map((t) => (
              <div className="next-steps__item" key={t}>
                {t}
              </div>
            ))}
          </div>
        </>
      ) : null}
    </section>
  );
}
