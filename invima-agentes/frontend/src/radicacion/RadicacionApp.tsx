import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { CLAVE_NO_INCLUIDA, leerNoIncluida } from '../components/DeclaracionNormas';
import { Sidebar } from '../components/Sidebar';
import { Topbar } from '../components/Topbar';
import { Cargando, ErrorVista } from '../components/EstadoCarga';
import { StepTipoSolicitud } from '../steps/StepTipoSolicitud';
import { StepDatosExpediente } from '../steps/StepDatosExpediente';
import { StepDocumentos } from '../steps/StepDocumentos';
import { StepPago } from '../steps/StepPago';
import { StepConfirmacion } from '../steps/StepConfirmacion';
import { CAMPOS_EXPEDIENTE, REQUERIDO_COMPROBANTE, STEP_LABELS } from '../constantes';
import {
  crearSolicitud,
  obtenerCatalogos,
  parcharSolicitud,
  radicarSolicitud,
  ErrorApi,
} from '../api/cliente';
import type {
  Catalogos,
  DatosDeclarados,
  DocumentoCargado,
  EnlaceEvidencia,
  ParchesSolicitud,
  ResultadoRadicacion,
  Solicitud,
} from '../api/tipos';

const ULTIMO_PASO = STEP_LABELS.length - 1;

export type EstadoGuardado = 'inactivo' | 'guardando' | 'guardado' | 'error';

// El contrato no fija el requeridoId del comprobante de pago. Se busca en el
// catalogo un documento que lo represente y, si no existe, se usa la constante.
function resolverRequeridoComprobante(catalogos: Catalogos | null): string {
  if (!catalogos) return REQUERIDO_COMPROBANTE;
  for (const modulo of catalogos.modulosCtd) {
    for (const doc of modulo.documentos) {
      const texto = `${doc.id} ${doc.nombre}`.toLowerCase();
      if (texto.includes('comprobante') || texto.includes('soporte de pago')) return doc.id;
    }
  }
  return REQUERIDO_COMPROBANTE;
}

