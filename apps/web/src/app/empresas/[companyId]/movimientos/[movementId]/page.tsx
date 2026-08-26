import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';

import {
  ApiError,
  fetchCompany,
  fetchCorrections,
  fetchCorrectionTargets,
  fetchDataset,
  fetchMapping,
  fetchMovement,
} from '@/lib/api';
import {
  CORRECTION_FIELD_LABELS,
  CORRECTION_STATUS_LABELS,
} from '@/lib/corrections';
import {
  pageFromQuery,
  withFlowContext,
} from '@/lib/navigation';
import { readSession } from '@/lib/session';

import { CorrectionProposalForm } from './correction-form';

export const dynamic = 'force-dynamic';

const FIELD_LABELS: Record<string, string> = {
  occurred_on: 'Fecha',
  description: 'Descripcion',
  reference: 'Referencia',
  amount: 'Importe',
  direction: 'Direccion',
  currency: 'Moneda',
  debit: 'Debito',
  credit: 'Credito',
};

const STAGE_LABELS: Record<string, string> = {
  artifact_version: 'la evidencia original',
  raw_locator: 'la celda exacta',
  extracted_field: 'el texto leido',
  transformed_value: 'el valor tipado',
  source_record_field: 'el campo del registro',
  financial_fact_field: 'el campo publicado',
};

const OPERATION_LABELS: Record<string, string> = {
  derived_from: 'el valor fluyo',
  decided_using: 'alguien lo eligio',
  included_in_snapshot: 'quedo sellado',
  overlay_applied: 'un overlay lo cambio',
  superseded_by: 'lo sustituyo otra version',
  redacted_from: 'se minimizo',
};

const TRANSFORM_LABELS: Record<string, string> = {
  verbatim: 'tal cual venia',
  'parse_date:dmy': 'leido como dd/mm/aaaa',
  'parse_date:mdy': 'leido como mm/dd/aaaa',
  'parse_date:iso': 'leido como aaaa-mm-dd',
  'normalise_amount:comma': 'leido con coma decimal',
  'normalise_amount:dot': 'leido con punto decimal',
  'resolve_direction:signed_amount': 'direccion tomada del signo',
  'resolve_direction:debit_credit_columns': 'direccion tomada de debito y credito',
  'resolve_direction:explicit_direction': 'direccion declarada por el fichero',
  normalise_reference: 'referencia normalizada para buscar',
  declared_currency: 'moneda declarada en el mapeo',
};

function money(amount: string, currency: string): string {
  // Punto fijo, sin `Number`: convertir a coma flotante para ensenar un importe
  // es perderlo en el unico sitio donde no se puede perder.
  const [whole = '0', fraction = ''] = amount.split('.');
  const trimmed = fraction.replace(/0+$/, '');
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return `${grouped}${trimmed ? `,${trimmed}` : ''} ${currency}`;
}

