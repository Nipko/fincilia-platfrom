'use client';

import { signOutAction } from '../actions';

export function SignOut() {
  return (
    <form action={signOutAction}>
      <button className="quiet" type="submit">
        Salir
      </button>
    </form>
  );
}
