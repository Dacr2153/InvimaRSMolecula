import { useState } from 'react';
import { registrarDecision } from '../api/cliente';
import { formatearFechaHora } from '../formato';
import type { DecisionHumana, SentidoDecision } from '../api/tipos';

type Props = {
  radicado: string;
  puedeDecidir: boolean;
  decision: DecisionHumana | null;
  usuario: string;
  onUsuario: (v: string) => void;
  onDecidido: () => void;
};

const ACCIONES: { sentido: SentidoDecision; etiqueta: string; clase: string }[] = [
  { sentido: 'APROBAR_ENRUTAMIENTO', etiqueta: 'Aprobar enrutamiento', clase: 'btn-decision--aprobar' },
  { sentido: 'CORREGIR_Y_APROBAR', etiqueta: 'Corregir y aprobar', clase: 'btn-decision--corregir' },
  { sentido: 'DEVOLVER', etiqueta: 'Devolver al solicitante', clase: 'btn-decision--devolver' },
];

const ETIQUETA_SENTIDO: Record<SentidoDecision, string> = {
  APROBAR_ENRUTAMIENTO: 'Aprobó el enrutamiento',
  CORREGIR_Y_APROBAR: 'Corrigió y aprobó',
  DEVOLVER: 'Devolvió al solicitante',
};

export function PanelDecision({ radicado, puedeDecidir, decision, usuario, onUsuario, onDecidido }: Props) {
  const [observaciones, setObservaciones] = useState('');
  const [pendiente, setPendiente] = useState<SentidoDecision | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!puedeDecidir) {
    if (!decision) {
      return (
        <div className="decision decision--cerrada">
          <div className="decision__firma-texto">
            Este expediente no admite una decisión humana en su estado actual.
          </div>
        </div>
      );
    }
    return (
      <div className="decision decision--firmada">
        <div className="decision__firma-titulo">Decisión registrada</div>
        <div className="decision__firma-texto">
          <strong>{decision.usuario}</strong> · {ETIQUETA_SENTIDO[decision.sentido] ?? decision.sentido} ·{' '}
          {formatearFechaHora(decision.momento)}
        </div>
        {decision.observaciones ? (
          <div className="decision__firma-observaciones">{decision.observaciones}</div>
        ) : null}
      </div>
    );
  }

  const confirmar = async () => {
    if (!pendiente) return;
    setEnviando(true);
    setError(null);
    try {
      await registrarDecision(radicado, {
        usuario: usuario.trim(),
        sentido: pendiente,
        observaciones: observaciones.trim() || undefined,
      });
      setPendiente(null);
      onDecidido();
    } catch (e) {
      // Un 409 trae el texto normativo completo: se muestra tal cual, sin resumir.
      setError(e instanceof Error ? e.message : 'No se pudo registrar la decisión.');
    } finally {
      setEnviando(false);
    }
  };

  const sinUsuario = !usuario.trim();
  const etiquetaPendiente = pendiente ? ACCIONES.find((a) => a.sentido === pendiente)?.etiqueta : '';

  return (
    <div className="decision">
      <div className="decision__marco">
        <div className="decision__leyenda">
          Aquí termina lo que hace el sistema. El agente recomienda; el servidor público decide. La decisión
          queda firmada con nombre y hora.
        </div>

        <div className="decision__campos">
          <div className="form-field">
            <label className="form-field__label" htmlFor="decision-usuario">
              Servidor público que decide <span className="req">*</span>
            </label>
            <input
              id="decision-usuario"
              className="form-field__input"
              type="text"
              value={usuario}
              placeholder="Nombre y cargo"
              aria-required="true"
              onChange={(e) => onUsuario(e.target.value)}
            />
          </div>
          <div className="form-field form-field--ancho">
            <label className="form-field__label" htmlFor="decision-observaciones">
              Observaciones
            </label>
            <textarea
              id="decision-observaciones"
              className="form-field__input form-field__input--area"
              rows={2}
              value={observaciones}
              placeholder="Sustento de la decisión, hallazgos y condiciones."
              onChange={(e) => setObservaciones(e.target.value)}
            />
          </div>
        </div>

        {error ? (
          <div className="aviso aviso--danger decision__error" role="alert">
            {error}
          </div>
        ) : null}

        {pendiente ? (
          <div className="decision__confirmacion" role="alertdialog" aria-label="Confirmar decisión">
            <div className="decision__confirmacion-texto">
              Vas a registrar <strong>{etiquetaPendiente}</strong> sobre el radicado {radicado}, firmado como{' '}
              <strong>{usuario.trim()}</strong>. Esta acción queda en el expediente.
            </div>
            <div className="decision__confirmacion-acciones">
              <button type="button" className="btn-secundario" onClick={() => setPendiente(null)} disabled={enviando}>
                Cancelar
              </button>
              <button type="button" className="btn-primario" onClick={() => void confirmar()} disabled={enviando}>
                {enviando ? 'Firmando…' : 'Confirmar y firmar'}
              </button>
            </div>
          </div>
        ) : (
          <div className="decision__acciones">
            {sinUsuario ? (
              <span className="decision__aviso-usuario">Escribe quién decide para habilitar las acciones.</span>
            ) : null}
            {ACCIONES.map((a) => (
              <button
                key={a.sentido}
                type="button"
                className={`btn-decision ${a.clase}`}
                disabled={sinUsuario}
                onClick={() => {
                  setError(null);
                  setPendiente(a.sentido);
                }}
              >
                {a.etiqueta}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
