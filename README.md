# VTU Genius

VTU Genius is a Django study assistant for VTU students. It combines note management, exam preparation tools, PDF retrieval, and a local Ollama-powered assistant.

## Main features

- Student registration, login, dashboard, and profile management
- PDF note upload, download, deletion, and subject/unit organization
- Persistent per-student RAG retrieval with ChromaDB
- Ollama chat using the local `llama3.2` model
- Expected-question generation, exam mode, and previous-year paper analysis

## Tech stack

- Python and Django
- SQLite for local development, with environment-configurable database settings
- ChromaDB and Sentence Transformers for local retrieval
- Ollama for local AI responses
- HTML templates, CSS, and Django static files

## Architecture overview

- `accounts/`: registration, authentication, and student profiles
- `dashboard/`: dashboard and profile views
- `notes/`: note models, uploads, and note operations
- `ai_assistant/`: Ollama integration, PDF extraction, RAG indexing/retrieval, and exam features
- `templates/`: Django templates
- `static/`: source static assets
- `vtu_genius/settings.py`: environment-driven application, database, static/media, ChromaDB, and Ollama configuration

Uploaded PDFs remain in `MEDIA_ROOT` locally. ChromaDB persists in `CHROMA_DB_PATH`; these directories are intentionally ignored by Git.

## Local setup

Create and activate a virtual environment:

```powershell
python -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create local configuration:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set a private `SECRET_KEY`. The example uses SQLite, local media, local ChromaDB, and Ollama defaults. `.env` is ignored and must never be committed.

## Run Ollama locally

Install Ollama, start the Ollama service, and pull the configured model:

```powershell
ollama serve
ollama pull llama3.2
```

The application uses Ollama at `http://localhost:11434/api` by default. Override `OLLAMA_BASE_URL` or `OLLAMA_MODEL` in `.env` when needed. No API key or AWS credentials are required.

## Run Django

Apply migrations and start the development server:

```powershell
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/` in a browser. The local server serves uploaded media during development.

Collect deployment static files with:

```powershell
python manage.py collectstatic --noinput
```

## Verify RAG and run tests

With Ollama running and at least one readable PDF note available:

```powershell
python manage.py verify_rag
python manage.py test
python manage.py check
python manage.py check --deploy
```

`verify_rag` exercises note indexing and student-isolated retrieval. Ollama-backed tests may require the local Ollama service; the test suite also contains mocked/failure-path coverage.

## GitHub safety

The repository ignores Python caches, virtual environments, `.env`, SQLite databases, uploaded media, collected static files, persistent ChromaDB data, IDE files, OS metadata, logs, and coverage output. Source code, templates, static source files, migrations, and dependency manifests remain trackable.

AWS/S3 is not required for local development. Local filesystem storage remains the active media backend.

## Future deployment

For a hosting platform, provide environment variables through the platform’s secret/configuration manager. Set `DEBUG=False`, a strong `SECRET_KEY`, explicit `ALLOWED_HOSTS`, and appropriate `CSRF_TRUSTED_ORIGINS`. Configure a production database and writable/static storage paths as supported by the platform. Ensure Ollama and the configured model are available to the deployed application, or plan a separate compatible inference service; the project does not require AWS S3.

## Deployment — Render

This repository includes `render.yaml` and `build.sh` as a deployment starting point. Nothing is deployed by this project change.

1. Create a Render account and connect the GitHub repository.
2. Create a Blueprint from the repository, or create a Python web service manually.
3. Use this build command:

```text
bash build.sh
```

4. Use this start command:

```text
gunicorn vtu_genius.wsgi:application
```

5. Set the required environment variables in Render:

- `SECRET_KEY`: generate a private random value, or let `render.yaml` generate it.
- `DEBUG=False`
- `ALLOWED_HOSTS=.onrender.com` plus any custom hostnames.
- `CSRF_TRUSTED_ORIGINS=https://your-service.onrender.com`.
- `DATABASE_URL`: provide the Render PostgreSQL connection URL for persistent production data.
- `OLLAMA_BASE_URL`: configure a separately hosted Ollama-compatible endpoint when production AI is added.
- `OLLAMA_MODEL=llama3.2` unless the separate AI host uses another configured model.
- `CHROMA_DB_PATH`: use a persistent mounted disk path if one is added later.

The application still uses SQLite, local media, local ChromaDB, and local Ollama by default for development. Render's free filesystem is ephemeral: uploaded PDFs and ChromaDB data stored there are not permanent. Persistent media storage and persistent vector storage are separate future deployment work; this step does not add S3 or any other storage provider.

Ollama is not installed, hosted, or run by Render in this step. Production AI hosting will be handled separately later. The `/health/` endpoint is lightweight and does not require login, Ollama, ChromaDB, or a database query.
