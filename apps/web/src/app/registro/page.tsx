import { RegistrationForm } from './registration-form';

export default function RegistrationPage() {
  return (
    <RegistrationForm
      inviteRequired={process.env.FINCILIA_REGISTRATION_INVITE_REQUIRED === 'true'}
    />
  );
}
