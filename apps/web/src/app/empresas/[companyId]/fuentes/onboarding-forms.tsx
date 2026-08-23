'use client';

import { useActionState, useState } from 'react';

import type { Account, Source } from '@/lib/api';
import {
  closeAccountAction,
  createAccountAction,
  createSourceAction,
  linkAccountAction,
  setCycleAction,
  type OnboardingState,
} from '../../../actions';

const INITIAL: OnboardingState = { error: null, done: null };

const ACCOUNT_FAMILIES: { id: string; label: string }[] = [
  { id: 'bank_account', label: 'Cuenta bancaria' },
  { id: 'payment_gateway', label: 'Pasarela de pagos' },
  { id: 'merchant_acquirer', label: 'Adquirente' },
  { id: 'marketplace', label: 'Marketplace' },
  { id: 'digital_wallet', label: 'Billetera digital' },
  { id: 'billing_erp', label: 'ERP de facturacion' },
  { id: 'accounting_ledger', label: 'Libro contable' },
];

const SOURCE_FAMILIES = ACCOUNT_FAMILIES.concat([
  { id: 'tax_documents_received', label: 'Documentos tributarios recibidos' },
  { id: 'supporting_evidence', label: 'Soportes' },
  { id: 'reference_data', label: 'Datos de referencia' },
]);

const TIMEZONES = ['America/Bogota', 'America/Lima', 'America/Mexico_City',
                   'America/Santiago', 'America/Argentina/Buenos_Aires', 'UTC'];

const ROLES: { id: string; label: string; hint: string }[] = [
  { id: 'primary', label: 'Principal', hint: 'contra la que se publica' },
  { id: 'settlement', label: 'Liquidacion', hint: 'donde aterriza el dinero' },
  { id: 'ledger', label: 'Libro contable', hint: 'contra la que se concilia' },
  { id: 'supporting', label: 'Soporte', hint: 'evidencia adicional' },
];

function Feedback({ state }: { state: OnboardingState }) {
  return (
    <>
      {state.error ? (
        <p className="notice error" role="alert">
          {state.error}
        </p>
      ) : null}
      {state.done ? (
        <p className="notice ok" role="status">
          {state.done}
        </p>
      ) : null}
    </>
  );
}

/**
 * Alta de una cuenta.
 *
 * El identificador se pide una vez y no vuelve a aparecer en ningun sitio: la
 * API lo convierte en huella con clave y devuelve la cola visible. Por eso el
 * campo avisa de lo que va a pasar con el, en vez de dejar que alguien suponga
 * que queda guardado.
 */
export function AccountForm({ companyId }: { companyId: string }) {
  const [state, action, pending] = useActionState(createAccountAction, INITIAL);

  return (
    <form className="upload" action={action}>
      <input type="hidden" name="companyId" value={companyId} />
      <label htmlFor="account_displayName">
        Nombre visible
        <input id="account_displayName" name="displayName" type="text"
               maxLength={160} required placeholder="Cuenta corriente principal" />
      </label>
      <label htmlFor="account_family">
        Que clase de cuenta es
        <select id="account_family" name="accountFamily" defaultValue="bank_account">
          {ACCOUNT_FAMILIES.map((family) => (
            <option key={family.id} value={family.id}>{family.label}</option>
          ))}
        </select>
      </label>
      <label htmlFor="account_identifier">
        Identificador de la cuenta
        <input id="account_identifier" name="identifier" type="text" minLength={4}
               maxLength={64} required autoComplete="off"
               aria-describedby="account_identifier_help" />
      </label>
      <p className="meta" id="account_identifier_help">
        No se guarda. Se convierte en una huella con clave, y de lo que escribas
        aqui solo quedan los cuatro ultimos digitos, que es lo unico que hace
        falta para reconocerla.
      </p>
      <label htmlFor="account_currency">
        Moneda
        <select id="account_currency" name="currency" defaultValue="COP">
          <option value="COP">COP</option>
          <option value="USD">USD</option>
          <option value="EUR">EUR</option>
        </select>
      </label>
      <label htmlFor="account_timezone">
        Zona horaria
        <select id="account_timezone" name="timezone" defaultValue="America/Bogota">
          {TIMEZONES.map((zone) => <option key={zone} value={zone}>{zone}</option>)}
        </select>
      </label>
      <div>
        <button type="submit" disabled={pending}>
          {pending ? 'Creando...' : 'Crear cuenta'}
        </button>
      </div>
      <Feedback state={state} />
    </form>
  );
}