export function RadicacionApp() {
  const [catalogos, setCatalogos] = useState<Catalogos | null>(null);
  const [solicitud, setSolicitud] = useState<Solicitud | null>(null);
  const [errorArranque, setErrorArranque] = useState<string | null>(null);
  const [cargandoArranque, setCargandoArranque] = useState(true);
  const [intento, setIntento] = useState(0);

  const [step, setStep] = useState(0);
  const [maxReached, setMaxReached] = useState(0);
  const [errorPaso, setErrorPaso] = useState<string | null>(null);
  const [guardado, setGuardado] = useState<EstadoGuardado>('inactivo');

  const [tramite, setTramite] = useState('');
  const [producto, setProducto] = useState('');
  const [datos, setDatos] = useState<DatosDeclarados>({});
  const [tocados, setTocados] = useState<Record<string, boolean>>({});
  const [documentos, setDocumentos] = useState<Record<string, DocumentoCargado>>({});
  const [enlaces, setEnlaces] = useState<EnlaceEvidencia[]>([]);

  const [tarifaCodigo, setTarifaCodigo] = useState('');
  const [metodoPago, setMetodoPago] = useState('');
  const [comprobante, setComprobante] = useState('');
  const [valorPagado, setValorPagado] = useState('');
  const [fechaPago, setFechaPago] = useState('');

  const [radicando, setRadicando] = useState(false);
  const [resultado, setResultado] = useState<ResultadoRadicacion | null>(null);

  // --- Arranque: catalogos + borrador ---
  useEffect(() => {
    let vivo = true;
    const controlador = new AbortController();
    setCargandoArranque(true);
    setErrorArranque(null);

    (async () => {
      try {
        const cat = await obtenerCatalogos(controlador.signal);
        if (!vivo) return;
        setCatalogos(cat);
        const borrador = await crearSolicitud();
        if (!vivo) return;
        setSolicitud(borrador);
        setTramite(borrador.tipoTramite ?? cat.tiposTramite[0]?.id ?? '');
        setProducto(borrador.tipoProducto ?? cat.tiposProducto[0]?.id ?? '');
        setDatos(borrador.datosDeclarados ?? {});
        setTarifaCodigo(borrador.tarifaCodigo ?? '');
        setMetodoPago(borrador.metodoPago ?? cat.metodosPago[0]?.id ?? '');
        setComprobante(borrador.comprobante ?? '');
        setValorPagado(borrador.valorPagado ?? '');
        setFechaPago(borrador.fechaPago ?? '');
        const mapa: Record<string, DocumentoCargado> = {};
        for (const d of borrador.documentos ?? []) mapa[d.requeridoId] = d;
        setDocumentos(mapa);
        setEnlaces(borrador.enlaces ?? []);
        setCargandoArranque(false);
      } catch (e) {
        if (!vivo) return;
        if (e instanceof DOMException && e.name === 'AbortError') return;
        setErrorArranque(e instanceof Error ? e.message : 'Error desconocido al iniciar la solicitud.');
        setCargandoArranque(false);
      }
    })();

    return () => {
      vivo = false;
      controlador.abort();
    };
  }, [intento]);

  // --- Parche con debounce (400 ms) para los campos de texto ---
  const pendiente = useRef<ParchesSolicitud>({});
  const temporizador = useRef<number | null>(null);

  const enviarParche = useCallback(
    async (parches: ParchesSolicitud) => {
      if (!solicitud) return;
      setGuardado('guardando');
      try {
        const actualizada = await parcharSolicitud(solicitud.id, parches);
        setSolicitud(actualizada);
        setGuardado('guardado');
      } catch (e) {
        setGuardado('error');
        setErrorPaso(e instanceof Error ? e.message : 'No se pudo guardar el borrador.');
      }
    },
    [solicitud],
  );

  const parcharAhora = useCallback(
    (parches: ParchesSolicitud) => {
      void enviarParche(parches);
    },
    [enviarParche],
  );

  const parcharConDemora = useCallback(
    (parches: ParchesSolicitud) => {
      pendiente.current = { ...pendiente.current, ...parches };
      if (temporizador.current !== null) window.clearTimeout(temporizador.current);
      temporizador.current = window.setTimeout(() => {
        const acumulado = pendiente.current;
        pendiente.current = {};
        temporizador.current = null;
        void enviarParche(acumulado);
      }, 400);
    },
    [enviarParche],
  );

  useEffect(
    () => () => {
      if (temporizador.current !== null) window.clearTimeout(temporizador.current);
    },
    [],
  );

  // --- Manejadores ---
  const cambiarTramite = (id: string) => {
    setTramite(id);
    parcharAhora({ tipoTramite: id });
  };
  const cambiarProducto = (id: string) => {
    setProducto(id);
    parcharAhora({ tipoProducto: id });
  };
  const cambiarDato = (campo: string, valor: string) => {
    const siguientes = { ...datos, [campo]: valor };
    setDatos(siguientes);
    parcharConDemora({ datosDeclarados: siguientes });
  };
  // Un switch no se teclea: se pulsa una vez. Va sin demora, a diferencia de
  // los campos de texto, que se parchean con debounce.
  const declararNoIncluida = (valor: boolean) => {
    const siguientes = { ...datos, [CLAVE_NO_INCLUIDA]: valor };
    setDatos(siguientes);
    parcharAhora({ datosDeclarados: siguientes });
  };
  const marcarTocado = (campo: string) => setTocados((t) => ({ ...t, [campo]: true }));

  const cambiarTarifa = (codigo: string) => {
    setTarifaCodigo(codigo);
    parcharAhora({ tarifaCodigo: codigo });
  };
  const cambiarMetodoPago = (id: string) => {
    setMetodoPago(id);
    parcharAhora({ metodoPago: id });
  };
  const cambiarComprobante = (v: string) => {
    setComprobante(v);
    parcharConDemora({ comprobante: v });
  };
  const cambiarValorPagado = (v: string) => {
    setValorPagado(v);
    parcharConDemora({ valorPagado: v });
  };
  const cambiarFechaPago = (v: string) => {
    setFechaPago(v);
    parcharAhora({ fechaPago: v });
  };

  const registrarDocumento = (requeridoId: string, doc: DocumentoCargado | null) =>
    setDocumentos((prev) => {
      const copia = { ...prev };
      if (doc) copia[requeridoId] = doc;
      else delete copia[requeridoId];
      return copia;
    });

  // --- Validaciones de paso ---
  const camposFaltantes = useMemo(
    // CAMPOS_EXPEDIENTE son todos de texto; un booleano nunca es uno de ellos.
    () =>
      CAMPOS_EXPEDIENTE.filter((c) => {
        const valor = datos[c.id];
        return c.required && !(typeof valor === 'string' ? valor : '').trim();
      }).map((c) => c.label),
    [datos],
  );

  const validarPaso = (indice: number): string | null => {
    if (indice === 0) {
      if (!tramite) return 'Selecciona el tipo de trámite.';
      if (!producto) return 'Selecciona el tipo de producto.';
      return null;
    }
    if (indice === 1) {
      if (camposFaltantes.length > 0) {
        return `Faltan campos obligatorios: ${camposFaltantes.join(', ')}.`;
      }
      return null;
    }
    if (indice === 3) {
      if (!tarifaCodigo) return 'Selecciona el código de tarifa aplicable.';
      if (!metodoPago) return 'Selecciona el método de pago.';
      if (!comprobante.trim()) return 'Ingresa el número de comprobante de pago.';
      if (!valorPagado.trim()) return 'Ingresa el valor pagado.';
      if (!fechaPago) return 'Ingresa la fecha de pago.';
      return null;
    }
    return null;
  };

  const irAPaso = (i: number) => {
    if (i <= maxReached) {
      setErrorPaso(null);
      setStep(i);
    }
  };

  const radicar = async () => {
    if (!solicitud) return;
    setRadicando(true);
    setErrorPaso(null);
    try {
      // Se vacia cualquier parche con demora pendiente antes de radicar.
      if (temporizador.current !== null) {
        window.clearTimeout(temporizador.current);
        temporizador.current = null;
        const acumulado = pendiente.current;
        pendiente.current = {};
        if (Object.keys(acumulado).length > 0) await parcharSolicitud(solicitud.id, acumulado);
      }
      const res = await radicarSolicitud(solicitud.id);
      setResultado(res);
      setStep(ULTIMO_PASO);
      setMaxReached(ULTIMO_PASO);
    } catch (e) {
      const mensaje =
        e instanceof ErrorApi ? e.message : e instanceof Error ? e.message : 'No se pudo radicar la solicitud.';
      setErrorPaso(mensaje);
    } finally {
      setRadicando(false);
    }
  };

  const avanzar = () => {
    const problema = validarPaso(step);
    if (problema) {
      if (step === 1) {
        const marcados: Record<string, boolean> = {};
        for (const c of CAMPOS_EXPEDIENTE) marcados[c.id] = true;
        setTocados(marcados);
      }
      setErrorPaso(problema);
      return;
    }
    setErrorPaso(null);
    if (step === 3) {
      void radicar();
      return;
    }
    const n = Math.min(step + 1, ULTIMO_PASO);
    setStep(n);
    setMaxReached((m) => Math.max(m, n));
  };

  const retroceder = () => {
    setErrorPaso(null);
    setStep((s) => Math.max(s - 1, 0));
  };

  if (cargandoArranque) {
    return (
      <div className="pantalla-centrada">
        <Cargando mensaje="Preparando la solicitud…" />
      </div>
    );
  }

  if (errorArranque || !catalogos || !solicitud) {
    return (
      <div className="pantalla-centrada">
        <ErrorVista
          titulo="No se pudo iniciar la radicación"
          mensaje={errorArranque ?? 'El servidor no devolvió los datos necesarios.'}
          onReintentar={() => setIntento((n) => n + 1)}
        />
      </div>
    );
  }

  const esUltimoPaso = step === ULTIMO_PASO;
  const requeridoComprobante = resolverRequeridoComprobante(catalogos);

  return (
    <div className="app">
      <Sidebar step={step} maxReached={maxReached} onGoToStep={irAPaso} />

      <div className="main">
        <Topbar step={step} guardado={guardado} />

        <main className="content">
          {step === 0 && (
            <StepTipoSolicitud
              tramites={catalogos.tiposTramite}
              productos={catalogos.tiposProducto}
              tramite={tramite}
              producto={producto}
              onTramite={cambiarTramite}
              onProducto={cambiarProducto}
            />
          )}
          {step === 1 && (
            <StepDatosExpediente
              datos={datos}
              tocados={tocados}
              onCambiar={cambiarDato}
              onTocar={marcarTocado}
            />
          )}
          {step === 2 && (
            <StepDocumentos
              solicitudId={solicitud.id}
              modulos={catalogos.modulosCtd}
              documentos={documentos}
              omitirIds={[requeridoComprobante]}
              onDocumento={registrarDocumento}
              enlaces={enlaces}
              onEnlaces={setEnlaces}
              noIncluidaEnNormas={leerNoIncluida(datos)}
              onNoIncluidaEnNormas={declararNoIncluida}
            />
          )}
          {step === 3 && (
            <StepPago
              solicitudId={solicitud.id}
              tarifas={catalogos.tarifas}
              metodosPago={catalogos.metodosPago}
              tarifaCodigo={tarifaCodigo}
              metodoPago={metodoPago}
              comprobante={comprobante}
              valorPagado={valorPagado}
              fechaPago={fechaPago}
              requeridoComprobante={requeridoComprobante}
              documentoComprobante={documentos[requeridoComprobante] ?? null}
              onTarifa={cambiarTarifa}
              onMetodoPago={cambiarMetodoPago}
              onComprobante={cambiarComprobante}
              onValorPagado={cambiarValorPagado}
              onFechaPago={cambiarFechaPago}
              onDocumento={registrarDocumento}
            />
          )}
          {step === 4 && <StepConfirmacion resultado={resultado} />}
        </main>

        <footer className="footerbar">
          <button
            type="button"
            className="btn-back"
            disabled={step === 0 || esUltimoPaso}
            onClick={retroceder}
          >
            Atrás
          </button>

          {errorPaso ? (
            <div className="footerbar__error" role="alert">
              {errorPaso}
            </div>
          ) : null}

          {esUltimoPaso ? (
            <div className="footerbar__done">Trámite completado</div>
          ) : (
            <button type="button" className="btn-next" onClick={avanzar} disabled={radicando}>
              {step === 3 ? (radicando ? 'Radicando…' : 'Confirmar y radicar') : 'Continuar'}
            </button>
          )}
        </footer>
      </div>
    </div>
  );
}
