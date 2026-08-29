import { redirect } from 'next/navigation';

import { RegistrationForm } from './registration-form';

type RegistrationPageProps = {
  searchParams: Promise<{ error?: string | string[] }>;
};

export default async function RegistrationPage({ searchParams }: RegistrationPageProps) {
  const managedIdentity = process.env.FINCILIA_OIDC_ENABLED === 'true';
  if (managedIdentity &&
      process.env.FINCILIA_OIDC_REGISTRATION_MODE !== 'public_google') {
    redirect('/entrar?error=registration-closed');
  }
  const supplied = (await searchParams).error;
  const errorCode = Array.isArray(supplied) ? supplied[0] : supplied;
  return (
    <RegistrationForm
      inviteRequired={process.env.FINCILIA_REGISTRATION_INVITE_REQUIRED === 'true'}
      managedIdentity={managedIdentity}
      managedError={errorCode === 'managed-registration' ||
        errorCode === 'account-required'}
    />
  );
}
