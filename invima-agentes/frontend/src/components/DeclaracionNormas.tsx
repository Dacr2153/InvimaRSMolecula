import type { DatosDeclarados } from '../api/tipos';

//: Clave dentro de `datos_declarados`. La lee `sintetizar_folio_fm113` para
//: escribir la casilla "Molecula NO incluida en normas farmacologicas: SI/NO"
//: del folio ASS-RSA-FM113, que es lo que el A1 cruza contra el Manual.
export const CLAVE_NO_INCLUIDA = 'moleculaNoIncluidaNormas';

export function leerNoIncluida(datos: DatosDeclarados): boolean {
  return datos[CLAVE_NO_INCLUIDA] === true;
}

type Props = {
  valor: boolean;
  onCambio: (valor: boolean) => void;
};

/**
 * La declaracion del solicitante sobre el estatus normativo de la molecula.
 *
 * Es una declaracion, no una verificacion: el agente la cruza despues contra el
 * Manual de Normas Farmacologicas y, si no coinciden, el Manual manda y la
 * contradiccion queda registrada para el evaluador. Por eso el texto de ayuda
 * lo dice: marcar la casilla no decide nada, y equivocarse no pasa inadvertido.
 */
export function DeclaracionNormas({ valor, onCambio }: Props) {
  return (
    <div className="doc-group">
      <div className="doc-group__title">
        Estatus normativo de la molécula <span className="chip chip--declaracion">Declaración</span>
      </div>

      <label className="declaracion">
        <span className="declaracion__texto">
          <span className="declaracion__titulo">
            La molécula NO está incluida en normas farmacológicas
          </span>
          <span className="declaracion__ayuda">
            Actívalo si el principio activo no figura en el Manual de Normas Farmacológicas.
            El sistema verifica esta declaración contra el Manual; si no coinciden, prevalece
            el Manual y la diferencia queda visible para el evaluador.
          </span>
        </span>

        <input
          className="switch__input"
          type="checkbox"
          role="switch"
          checked={valor}
          onChange={(e) => onCambio(e.target.checked)}
        />
        <span className="switch" aria-hidden="true">
          <span className="switch__perilla" />
        </span>
      </label>

      <p className="declaracion__estado">
        Declarado: <strong>{valor ? 'NO incluida en normas' : 'Incluida en normas'}</strong>
      </p>
    </div>
  );
}
