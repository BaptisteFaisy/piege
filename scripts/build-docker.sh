#!/usr/bin/env bash
# build-docker.sh — construit l'image Piège, lance un conteneur de smoke-test
# et vérifie que l'API répond. Aucune dépendance tierce dans l'image.
set -euo pipefail

IMAGE="${IMAGE:-piege:latest}"
PORT="${PORT:-8080}"

echo "==> Construction de l'image ${IMAGE}"
docker build -t "${IMAGE}" .

echo "==> Smoke-test : démarrage d'un conteneur éphémère"
CID="$(docker run -d -p "${PORT}:8080" "${IMAGE}")"
trap 'docker rm -f "${CID}" >/dev/null 2>&1 || true' EXIT

echo "==> Attente de disponibilité (30 s max)"
for _ in $(seq 1 30); do
  if curl -fsS -o /dev/null "http://127.0.0.1:${PORT}/api/health" \
       -H "Authorization: Bearer jeton:TEN-demo:analyste" 2>/dev/null; then
    echo "OK — API joignable sur http://127.0.0.1:${PORT}/"
    echo "Portail : http://127.0.0.1:${PORT}/"
    exit 0
  fi
  sleep 1
done

echo "ÉCHEC — l'API n'a pas répondu dans le délai" >&2
docker logs "${CID}" 2>&1 | tail -20 >&2
exit 1
