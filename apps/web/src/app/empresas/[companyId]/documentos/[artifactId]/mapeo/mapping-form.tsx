'use client';

import Link from 'next/link';
import { useActionState, useState } from 'react';

import type { Blocker, ColumnProfile, PreviewPage } from '@/lib/api';
import { withFlowContext } from '@/lib/navigation';
import {
  approveOverrideAction,
  applyApprovedCorrectionsAction,
  continueDatasetAction,
  createMappingAction,
  decideAmbiguityAction,
  prepareDatasetAction,
  publishDatasetAction,
  reviewCorrectionAction,
  rejectDatasetAction,
  type DecisionState,
  type CorrectionApplicationState,
  type MappingState,
  type PrepareState,
  type PublishState,
  type ReviewState,
} from '../../../../../actions';

/** Los campos canonicos, con el nombre que una persona reconoce. */
const FIELDS: { id: string; label: string; hint: string }[] = [
  { id: 'occurred_on', label: 'Fecha', hint: 'obligatoria' },
  { id: 'description', label: 'Descripcion', hint: 'obligatoria' },
  { id: 'reference', label: 'Referencia', hint: 'opcional' },
  { id: 'amount', label: 'Importe', hint: 'con signo o con direccion aparte' },
  { id: 'debit', label: 'Debito', hint: 'solo si van en columnas separadas' },
  { id: 'credit', label: 'Credito', hint: 'solo si van en columnas separadas' },
  { id: 'direction', label: 'Direccion', hint: 'solo si el fichero la trae' },
];

const KIND_LABELS: Record<string, string> = {
  date_format: 'convenio de fecha',
  decimal_format: 'convenio decimal',
  direction_sign: 'convenio de signo',
  currency: 'moneda',
  column_role: 'papel de la columna',
  timezone: 'zona horaria',
};

const VALUE_LABELS: Record<string, string> = {
  iso: 'aaaa-mm-dd',
  dmy: 'dd/mm/aaaa',
  mdy: 'mm/dd/aaaa',
  dot: '1,234.56 (punto decimal)',
  comma: '1.234,56 (coma decimal)',
};

const MAPPING_INITIAL: MappingState = {
  error: null,
  mappingVersionId: null,
  blockers: [],
};
const DECISION_INITIAL: DecisionState = { error: null, resolved: null };
const CORRECTION_APPLICATION_INITIAL: CorrectionApplicationState = {
  error: null,
  done: null,
  resultDatasetVersionId: null,
};
const PREPARE_INITIAL: PrepareState = {
  error: null,
  datasetVersionId: null,
  summary: null,
  rejections: [],
};
const PUBLISH_INITIAL: PublishState = { error: null, published: null };
const REVIEW_INITIAL: ReviewState = { error: null, done: null };

/**
 * Selector visual de columnas.
 *
 * Cada campo canonico elige su columna de una lista que **son las columnas del
 * fichero**, con su cabecera y el tipo que el perfilador infirio. Escribir un
 * indice a mano seria pedirle a una persona que cuente columnas, y contar mal la
 * columna del importe mueve dinero sin que nada falle.
 */
