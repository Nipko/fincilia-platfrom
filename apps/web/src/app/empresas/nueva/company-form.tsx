'use client';

import { useActionState, useState } from 'react';

import {
  provisionCompanyAction,
  type CompanyProvisionState,
} from '@/app/actions';
import type { ManagedFirm } from '@/lib/api';

const INITIAL: CompanyProvisionState = { error: null };

export function CompanyForm({
  firms,
  idempotencyKey,
  monthAnchor,
}: {
  firms: ManagedFirm[];
  idempotencyKey: string;
  monthAnchor: string;
}) {
  const [state, action, pending] = useActionState(provisionCompanyAction, INITIAL);
  const [includeSetup, setIncludeSetup] = useState(true);

  return (
    <form action={action} className="company-onboarding" aria-describedby="synthetic-company-notice">
      <input type="hidden" name="idempotencyKey" value={idempotencyKey} />

      <section className="card" aria-labelledby="company-identity-heading">
        <div className="section-heading">
          <div>
            <span className="step-number">1</span>
            <h2 id="company-identity-heading">Identidad de la empresa</h2>
          </div>
          <span className="tag">Requerido</span>
        </div>

        <div className="form-grid">
          <label>
            Firma responsable
            <select name="firmId" required defaultValue={firms[0]?.firm_id}>
              {firms.map((firm) => (
                <option value={firm.firm_id} key={firm.firm_id}>
                  {firm.legal_name} · {firm.firm_role}
                </option>
              ))}
            </select>
          </label>
          <label>
            Pais
            <select name="countryCode" required defaultValue="CO">
              <option value="CO">Colombia</option>
              <option value="MX">Mexico</option>
              <option value="CL">Chile</option>
              <option value="PE">Peru</option>
              <option value="AR">Argentina</option>
            </select>
          </label>
          <label className="form-span-2">
            Razon social
            <input name="legalName" minLength={2} maxLength={300} required
                   placeholder="Empresa Demostracion SAS" autoComplete="organization" />
          </label>
          <label className="form-span-2">
            Identificacion tributaria sintetica
            <input name="taxIdentifier" minLength={4} maxLength={64} required
                   placeholder="NIT-DEMO-2026-001" autoComplete="off" />
            <span className="field-help">Se tokeniza antes de tocar la base.</span>
          </label>
        </div>
      </section>

      <section className="card" aria-labelledby="initial-setup-heading">
        <div className="section-heading">
          <div>
            <span className="step-number">2</span>
            <h2 id="initial-setup-heading">Preparar la primera operacion</h2>
          </div>
          <label className="switch-label">
            <input name="includeSetup" type="checkbox" checked={includeSetup}
                   onChange={(event) => setIncludeSetup(event.target.checked)} />
            Crear ahora
          </label>
        </div>
        <p className="meta">
          Si lo activas, la cuenta, la fuente, el vinculo principal y el ciclo
          mensual nacen en la misma transaccion. Un fallo revierte todo.
        </p>

        {includeSetup ? (
          <div className="form-grid onboarding-setup">
            <label>
              Tipo de cuenta
              <select name="accountFamily" defaultValue="bank_account" required>
                <option value="bank_account">Cuenta bancaria</option>
                <option value="payment_gateway">Pasarela de pagos</option>
                <option value="merchant_acquirer">Adquirente</option>
                <option value="digital_wallet">Billetera digital</option>
                <option value="billing_erp">ERP de facturacion</option>
                <option value="accounting_ledger">Libro contable</option>
              </select>
            </label>
            <label>
              Moneda
              <select name="currencyCode" defaultValue="COP" required>
                <option value="COP">COP</option>
                <option value="USD">USD</option>
                <option value="EUR">EUR</option>
                <option value="MXN">MXN</option>
                <option value="CLP">CLP</option>
                <option value="PEN">PEN</option>
                <option value="ARS">ARS</option>
              </select>
            </label>
            <label>
              Nombre visible de la cuenta
              <input name="accountName" maxLength={160} required
                     defaultValue="Cuenta principal" />
            </label>
            <label>
              Identificador sintetico de cuenta
              <input name="accountIdentifier" minLength={4} maxLength={64}
                     required placeholder="CTA-DEMO-0001" autoComplete="off" />
            </label>
            <label>
              Tipo de fuente
              <select name="sourceFamily" defaultValue="bank_account" required>
                <option value="bank_account">Extracto bancario</option>
                <option value="payment_gateway">Reporte de pasarela</option>
                <option value="merchant_acquirer">Reporte de adquirente</option>
                <option value="marketplace">Marketplace</option>
                <option value="billing_erp">ERP de facturacion</option>
                <option value="accounting_ledger">Libro contable</option>
                <option value="tax_documents_received">Documentos tributarios</option>
                <option value="supporting_evidence">Soportes</option>
              </select>
            </label>
            <label>
              Nombre visible de la fuente
              <input name="sourceName" maxLength={160} required
                     defaultValue="Extracto mensual" />
            </label>
            <label>
              Inicio del ciclo
              <input name="anchorDate" type="date" required defaultValue={monthAnchor} />
            </label>
            <label>
              Zona horaria
              <select name="timezone" defaultValue="America/Bogota" required>
                <option value="America/Bogota">America/Bogota</option>
                <option value="America/Mexico_City">America/Mexico_City</option>
                <option value="America/Santiago">America/Santiago</option>
                <option value="America/Lima">America/Lima</option>
                <option value="America/Argentina/Buenos_Aires">America/Argentina/Buenos_Aires</option>
              </select>
            </label>
            <label>
              Dias para entrega
              <input name="dueDayOffset" type="number" min={0} max={120}
                     defaultValue={0} required />
            </label>
            <label>
              Dias de gracia
              <input name="graceDays" type="number" min={0} max={120}
                     defaultValue={3} required />
            </label>
          </div>
        ) : null}
      </section>

      {state.error ? <p className="notice error" role="alert">{state.error}</p> : null}

      <div className="company-onboarding__submit">
        <p className="meta">Al terminar entraras directamente a fuentes y cuentas.</p>
        <button type="submit" disabled={pending}>
          {pending ? 'Creando espacio operativo…' : 'Crear empresa y continuar'}
        </button>
      </div>
    </form>
  );
}