/** Suspender o cerrar una cuenta. **Nunca borrarla.** */
export function AccountStatusForm({
  companyId,
  account,
}: {
  companyId: string;
  account: Account;
}) {
  const [state, action, pending] = useActionState(closeAccountAction, INITIAL);
  const [status, setStatus] = useState(account.status === 'active' ? 'suspended' : 'active');

  return (
    <form className="upload" action={action}>
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="accountId" value={account.account_id} />
      <label htmlFor={`status_${account.account_id}`}>
        Estado
        <select id={`status_${account.account_id}`} name="status" value={status}
                onChange={(event) => setStatus(event.target.value)}>
          <option value="active">Activa</option>
          <option value="suspended">Suspendida</option>
          <option value="closed">Cerrada</option>
        </select>
      </label>
      {status !== 'active' ? (
        <label htmlFor={`reason_${account.account_id}`}>
          Por que
          <input id={`reason_${account.account_id}`} name="reason" type="text"
                 maxLength={200} required
                 placeholder="el banco cancelo la cuenta en marzo" />
        </label>
      ) : null}
      <div>
        <button type="submit" disabled={pending}>
          {pending ? 'Guardando...' : 'Guardar estado'}
        </button>
      </div>
      <p className="meta">
        Una cuenta no se borra. Si tiene movimientos publicados detras,
        borrarla dejaria hechos economicos apuntando a algo que nadie puede
        explicar.
      </p>
      <Feedback state={state} />
    </form>
  );
}

export function SourceForm({ companyId }: { companyId: string }) {
  const [state, action, pending] = useActionState(createSourceAction, INITIAL);

  return (
    <form className="upload" action={action}>
      <input type="hidden" name="companyId" value={companyId} />
      <label htmlFor="source_displayName">
        Nombre visible
        <input id="source_displayName" name="displayName" type="text" maxLength={160}
               required placeholder="Extracto Bancolombia" />
      </label>
      <label htmlFor="source_family">
        De donde viene
        <select id="source_family" name="sourceFamily" defaultValue="bank_account">
          {SOURCE_FAMILIES.map((family) => (
            <option key={family.id} value={family.id}>{family.label}</option>
          ))}
        </select>
      </label>
      <label htmlFor="source_purpose">
        Para que se usa
        <input id="source_purpose" name="purposeCode" type="text" minLength={3}
               maxLength={64} defaultValue="operational" />
      </label>
      <label htmlFor="source_timezone">
        Zona horaria
        <select id="source_timezone" name="timezone" defaultValue="America/Bogota">
          {TIMEZONES.map((zone) => <option key={zone} value={zone}>{zone}</option>)}
        </select>
      </label>
      <div>
        <button type="submit" disabled={pending}>
          {pending ? 'Creando...' : 'Crear fuente'}
        </button>
      </div>
      <Feedback state={state} />
    </form>
  );
}