export function MappingForm({
  companyId,
  artifactId,
  sources,
  selectedDataSourceId,
  page,
  movementPage,
  preview,
}: {
  companyId: string;
  artifactId: string;
  sources: {
    data_source_id: string;
    display_name: string;
    source_family: string;
    status: string;
  }[];
  selectedDataSourceId: string;
  page: number;
  movementPage: number;
  preview: PreviewPage;
}) {
  const [state, action, pending] = useActionState(createMappingAction, MAPPING_INITIAL);
  const [directionMode, setDirectionMode] = useState('signed_amount');
  const [dataSourceId, setDataSourceId] = useState(selectedDataSourceId);

  const columns: ColumnProfile[] = preview.columns.length
    ? preview.columns
    : preview.header.map((header, index) => ({
        index,
        header,
        non_empty: 0,
        empty: 0,
        min_length: 0,
        max_length: 0,
        inferred_type: 'text',
        type_confidence: 0,
        ambiguous: false,
      }));

  return (
    <form className="upload" action={action}>
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="artifactId" value={artifactId} />

      <label htmlFor="dataSourceId">
        Fuente de estos datos
        <select
          id="dataSourceId"
          name="dataSourceId"
          value={dataSourceId}
          onChange={(event) => setDataSourceId(event.target.value)}
          required
        >
          <option value="">elige una fuente</option>
          {sources.map((source) => (
            <option key={source.data_source_id} value={source.data_source_id}>
              {source.display_name} · {source.source_family} · {source.status}
            </option>
          ))}
        </select>
      </label>
      {sources.length === 0 ? (
        <p className="notice error" role="status">
          No hay fuentes autorizadas disponibles. Crea o recupera una fuente
          antes de guardar el mapeo.
        </p>
      ) : null}

      <label htmlFor="displayName">
        Nombre del mapeo
        <input
          id="displayName"
          name="displayName"
          type="text"
          maxLength={160}
          defaultValue={`Mapeo de ${preview.header.join(', ').slice(0, 60)}`}
        />
      </label>

      <fieldset>
        <legend>Que columna es cada cosa</legend>
        {FIELDS.map((field) => (
          <label key={field.id} htmlFor={`col_${field.id}`}>
            {field.label} <span className="meta">({field.hint})</span>
            <select id={`col_${field.id}`} name={`col_${field.id}`} defaultValue="">
              <option value="">sin asignar</option>
              {columns.map((column) => (
                <option key={column.index} value={column.index}>
                  {column.index + 1}. {column.header} · {column.inferred_type}
                  {column.ambiguous ? ' (ambigua)' : ''}
                </option>
              ))}
            </select>
          </label>
        ))}
      </fieldset>

      <fieldset>
        <legend>Como se leen los valores</legend>
        <label htmlFor="dateFormat">
          Convenio de fecha
          <select id="dateFormat" name="dateFormat" defaultValue="dmy">
            <option value="dmy">dd/mm/aaaa</option>
            <option value="mdy">mm/dd/aaaa</option>
            <option value="iso">aaaa-mm-dd</option>
          </select>
        </label>
        <label htmlFor="decimalFormat">
          Convenio decimal
          <select id="decimalFormat" name="decimalFormat" defaultValue="comma">
            <option value="comma">1.234,56</option>
            <option value="dot">1,234.56</option>
          </select>
        </label>
        <label htmlFor="currency">
          Moneda
          <input
            id="currency"
            name="currency"
            type="text"
            maxLength={3}
            minLength={3}
            defaultValue="COP"
            pattern="[A-Za-z]{3}"
            required
          />
        </label>
        <label htmlFor="directionMode">
          De donde sale la direccion
          <select
            id="directionMode"
            name="directionMode"
            value={directionMode}
            onChange={(event) => setDirectionMode(event.target.value)}
          >
            <option value="signed_amount">del signo del importe</option>
            <option value="debit_credit_columns">de dos columnas separadas</option>
            <option value="explicit_direction">de una columna que la dice</option>
          </select>
        </label>
        <p className="meta">
          La direccion se guarda aparte y el importe siempre positivo. Un menos
          delante de un numero significa cosas distintas en cada banco, y guardar
          esa ambiguedad dentro del importe la propaga a todo lo que venga despues.
        </p>
      </fieldset>

      <fieldset>
        <legend>Donde empieza la tabla</legend>
        <label htmlFor="headerRow">
          Fila de la cabecera
          <input
            id="headerRow"
            name="headerRow"
            type="number"
            min={1}
            defaultValue={preview.header_row}
          />
        </label>
        <label htmlFor="firstDataRow">
          Primera fila de datos
          <input
            id="firstDataRow"
            name="firstDataRow"
            type="number"
            min={1}
            defaultValue={preview.first_data_row}
          />
        </label>
      </fieldset>

      <div>
        <button type="submit" disabled={pending || sources.length === 0}>
          {pending ? 'Guardando...' : 'Guardar mapeo'}
        </button>
      </div>

      {state.error ? (
        <p className="notice error" role="alert">
          {state.error}
        </p>
      ) : null}
      {state.mappingVersionId ? (
        <p className="notice ok" role="status">
          Mapeo guardado en borrador.
          {state.blockers.length > 0
            ? ` Quedan ${state.blockers.length} cosa(s) por resolver antes de poder preparar.`
            : ' No queda nada por resolver.'}
          {' '}
          <Link
            href={withFlowContext(
              `/empresas/${companyId}/documentos/${artifactId}/mapeo`,
              {
                documento: artifactId,
                fuente: dataSourceId,
                mapeo: state.mappingVersionId,
                pagina: page,
                movimientosPagina: movementPage,
              },
            )}
          >
            Abrir esta version
          </Link>
        </p>
      ) : null}
    </form>
  );
}

