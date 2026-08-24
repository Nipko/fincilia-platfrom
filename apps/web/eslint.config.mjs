import next from 'eslint-config-next';

/**
 * ESLint se fija en la 9: la 10 rompe con el `@typescript-eslint` que arrastra
 * `eslint-config-next` (`scopeManager.addGlobals` ya no existe). Subir el linter
 * y quedarse sin linter no es subir nada.
 */
const config = [
  { ignores: ['.next/**', 'node_modules/**', 'next-env.d.ts'] },
  ...next,
];

export default config;
