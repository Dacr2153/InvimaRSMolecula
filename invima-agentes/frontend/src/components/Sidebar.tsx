import { STEP_LABELS, SOLICITANTE } from '../constantes';

type Props = {
  step: number;
  maxReached: number;
  onGoToStep: (i: number) => void;
};

export function Sidebar({ step, maxReached, onGoToStep }: Props) {
  return (
    <nav className="sidebar" aria-label="Pasos de la radicación">
      <div className="sidebar__brand">
        <div className="sidebar__eyebrow">SISTEMA DE RADICACIÓN</div>
        <div className="sidebar__title">Registro Sanitario</div>
      </div>

      <div className="sidebar__steps">
        {STEP_LABELS.map((label, i) => {
          const active = i === step;
          const done = i < step;
          const reachable = i <= maxReached;

          const badge = ['step-item__badge'];
          if (active) badge.push('step-item__badge--active');
          else if (done) badge.push('step-item__badge--done');

          const text = ['step-item__label'];
          if (active) text.push('step-item__label--active');
          else if (!reachable) text.push('step-item__label--locked');

          return (
            <button
              key={label}
              type="button"
              className="step-item"
              disabled={!reachable}
              aria-current={active ? 'step' : undefined}
              onClick={() => onGoToStep(i)}
            >
              <div className={badge.join(' ')}>{done ? '✓' : i + 1}</div>
              <div className={text.join(' ')}>{label}</div>
            </button>
          );
        })}
      </div>

      <div className="sidebar__footer">
        Radicado en curso
        <br />
        Solicitante: {SOLICITANTE.nombre}
      </div>
    </nav>
  );
}
