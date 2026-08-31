import { navegar } from '../router';

type Props = { rol: 'solicitante' | 'evaluador' };

// Selector provisional de rol: no hay autenticacion todavia, asi que la unica
// forma de cambiar de pantalla es esta. Va discreto, arriba a la derecha.
export function SelectorRol({ rol }: Props) {
  return (
    <div className="selector-rol" role="group" aria-label="Cambiar de rol (sin autenticación)">
      <span className="selector-rol__etiqueta">Vista</span>
      <button
        type="button"
        className={`selector-rol__opcion${rol === 'solicitante' ? ' selector-rol__opcion--activa' : ''}`}
        aria-pressed={rol === 'solicitante'}
        onClick={() => navegar('/radicacion')}
      >
        Solicitante
      </button>
      <button
        type="button"
        className={`selector-rol__opcion${rol === 'evaluador' ? ' selector-rol__opcion--activa' : ''}`}
        aria-pressed={rol === 'evaluador'}
        onClick={() => navegar('/evaluacion')}
      >
        Evaluador
      </button>
    </div>
  );
}
