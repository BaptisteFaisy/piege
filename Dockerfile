# Piège — image de démonstration / déploiement on-prem.
# Le cœur n'a AUCUNE dépendance tierce : l'image reste minuscule et l'API
# tourne hors ligne. Un utilisateur non-root exécute le serveur (bonne hygiène).
FROM python:3.13-slim

# Métadonnées
LABEL org.opencontainers.image.title="Piège" \
      org.opencontainers.image.description="Pentest continu des applications d'IA générative" \
      org.opencontainers.image.licenses="Proprietary"

WORKDIR /app

# Le cœur est stdlib : pas de requirements à installer. On installe le paquet
# en mode éditable pour que `piege` et `python -m piege.*` soient disponibles.
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -e .

# Données de démonstration et portail statique (servis par le même serveur).
COPY catalogue ./catalogue
COPY demo ./demo
COPY portal ./portal

# Utilisateur non-root
RUN useradd --create-home --uid 10001 piege \
    && mkdir -p /data \
    && chown -R piege:piege /app /data
USER piege

ENV PYTHONPATH=src \
    PIEGE_DONNEES=/data \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080

# Sonde de disponibilité : la racine sert le portail statique sans authentification,
# donc un 200 prouve que le serveur écoute (la route /api/health exige un jeton).
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8080/'); sys.exit(0)" || exit 1

CMD ["python", "-m", "piege.api.serveur", "--port", "8080", "--donnees", "/data", "--portail", "/app/portal"]