export default async function MovementPage({
  params,
  searchParams,
}: {
  params: Promise<{ companyId: string; movementId: string }>;
  searchParams: Promise<{
    pagina?: string | string[];
    movimientosPagina?: string | string[];
  }>;
}) {
  const session = await readSession();
  if (!session) {
    redirect('/entrar');
  }
  const [{ companyId, movementId }, query] = await Promise.all([params, searchParams]);

  let company;
  let movement;
  let dataset;
  let mapping;
  let targets;
  let corrections;
  try {
    [company, movement] = await Promise.all([
      fetchCompany(session.token, companyId),
      fetchMovement(session.token, companyId, movementId),
    ]);
    // El contexto de regreso se deriva de la cadena autorizada, no de UUID que
    // envie el navegador: movimiento -> dataset -> mapping -> fuente/artefacto.
    dataset = await fetchDataset(
      session.token,
      companyId,
      movement.dataset_version_id,
    );
    mapping = await fetchMapping(
      session.token,
      companyId,
      dataset.mapping_version_id,
    );
    [targets, corrections] = await Promise.all([
      fetchCorrectionTargets(
        session.token, companyId, movement.dataset_version_id, movementId,
      ),
      fetchCorrections(session.token, companyId, movement.dataset_version_id),
    ]);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect('/entrar');
    }
    if (error instanceof ApiError && error.status === 404) {
      notFound();
    }
    if (error instanceof ApiError && error.status === 403) {
      return (
        <main>
          <header className="bar">
            <h1>Sin acceso</h1>
            <Link href={`/empresas/${companyId}`}>Volver</Link>
          </header>
          <p className="card">
            Esta cuenta no tiene acceso vigente a lo que has pedido.
          </p>
        </main>
      );
    }
    throw error;
  }

  const artifactId = mapping.artifact_id;
  const flowContext = {
    documento: artifactId,
    fuente: mapping.data_source_id,
    mapeo: mapping.mapping_version_id,
    // Se deriva de la cadena autorizada movimiento -> dataset, no de la URL.
    dataset: movement.dataset_version_id,
    pagina: pageFromQuery(query.pagina),
    movimientosPagina: pageFromQuery(query.movimientosPagina),
  };

  const cellOf = (field: string) =>
    movement.lineage.find((step) => step.field === field)?.cell ?? null;
  const movementCorrections = corrections.filter(
    (item) => item.movement_id === movement.movement_id,
  );

  return (
    <main>
      <header className="bar">
        <div>
          <h1>{money(movement.amount, movement.currency)}</h1>
          <span className="who">
            {movement.direction === 'inflow' ? 'entrada' : 'salida'} ·{' '}
            {movement.occurred_on} · fila {movement.record_ordinal} de{' '}
            {movement.origin.filename}
          </span>
        </div>
        <nav aria-label="Navegacion del movimiento">
          <Link
            href={withFlowContext(
              artifactId
                ? `/empresas/${companyId}/documentos/${artifactId}/mapeo`
                : `/empresas/${companyId}`,
              flowContext,
            )}
          >
            Volver
          </Link>
        </nav>
      </header>

      <section className="card" aria-label="El hecho economico">
        <div className="meta">
          Conjunto <strong>{movement.dataset_state}</strong> · estado del
          movimiento <strong>{movement.state}</strong> · tipo {movement.kind}
        </div>
        <dl>
          <dt>Descripcion</dt>
          <dd>{movement.description}</dd>
          <dt>Referencia</dt>
          <dd>{movement.reference ?? 'sin referencia'}</dd>
          <dt>Ocurrio</dt>
          <dd>{movement.occurred_on}</dd>
          <dt>Se asento</dt>
          <dd>{movement.posted_on ?? 'el fichero no lo dice'}</dd>
          <dt>Fecha valor</dt>
          <dd>{movement.value_date ?? 'el fichero no lo dice'}</dd>
          <dt>Periodo contable</dt>
          <dd>{movement.accounting_date ?? 'todavia sin asignar'}</dd>
        </dl>
        <p className="meta">
          Cuando ocurrio, cuando se asento y a que periodo pertenece son tres
          fechas distintas. Confundirlas cambia de mes un asiento.
        </p>
      </section>

      <h2 id="correcciones">Correcciones controladas</h2>
      <section className="card" aria-labelledby="correcciones">
        <p className="meta">
          Una correccion es una propuesta append-only. No cambia el original ni
          este movimiento; si se aprueba, se aplicara al crear otra version del
          conjunto con linaje nuevo. Solo aparecen campos cuyo plan conserva las
          seis etapas necesarias para aplicar y comprobar el resultado.
        </p>
        {movementCorrections.length > 0 ? (
          <div className="correction-list">
            {movementCorrections.map((item) => {
              const target = targets.find((candidate) => candidate.field === item.field);
              return (
                <article className="notice" key={item.overlay_id}>
                  <strong>
                    {CORRECTION_FIELD_LABELS[item.field] ?? item.field}:{' '}
                    {target?.current_value ?? 'sin valor'} → {item.proposed_value}
                  </strong>
                  <div className="meta">
                    {CORRECTION_STATUS_LABELS[item.status] ?? item.status} · propuesta
                    por {item.author_name} · motivo {item.reason_code}
                  </div>
                  <p>{item.reason_comment}</p>
                  {item.review_rationale ? (
                    <p className="meta">
                      Revision de {item.reviewer_name}: {item.review_rationale}
                    </p>
                  ) : null}
                  {item.status === 'approved' ? (
                    <p className="notice warning">
                      Aprobada no significa aplicada. Este movimiento conserva{' '}
                      <strong>{target?.current_value ?? 'su valor actual'}</strong>.
                    </p>
                  ) : null}
                </article>
              );
            })}
          </div>
        ) : (
          <p className="notice">No hay correcciones propuestas para esta fila.</p>
        )}

        {dataset.state === 'validated' && company.permissions.includes('dataset.map') ? (
          <CorrectionProposalForm
            companyId={companyId}
            artifactId={mapping.artifact_id}
            datasetVersionId={dataset.dataset_version_id}
            movementId={movement.movement_id}
            targets={targets}
          />
        ) : (
          <p className="notice">
            {dataset.state !== 'validated'
              ? 'Esta version es historica o no esta validada; no admite propuestas.'
              : 'Tu rol puede revisar el movimiento, pero no proponer correcciones.'}
          </p>
        )}
      </section>

      <h2 id="origen">De donde sale</h2>
      <div className="card scroll" aria-labelledby="origen">
        <table>
          <caption className="meta">
            La fila del fichero, tal cual se leyo. La celda que produjo cada
            campo publicado va marcada.
          </caption>
          <thead>
            <tr>
              <th scope="col">Columna</th>
              <th scope="col">Valor original</th>
              <th scope="col">Produjo</th>
            </tr>
          </thead>
          <tbody>
            {movement.origin.values.map((value, index) => {
              const step = movement.lineage.find(
                (item) => item.cell.field_ordinal === index,
              );
              return (
                <tr key={index}>
                  <th scope="row" className="when">
                    {index + 1}
                  </th>
                  <td>{value}</td>
                  <td>
                    {step ? (
                      <span className="outcome">
                        {FIELD_LABELS[step.field] ?? step.field}
                      </span>
                    ) : (
                      <span className="meta">no se usa</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <h2 id="linaje">Como se leyo cada campo</h2>
      {!movement.lineage_complete ? (
        <p className="notice error" role="alert">
          El camino de este movimiento no se puede reconstruir entero
          {movement.lineage_reason ? `: ${movement.lineage_reason}` : '.'} Un
          importe sin camino hasta su celda no se puede auditar, y decirlo es
          mejor que ensenar un camino corto que parezca el contrato completo.
        </p>
      ) : null}

      {movement.lineage.map((step) => (
        <section className="card scroll" key={step.field}
                 aria-label={`Camino de ${FIELD_LABELS[step.field] ?? step.field}`}>
          <div className="meta">
            <strong>{FIELD_LABELS[step.field] ?? step.field}</strong> · fila{' '}
            {step.cell.record_ordinal} · columna{' '}
            {step.cell.field_ordinal !== undefined ? step.cell.field_ordinal + 1 : '—'}
            {' · '}bytes {step.cell.byte_start}–{step.cell.byte_end}
          </div>
          <table>
            <caption className="meta">
              Las seis etapas que exige el contrato de linaje, en orden. Cada una
              dice que tipo entra, que tipo sale y con que se leyo.
            </caption>
            <thead>
              <tr>
                <th scope="col">#</th>
                <th scope="col">Etapa</th>
                <th scope="col">Operacion</th>
                <th scope="col">De</th>
                <th scope="col">A</th>
                <th scope="col">Con que</th>
              </tr>
            </thead>
            <tbody>
              {step.stages.map((stage) => (
                <tr key={stage.step_ordinal}>
                  <th scope="row" className="when">{stage.step_ordinal}</th>
                  <td>{STAGE_LABELS[stage.stage] ?? stage.stage}</td>
                  <td>
                    <span className="outcome">
                      {OPERATION_LABELS[stage.operation] ?? stage.operation}
                    </span>
                  </td>
                  <td className="meta">{stage.input_semantic_type}</td>
                  <td className="meta">{stage.output_semantic_type}</td>
                  <td>
                    {TRANSFORM_LABELS[stage.transform_ref ?? ''] ??
                      stage.transform_ref ??
                      'sin transformacion'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="meta">
            Huella del valor publicado{' '}
            <code className="digest">{step.value_digest}</code>. El grafo guarda
            la huella y jamas el valor: uno que copiara importes seria una
            segunda base de datos que nadie protege.
          </p>
        </section>
      ))}

      <section className="card" aria-label="Evidencia">
        <div className="meta">Huella del artefacto</div>
        <code className="digest">
          {cellOf('amount')?.artifact_sha256 ??
            movement.origin.locator.artifact_sha256}
        </code>
        <p className="meta">
          Con la huella, la fila y el tramo de bytes se puede volver al fichero
          original y comprobar. Una coordenada que no permite comprobar no es una
          coordenada: es una promesa.
        </p>
      </section>
    </main>
  );
}
