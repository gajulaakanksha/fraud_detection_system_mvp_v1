# Build stage
FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# API_BASE_URL is baked in at build time (webpack.DefinePlugin, see
# webpack.config.mjs) -- left empty here on purpose. nginx.conf proxies
# /v1/* on this same origin, so the frontend should call relative paths,
# not a separate backend address.
ARG API_BASE_URL=""
RUN printf "API_BASE_URL=%s\n" "$API_BASE_URL" > .env && npm run build

# Serve stage
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
