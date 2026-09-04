# Imagen de la web. Base fijada por digest: una etiqueta puede reapuntar a otros
# bytes manana, y entonces «la misma imagen» deja de serlo.
FROM node:22-alpine3.23@sha256:46825fbbd4e996a78b7a2cdc08d75e38a5a505bdab95dcda55605359bf124bc6 AS build

ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production

WORKDIR /build

# La base oficial aun trae 3.5.7-r0. Las versiones exactas corrigen las CVE
# criticas que el scan ECR rechazo; sin pin, un mirror puede cambiar el build.
RUN apk update \
    && apk add --no-cache --upgrade libcrypto3=3.5.8-r0 libssl3=3.5.8-r0 \
    && rm -rf /var/cache/apk/*

# `npm ci` instala exactamente lo que dice el lock y falla si no coincide, en vez
# de resolver de nuevo el arbol y traer otra cosa que la que se reviso.
# `--ignore-scripts`: un postinstall es codigo arbitrario de un tercero corriendo
# en la construccion.
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --ignore-scripts --include=dev

COPY apps/web/next.config.mjs apps/web/tsconfig.json apps/web/eslint.config.mjs apps/web/vitest.config.mts apps/web/vitest.setup.ts ./
COPY apps/web/public ./public
COPY apps/web/src ./src
RUN npm run typecheck && npm run build

# --------------------------------------------------------------------------- #
# Runtime: solo lo que hace falta para servir.
# --------------------------------------------------------------------------- #
FROM node:22-alpine3.23@sha256:46825fbbd4e996a78b7a2cdc08d75e38a5a505bdab95dcda55605359bf124bc6

ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

WORKDIR /app

RUN apk update \
    && apk add --no-cache --upgrade libcrypto3=3.5.8-r0 libssl3=3.5.8-r0 \
    && rm -rf /var/cache/apk/*

# La salida `standalone` trae su propio servidor y solo las dependencias que
# usa. `node_modules` entero en la imagen final es superficie que nadie audita.
COPY --from=build /build/.next/standalone ./
COPY --from=build /build/.next/static ./.next/static
COPY --from=build /build/public ./public

RUN adduser --system --uid 10002 --home /home/fincilia fincilia
USER 10002

EXPOSE 3000
CMD ["node", "server.js"]
