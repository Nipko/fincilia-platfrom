# Imagen de la web. Base fijada por digest: una etiqueta puede reapuntar a otros
# bytes manana, y entonces «la misma imagen» deja de serlo.
FROM node@sha256:d649c27dae7ba0137b3cef5dd75baa422c08dc3d9e3fc0c23dfb172dc3cc6436 AS build

ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

WORKDIR /build

# `npm ci` instala exactamente lo que dice el lock y falla si no coincide, en vez
# de resolver de nuevo el arbol y traer otra cosa que la que se reviso.
# `--ignore-scripts`: un postinstall es codigo arbitrario de un tercero corriendo
# en la construccion.
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --ignore-scripts --include=dev

COPY apps/web/next.config.mjs apps/web/tsconfig.json apps/web/eslint.config.mjs apps/web/vitest.setup.ts ./
COPY apps/web/src ./src
RUN npm run typecheck && npm run build

# --------------------------------------------------------------------------- #
# Runtime: solo lo que hace falta para servir.
# --------------------------------------------------------------------------- #
FROM node@sha256:d649c27dae7ba0137b3cef5dd75baa422c08dc3d9e3fc0c23dfb172dc3cc6436

ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

WORKDIR /app

# La salida `standalone` trae su propio servidor y solo las dependencias que
# usa. `node_modules` entero en la imagen final es superficie que nadie audita.
COPY --from=build /build/.next/standalone ./
COPY --from=build /build/.next/static ./.next/static

RUN useradd --system --uid 10002 --create-home fincilia
USER 10002

EXPOSE 3000
CMD ["node", "server.js"]
