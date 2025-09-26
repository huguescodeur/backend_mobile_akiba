# Dockerfile pour Django + Channels
FROM python:3.12-slim

# Variables d'environnement
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Installer les dépendances système
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Créer un répertoire de travail
WORKDIR /app

# Copier les fichiers requirements
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copier tout le projet
COPY . .

# Commande par défaut (peut être surchargée dans docker-compose)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