/** Resolucion explicita de una ambiguedad, con su motivo escrito. */
export function DecisionForm({
  companyId,
  artifactId,
  mappingVersionId,
  blocker,
}: {
  companyId: string;
  artifactId: string;
  mappingVersionId: string;
  blocker: Blocker;
}) {
  const [state, action, pending] = useActionState(
    decideAmbiguityAction,
    DECISION_INITIAL,
  );

  if (blocker.resolvable !== 'true') {
    return (
      <li>
        <strong>{blocker.code}</strong> · {blocker.location} · {blocker.detail}
        <p className="meta">
          Esto no se resuelve con una explicacion: hay que corregir el mapeo.
        </p>
      </li>
    );
  }

  return (
    <li>
      <strong>{KIND_LABELS[blocker.ambiguity_kind] ?? blocker.ambiguity_kind}</strong>{' '}
      en <code>{blocker.subject_ref}</code> · {blocker.detail}
      <form className="upload" action={action}>
        <input type="hidden" name="companyId" value={companyId} />
        <input type="hidden" name="artifactId" value={artifactId} />
        <input type="hidden" name="mappingVersionId" value={mappingVersionId} />
        <input type="hidden" name="ambiguityKind" value={blocker.ambiguity_kind} />
        <input type="hidden" name="subjectRef" value={blocker.subject_ref} />
        <input type="hidden" name="resolvedValue" value={blocker.expected_value} />
        <label htmlFor={`rationale_${blocker.subject_ref}`}>
          Confirmo{' '}
          <strong>
            {VALUE_LABELS[blocker.expected_value] ?? blocker.expected_value}
          </strong>{' '}
          porque
          <input
            id={`rationale_${blocker.subject_ref}`}
            name="rationale"
            type="text"
            maxLength={500}
            required
            placeholder="el banco emite dd/mm/aaaa en Colombia"
          />
        </label>
        <div>
          <button type="submit" disabled={pending}>
            {pending ? 'Registrando...' : 'Registrar la decision'}
          </button>
        </div>
        {state.error ? (
          <p className="notice error" role="alert">
            {state.error}
          </p>
        ) : null}
        {state.resolved ? (
          <p className="notice ok" role="status">
            Decidido y anotado. Queda escrito quien lo eligio y por que.
          </p>
        ) : null}
      </form>
    </li>
  );
}

