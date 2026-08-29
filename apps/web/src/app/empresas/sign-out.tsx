import { signOutAction } from '../actions';
import { managedOidcEnabled } from '@/lib/managed-oidc';

export function SignOut() {
  if (managedOidcEnabled()) {
    return (
      <form action="/api/auth/oidc/logout" method="post">
        <button className="quiet" type="submit">
          Salir
        </button>
      </form>
    );
  }
  return (
    <form action={signOutAction}>
      <button className="quiet" type="submit">
        Salir
      </button>
    </form>
  );
}
