import { SOLICITANTE, STEP_LABELS } from '../constantes';
import { SelectorRol } from './SelectorRol';
import type { EstadoGuardado } from '../radicacion/RadicacionApp';

const TEXTO_GUARDADO: Record<EstadoGuardado, string> = {
  inactivo: '',
  guardando: 'Guardando borrador…',
  guardado: 'Borrador guardado',
  error: 'No se pudo guardar',
};

export function Topbar({ step, guardado }: { step: number; guardado: EstadoGuardado }) {
  const texto = TEXTO_GUARDADO[guardado];
  return (
    <header className="topbar">
      <div className="topbar__progress">
        Paso {step + 1} de {STEP_LABELS.length}
        {texto ? (
          <span className={`topbar__guardado topbar__guardado--${guardado}`} aria-live="polite">
            {texto}
          </span>
        ) : null}
      </div>
      <div className="topbar__user">
        <SelectorRol rol="solicitante" />
        <div className="topbar__avatar" aria-hidden="true">
          {SOLICITANTE.iniciales}
        </div>
        <div className="topbar__name">{SOLICITANTE.nombre}</div>
      </div>
    </header>
  );
}