/** Preparar es del preparador. El resumen sale antes de que nadie publique. */
export function PrepareForm({
  companyId,
  artifactId,
  mappingVersionId,
  accounts,
}: {
  companyId: string;
  artifactId: string;
  mappingVersionId: string;
  accounts: { account_id: string; label: string }[];
}) {
  const [state, action, pending] = useActionState(prepareDatasetAction, PREPARE_INITIAL);

  return (
    <form className="upload" action={action}>
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="artifactId" value={artifactId} />
      <input type="hidden" name="mappingVersionId" value={mappingVersionId} />
      <label htmlFor="financialAccountId">
        Cuenta contra la que se registran
        <select id="financialAccountId" name="financialAccountId" required>
          {accounts.length === 0 ? <option value="">no hay cuentas</option> : null}
          {accounts.map((account) => (
            <option key={account.account_id} value={account.account_id}>
              {account.label}
            </option>
          ))}
        </select>
      </label>
      <div>
        <button type="submit" disabled={pending || accounts.length === 0}>
          {pending ? 'Preparando...' : 'Preparar el conjunto canonico'}
        </button>
      </div>
      {state.error ? (
        <p className="notice error" role="alert">
          {state.error}
        </p>
      ) : null}
      {state.summary ? (
        <p className="notice ok" role="status">
          {state.summary}
        </p>
      ) : null}
      {state.rejections.length > 0 ? (
        <div className="card scroll">
          <div className="meta">Filas que no se pudieron leer</div>
          <table>
            <caption className="meta">
              Cada rechazo lleva su numero de fila del fichero, que es como se
              encuentra. Nunca lleva el valor que fallo.
            </caption>
            <thead>
              <tr>
                <th scope="col">Fila</th>
                <th scope="col">Motivo</th>
              </tr>
            </thead>
            <tbody>
              {state.rejections.map((item) => (
                <tr key={item.record_ordinal}>
                  <td className="when">{item.record_ordinal}</td>
                  <td>{item.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </form>
  );
}

/** Publicar es de otra persona, y el boton solo aparece si esa persona eres tu. */
export function PublishForm({
  companyId,
  artifactId,
  datasetVersionId,
  canPublish,
  reason,
}: {
  companyId: string;
  artifactId: string;
  datasetVersionId: string;
  canPublish: boolean;
  reason: string;
}) {
  const [state, action, pending] = useActionState(publishDatasetAction, PUBLISH_INITIAL);

  if (!canPublish) {
    return (
      <p className="notice" role="status">
        {reason}
      </p>
    );
  }

  return (
    <form className="upload" action={action}>
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="artifactId" value={artifactId} />
      <input type="hidden" name="datasetVersionId" value={datasetVersionId} />
      <div>
        <button type="submit" disabled={pending}>
          {pending ? 'Publicando...' : 'Publicar'}
        </button>
      </div>
      {state.error ? (
        <p className="notice error" role="alert">
          {state.error}
        </p>
      ) : null}
      {state.published ? (
        <p className="notice ok" role="status">
          {state.published}
        </p>
      ) : null}
    </form>
  );
}

/** El identificador basta: ni las huellas ni los valores viajan en el formulario. */
export function OverrideApprovalForm({
  companyId,
  artifactId,
  datasetVersionId,
  overrideId,
}: {
  companyId: string;
  artifactId: string;
  datasetVersionId: string;
  overrideId: string;
}) {
  const [state, action, pending] = useActionState(
    approveOverrideAction,
    REVIEW_INITIAL,
  );
  return (
    <form className="upload" action={action}>
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="artifactId" value={artifactId} />
      <input type="hidden" name="datasetVersionId" value={datasetVersionId} />
      <input type="hidden" name="overrideId" value={overrideId} />
      <button type="submit" disabled={pending}>
        {pending ? 'Aprobando...' : 'Aprobar excepcion'}
      </button>
      {state.error ? <p className="notice error" role="alert">{state.error}</p> : null}
      {state.done ? <p className="notice ok" role="status">{state.done}</p> : null}
    </form>
  );
}

export function CorrectionReviewForm({
  companyId,
  artifactId,
  datasetVersionId,
  overlayId,
}: {
  companyId: string;
  artifactId: string;
  datasetVersionId: string;
  overlayId: string;
}) {
  const [state, action, pending] = useActionState(
    reviewCorrectionAction,
    REVIEW_INITIAL,
  );
  const hint = `correction-review-hint-${overlayId}`;
  return (
    <form className="upload" action={action}>
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="artifactId" value={artifactId} />
      <input type="hidden" name="datasetVersionId" value={datasetVersionId} />
      <input type="hidden" name="overlayId" value={overlayId} />
      <label htmlFor={`correction-rationale-${overlayId}`}>Justificacion</label>
      <textarea
        id={`correction-rationale-${overlayId}`}
        name="rationale"
        required
        maxLength={500}
        aria-describedby={hint}
      />
      <p id={hint} className="meta">
        Aprobar no aplica el valor: autoriza crear una version nueva. El autor no
        puede revisar su propia propuesta.
      </p>
      <div className="actions">
        <button name="decision" value="approved" type="submit" disabled={pending}>
          {pending ? 'Guardando...' : 'Aprobar para reproceso'}
        </button>
        <button
          name="decision"
          value="rejected"
          type="submit"
          className="secondary"
          disabled={pending}
        >
          Rechazar propuesta
        </button>
      </div>
      {state.error ? <p className="notice error" role="alert">{state.error}</p> : null}
      {state.done ? <p className="notice ok" role="status">{state.done}</p> : null}
    </form>
  );
}

export function ApplyCorrectionsForm({
  companyId,
  artifactId,
  datasetVersionId,
  sourceId,
  mappingVersionId,
}: {
  companyId: string;
  artifactId: string;
  datasetVersionId: string;
  sourceId: string;
  mappingVersionId: string | null;
}) {
  const [state, action, pending] = useActionState(
    applyApprovedCorrectionsAction,
    CORRECTION_APPLICATION_INITIAL,
  );
  const resultHref = state.resultDatasetVersionId
    ? withFlowContext(
        `/empresas/${companyId}/documentos/${artifactId}/mapeo`,
        {
          documento: artifactId,
          fuente: sourceId,
          mapeo: mappingVersionId,
          dataset: state.resultDatasetVersionId,
          pagina: 0,
          movimientosPagina: 0,
        },
      )
    : null;
  return (
    <form className="upload" action={action}>
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="artifactId" value={artifactId} />
      <input type="hidden" name="datasetVersionId" value={datasetVersionId} />
      <p className="meta">
        Se creara una version validada nueva con todas las correcciones aprobadas.
        La evidencia y la version base no cambian; publicar sigue siendo una
        decision independiente.
      </p>
      <button type="submit" disabled={pending || resultHref !== null}>
        {pending ? 'Creando version...' : resultHref ? 'Version creada' : 'Aplicar correcciones aprobadas'}
      </button>
      {state.error ? <p className="notice error" role="alert">{state.error}</p> : null}
      {state.done ? <p className="notice ok" role="status">{state.done}</p> : null}
      {resultHref ? <p><Link href={resultHref}>Abrir la version corregida</Link></p> : null}
    </form>
  );
}

/** Rechazar conserva evidencia y bloquea publicar esta version. */
export function RejectDatasetForm({
  companyId,
  artifactId,
  datasetVersionId,
}: {
  companyId: string;
  artifactId: string;
  datasetVersionId: string;
}) {
  const [state, action, pending] = useActionState(
    rejectDatasetAction,
    REVIEW_INITIAL,
  );
  const hintId = `reject-hint-${datasetVersionId}`;
  return (
    <form className="upload" action={action}>
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="artifactId" value={artifactId} />
      <input type="hidden" name="datasetVersionId" value={datasetVersionId} />
      <label htmlFor={`reject-reason-${datasetVersionId}`}>Motivo del rechazo</label>
      <textarea
        id={`reject-reason-${datasetVersionId}`}
        name="reason"
        required
        maxLength={200}
        aria-describedby={hintId}
      />
      <p id={hintId} className="meta">
        Hasta 200 caracteres. El motivo se audita; no copies valores del extracto.
      </p>
      <button type="submit" className="secondary" disabled={pending}>
        {pending ? 'Rechazando...' : 'Rechazar esta version'}
      </button>
      {state.error ? <p className="notice error" role="alert">{state.error}</p> : null}
      {state.done ? <p className="notice ok" role="status">{state.done}</p> : null}
    </form>
  );
}

/** Continua una preparacion que se quedo a medias. */
export function ContinueForm({
  companyId,
  artifactId,
  datasetVersionId,
}: {
  companyId: string;
  artifactId: string;
  datasetVersionId: string;
}) {
  const [state, action, pending] = useActionState(continueDatasetAction, {
    error: null,
    progress: null,
  });

  return (
    <form className="upload" action={action}>
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="artifactId" value={artifactId} />
      <input type="hidden" name="datasetVersionId" value={datasetVersionId} />
      <div>
        <button type="submit" disabled={pending}>
          {pending ? 'Continuando...' : 'Continuar la preparacion'}
        </button>
      </div>
      <p className="meta">
        Cada tanda entra con su punto de control. Si esto se interrumpe, lo que
        entro se queda y lo que falta se retoma desde ahi: reanudar no repite.
      </p>
      {state.error ? (
        <p className="notice error" role="alert">
          {state.error}
        </p>
      ) : null}
      {state.progress ? (
        <p className="notice ok" role="status">
          {state.progress}
        </p>
      ) : null}
    </form>
  );
}
