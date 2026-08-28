import { RegistrationForm } from './registration-form';

type RegistrationPageProps = {
  searchParams: Promise<{ error?: string | string[] }>;
};

export default async function RegistrationPage({ searchParams }: RegistrationPageProps) {
  const supplied = (await searchParams).error;
  const errorCode = Array.isArray(supplied) ? supplied[0] : supplied;
  return (
    <RegistrationForm
      inviteRequired={process.env.FINCILIA_REGISTRATION_INVITE_REQUIRED === 'true'}
      managedIdentity={process.env.FINCILIA_OIDC_ENABLED === 'true'}
      managedError={errorCode === 'managed-registration'}
    />
  );
}
