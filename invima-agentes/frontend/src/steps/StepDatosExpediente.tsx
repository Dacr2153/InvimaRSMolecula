import { CAMPOS_EXPEDIENTE } from '../constantes';
import type { DatosDeclarados } from '../api/tipos';

type Props = {
  datos: DatosDeclarados;
  tocados: Record<string, boolean>;
  onCambiar: (campo: string, valor: string) => void;
  onTocar: (campo: string) => void;
};

export function StepDatosExpediente({ datos, tocados, onCambiar, onTocar }: Props) {
  return (
    <section className="pane">
      <h1 className="pane__title">Datos del expediente</h1>
      <p className="pane__subtitle">
        Información general de la solicitud, el producto y los responsables. Los campos marcados con
        <span className="req"> *</span> son obligatorios.
      </p>

      <div className="form-grid">
        {CAMPOS_EXPEDIENTE.map((c) => {
          const bruto = datos[c.id];
          const valor = typeof bruto === 'string' ? bruto : '';
          const invalido = c.required && tocados[c.id] && !valor.trim();
          const idInput = `campo-${c.id}`;
          return (
            <div key={c.id} className={c.fullWidth ? 'form-field form-field--ancho' : 'form-field'}>
              <label className="form-field__label" htmlFor={idInput}>
                {c.label}
                {c.required ? <span className="req"> *</span> : null}
              </label>
              <input
                id={idInput}
                className={`form-field__input${invalido ? ' form-field__input--invalido' : ''}`}
                type="text"
                value={valor}
                placeholder={c.placeholder}
                aria-required={c.required}
                aria-invalid={invalido ? true : undefined}
                aria-describedby={invalido ? `${idInput}-error` : undefined}
                onChange={(e) => onCambiar(c.id, e.target.value)}
                onBlur={() => onTocar(c.id)}
              />
              {invalido ? (
                <div className="form-field__error" id={`${idInput}-error`}>
                  Este campo es obligatorio.
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </section>
  );
}