/** Vincula una fuente con una cuenta y dice que papel juega. */
export function LinkForm({
  companyId,
  source,
  accounts,
}: {
  companyId: string;
  source: Source;
  accounts: Account[];
}) {
  const [state, action, pending] = useActionState(linkAccountAction, INITIAL);
  const usable = accounts.filter((account) => account.status === 'active');

  return (
    <form className="upload" action={action}>
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="sourceId" value={source.data_source_id} />
      <label htmlFor={`link_account_${source.data_source_id}`}>
        Cuenta
        <select id={`link_account_${source.data_source_id}`} name="accountId" required>
          {usable.length === 0 ? (
            <option value="">no hay cuentas activas</option>
          ) : null}
          {usable.map((account) => (
            <option key={account.account_id} value={account.account_id}>
              {account.display_name} · {account.currency_code}
              {account.identifier_last4 ? ` · ...${account.identifier_last4}` : ''}
            </option>
          ))}
        </select>
      </label>
      <label htmlFor={`link_role_${source.data_source_id}`}>
        Que papel juega
        <select id={`link_role_${source.data_source_id}`} name="relationRole"
                defaultValue="primary">
          {ROLES.map((role) => (
            <option key={role.id} value={role.id}>
              {role.label} — {role.hint}
            </option>
          ))}
        </select>
      </label>
      <div>
        <button type="submit" disabled={pending || usable.length === 0}>
          {pending ? 'Vinculando...' : 'Vincular'}
        </button>
      </div>
      <p className="meta">
        Una fuente se relaciona con varias cuentas: una pasarela liquida a una
        cuenta bancaria y concilia contra un libro contable. Solo hay una
        principal viva a la vez, porque «contra que cuenta se publica esto»
        tiene que tener una sola respuesta.
      </p>
      <Feedback state={state} />
    </form>
  );
}

/** El ciclo esperado, y los periodos que genera. */
export function CycleForm({
  companyId,
  source,
  people,
  today,
}: {
  companyId: string;
  source: Source;
  people: { subject_id: string; display_name: string }[];
  today: string;
}) {
  const [state, action, pending] = useActionState(setCycleAction, INITIAL);
  const [periodicity, setPeriodicity] = useState('monthly');

  return (
    <form className="upload" action={action}>
      <input type="hidden" name="companyId" value={companyId} />
      <input type="hidden" name="sourceId" value={source.data_source_id} />
      <label htmlFor={`cycle_periodicity_${source.data_source_id}`}>
        Cada cuanto se espera
        <select id={`cycle_periodicity_${source.data_source_id}`} name="periodicity"
                value={periodicity}
                onChange={(event) => setPeriodicity(event.target.value)}>
          <option value="monthly">Mensual</option>
          <option value="fortnightly">Quincenal</option>
          <option value="weekly">Semanal</option>
          <option value="custom">Cada N dias</option>
        </select>
      </label>
      {periodicity === 'custom' ? (
        <label htmlFor={`cycle_days_${source.data_source_id}`}>
          Cada cuantos dias
          <input id={`cycle_days_${source.data_source_id}`} name="customDays"
                 type="number" min={1} max={366} defaultValue={30} required />
        </label>
      ) : null}
      <label htmlFor={`cycle_due_${source.data_source_id}`}>
        Dias de plazo tras el cierre del periodo
        <input id={`cycle_due_${source.data_source_id}`} name="dueDayOffset"
               type="number" min={0} max={120} defaultValue={5} />
      </label>
      <label htmlFor={`cycle_grace_${source.data_source_id}`}>
        Dias de gracia antes de llamarlo atraso
        <input id={`cycle_grace_${source.data_source_id}`} name="graceDays"
               type="number" min={0} max={120} defaultValue={3} />
      </label>
      <label htmlFor={`cycle_owner_${source.data_source_id}`}>
        Quien responde de que llegue
        <select id={`cycle_owner_${source.data_source_id}`} name="responsible" required>
          {people.map((person) => (
            <option key={person.subject_id} value={person.subject_id}>
              {person.display_name}
            </option>
          ))}
        </select>
      </label>
      <label htmlFor={`cycle_anchor_${source.data_source_id}`}>
        Desde cuando
        <input id={`cycle_anchor_${source.data_source_id}`} name="anchorDate"
               type="date" required defaultValue={today.slice(0, 8) + '01'} />
      </label>
      <label htmlFor={`cycle_until_${source.data_source_id}`}>
        Calcular periodos hasta
        <input id={`cycle_until_${source.data_source_id}`} name="until" type="date"
               defaultValue={today} />
      </label>
      <input type="hidden" name="timezone" value={source.timezone} />
      <div>
        <button type="submit" disabled={pending || people.length === 0}>
          {pending ? 'Guardando...' : 'Guardar ciclo'}
        </button>
      </div>
      <Feedback state={state} />
    </form>
  );
}
