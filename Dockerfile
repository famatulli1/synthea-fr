# =============================================================================
# Synthea-FR Dashboard FHIR
# Image complète : Java 17 (Synthea) + Python 3.11 (Streamlit)
# =============================================================================

FROM eclipse-temurin:17-jdk-jammy AS builder

# Installation des dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3-pip \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copie du projet Synthea
WORKDIR /app
COPY . .

# Build Synthea JAR (skip tests pour accélérer)
RUN ./gradlew build -x test --no-daemon

# =============================================================================
# Image finale
# =============================================================================
FROM eclipse-temurin:17-jre-jammy

# Installation Python et dépendances
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3-pip \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Création utilisateur non-root
RUN useradd -m -u 1000 synthea
WORKDIR /app

# Copie des artefacts depuis le builder
COPY --from=builder /app/build /app/build
COPY --from=builder /app/src /app/src
COPY --from=builder /app/gradlew /app/gradlew
COPY --from=builder /app/gradle /app/gradle
COPY --from=builder /app/build.gradle /app/build.gradle
COPY --from=builder /app/settings.gradle /app/settings.gradle

# Copie du dashboard
COPY fhir_dashboard /app/fhir_dashboard

# Installation des dépendances Python
RUN python3 -m venv /app/venv && \
    /app/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /app/venv/bin/pip install --no-cache-dir -r /app/fhir_dashboard/requirements.txt

# Création des répertoires de données
RUN mkdir -p /app/output/fhir /app/datasets && \
    chown -R synthea:synthea /app

# Configuration Streamlit (créée inline si absente)
RUN mkdir -p /app/fhir_dashboard/.streamlit && \
    echo '[server]\naddress = "0.0.0.0"\nport = 8501\nheadless = true\n\n[browser]\ngatherUsageStats = false' > /app/fhir_dashboard/.streamlit/config.toml

# Variables d'environnement
ENV PYTHONUNBUFFERED=1
ENV FHIR_DIR=/app/output/fhir
ENV PATH="/app/venv/bin:$PATH"

# Switch vers utilisateur non-root
USER synthea

# Exposition du port Streamlit
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Commande de démarrage
WORKDIR /app/fhir_dashboard
CMD ["streamlit", "run", "app.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
