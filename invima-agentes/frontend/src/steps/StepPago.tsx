import { OptionCard } from '../components/OptionCard';
import { CargaDocumento } from '../components/CargaDocumento';
import { formatearMoneda } from '../formato';
import type { DocumentoCargado, MetodoPago, Tarifa } from '../api/tipos';

type Props = {
  solicitudId: string;
  tarifas: Tarifa[];
  metodosPago: MetodoPago[];
  tarifaCodigo: string;
  metodoPago: string;
  comprobante: string;
  valorPagado: string;
  fechaPago: string;
  requeridoComprobante: string;
  documentoComprobante: DocumentoCargado | null;
  onTarifa: (codigo: string) => void;
  onMetodoPago: (id: string) => void;
  onComprobante: (v: string) => void;
  onValorPagado: (v: string) => void;
  onFechaPago: (v: string) => void;
  onDocumento: (requeridoId: string, doc: DocumentoCargado | null) => void;
};

export function StepPago(p: Props) {
  const tarifa = p.tarifas.find((t) => t.codigo === p.tarifaCodigo) ?? null;

  return (
    <section className="pane--mid">
      <h1 className="pane__title">Pago del trámite</h1>
      <p className="pane__subtitle">
        Selecciona la tarifa aplicable y declara el pago. Estos datos se contrastan contra la base
        transaccional al radicar.
      </p>

      <div className="card">
        <div className="form-field mb-16">
          <label className="form-field__label" htmlFor="tarifa-codigo">
            Código de tarifa <span className="req">*</span>
          </label>
          <select
            id="tarifa-codigo"
            className="form-field__input"
            value={p.tarifaCodigo}
            aria-required="true"
            onChange={(e) => p.onTarifa(e.target.value)}
          >
            <option value="">Selecciona un código…</option>
            {p.tarifas.map((t) => (
              <option key={t.codigo} value={t.codigo}>
                {t.codigo} — {t.concepto}
              </option>
            ))}
          </select>
        </div>

        <div className="fee-row">
          <span className="fee-row__key">Concepto</span>
          <span>{tarifa ? tarifa.concepto : '—'}</span>
        </div>
        <div className="fee-total">
          <span>Valor a pagar</span>
          <span className="fee-total__value">{tarifa ? formatearMoneda(tarifa.valor) : '—'}</span>
        </div>
      </div>

      <div className="field-label">Método de pago</div>
      <div className="option-grid option-grid--3 mb-24">
        {p.metodosPago.map((m) => (
          <OptionCard
            key={m.id}
            label={m.etiqueta}
            variant="pay"
            selected={p.metodoPago === m.id}
            onSelect={() => p.onMetodoPago(m.id)}
          />
        ))}
      </div>

      <div className="field-label">Datos del pago realizado</div>
      <div className="form-grid mb-24">
        <div className="form-field">
          <label className="form-field__label" htmlFor="pago-comprobante">
            Número de comprobante <span className="req">*</span>
          </label>
          <input
            id="pago-comprobante"
            className="form-field__input"
            type="text"
            value={p.comprobante}
            placeholder="BAN-8839201"
            aria-required="true"
            onChange={(e) => p.onComprobante(e.target.value)}
          />
        </div>
        <div className="form-field">
          <label className="form-field__label" htmlFor="pago-valor">
            Valor pagado <span className="req">*</span>
          </label>
          <input
            id="pago-valor"
            className="form-field__input"
            type="text"
            inputMode="decimal"
            value={p.valorPagado}
            placeholder="9350000.00"
            aria-required="true"
            onChange={(e) => p.onValorPagado(e.target.value)}
          />
        </div>
        <div className="form-field">
          <label className="form-field__label" htmlFor="pago-fecha">
            Fecha de pago <span className="req">*</span>
          </label>
          <input
            id="pago-fecha"
            className="form-field__input"
            type="date"
            value={p.fechaPago}
            aria-required="true"
            onChange={(e) => p.onFechaPago(e.target.value)}
          />
        </div>
      </div>

      <div className="field-label">Comprobante de pago</div>
      <div className="doc-group__list">
        <CargaDocumento
          solicitudId={p.solicitudId}
          requeridoId={p.requeridoComprobante}
          nombre="Comprobante de pago"
          obligatorio
          documento={p.documentoComprobante}
          onDocumento={p.onDocumento}
        />
      </div>
    </section>
  );
}
