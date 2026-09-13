# VTU Genius

VTU Genius is a Django study assistant for VTU students. It combines personal PDF notes, student-isolated retrieval-augmented generation, local Ollama responses, and exam-focused revision tools.

## 🚀 Live Demo

https://vtu-genius.onrender.com/

## 🛠️ Tech Stack

- Python
- Django
- ChromaDB
- RAG
- Ollama
- Llama 3.2
## Features

- Student authentication and profiles
- Personal notes and PDF upload, search, download, and deletion
- RAG-based document retrieval limited to the current student's notes
- AI Assistant with conversation history and note-grounded answers
- VTU-style question generation
- Expected exam questions
- Previous-year question analysis
- One-day-before exam mode and smart revision planner

## Technology Stack

**Frontend:** HTML, CSS, JavaScript, Django templates, Bootstrap-compatible static assets

**Backend:** Python, Django

**AI:** Ollama, Llama 3.2

**RAG:** ChromaDB, Sentence Transformers

**PDF:** pypdf

**Deployment:** GitHub + Render, Gunicorn, WhiteNoise

## Architecture

```text
User
  -> Django authentication and views
  -> PDF processing with pypdf
  -> text chunking and embeddings
  -> student-isolated ChromaDB storage
  -> similarity retrieval for the current question
  -> relevant context and conversation history
  -> Ollama /api/chat
  -> grounded AI response
```

The Django application owns authentication, authorization, note operations, feature workflows, and persistence. RAG retrieval filters ChromaDB metadata by student, and Ollama receives the retrieved context together with the existing VTU-specific instructions.

## Local Setup

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

Create local environment configuration:

```powershell
Copy-Item .env.example .env
```

Set a private `SECRET_KEY` in `.env`. Local defaults are:

```env
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
CHROMA_DB_PATH=chroma_db
RAG_ENABLED=True
MEDIA_ROOT=media
```

Apply migrations and run Django:

```powershell
python manage.py migrate
python manage.py runserver
```

Start Ollama in a separate terminal and download the local model:

```powershell
ollama serve
ollama pull llama3.2
```

Open `http://127.0.0.1:8000/` after the server starts.

## Validation Commands

```powershell
python manage.py check
python manage.py check --deploy
python -m pip check
python manage.py collectstatic --noinput
python manage.py test accounts dashboard ai_assistant.test_exam_mode ai_assistant.test_expected_questions ai_assistant.test_previous_year_analysis
```

The default `python manage.py test` discovery currently finds no tests because the AI suites use explicit `test_*.py` module names. Run the explicit command above for the current test coverage.

To verify one note and its retrieval, provide an existing note ID and question:

```powershell
python manage.py verify_rag <note_id> --question "Explain the main concepts"
```

This command indexes the selected note before checking retrieval. Do not run it against important production data without a backup.

## RAG Explanation

1. A student uploads a PDF note.
2. pypdf extracts readable text.
3. The text is split into overlapping chunks.
4. Sentence Transformers creates normalized embeddings.
5. ChromaDB stores chunks with student, note, subject, semester, and unit metadata.
6. A question performs similarity retrieval filtered to that student's metadata.
7. Retrieved context is sent to Ollama with the question and supported conversation history.
8. The generated grounded answer is returned to the student.

The existing local ChromaDB directory is preserved for development and ignored by Git. Render's free filesystem is ephemeral, so persistent production vector storage requires separate infrastructure.

On Render Free, `RAG_ENABLED=False` prevents ChromaDB and Sentence Transformers from loading in the web worker. PDF uploads still save normally, and Ollama-backed pages remain available with their existing PDF-context fallback. Set `RAG_ENABLED=True` only when the deployment has enough memory and appropriate persistent vector storage.

## Deployment

The project is deployed as a Render Web Service using the free plan.

Build command:

```text
./build.sh
```

Start command:

```text
gunicorn vtu_genius.wsgi:application --bind 0.0.0.0:$PORT
```

The service runs migrations and `collectstatic` during the build and exposes `/health/` for health checks. `render.yaml` contains the service configuration.

The Render Free service uses one Gunicorn worker (`WEB_CONCURRENCY=1`) and does not preload the Django application, avoiding duplicate model memory across workers.

Production configuration requires:

- `SECRET_KEY`
- `DEBUG=False`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `DATABASE_URL` for a persistent PostgreSQL database when configured
- `OLLAMA_BASE_URL` pointing to a publicly and reliably reachable Ollama-compatible endpoint
- `OLLAMA_MODEL` set to a model available at that endpoint
- `CHROMA_DB_PATH` set to an appropriate persistent path when persistent vector storage is provided
- `RAG_ENABLED=False` on the Render Free plan unless the service has enough memory for ChromaDB and Sentence Transformers

Localhost Ollama works only for local development. Ollama is not hosted by this project on Render and is not installed by the Render build. Production AI requires a separately hosted reachable endpoint; no paid AI provider is required by the application.

If `OLLAMA_BASE_URL` is missing on Render, the AI Assistant reports that production AI is not configured and does not attempt a localhost request. A Render value pointing to `localhost` is also rejected before any network request.

Uploaded media, SQLite, and local ChromaDB data on Render's free filesystem are not permanent. Persistent production media, database, and vector storage require appropriate infrastructure. AWS/S3 is not currently required or configured.

Current deployed application: https://vtu-genius.onrender.com

## Project Structure

```text
accounts/                 Authentication, registration, and student profiles
dashboard/                Dashboard and profile views
notes/                    Note models, PDF upload, download, search, and deletion
ai_assistant/             Ollama, RAG, exam features, and verification command
templates/                Django HTML templates
static/                   Source CSS and static assets
vtu_genius/settings.py    Environment-driven Django configuration
vtu_genius/urls.py        Root routes and /health/
vtu_genius/wsgi.py        Gunicorn/WSGI entry point
build.sh                  Render dependency, static, and migration build
render.yaml               Render Web Service configuration
requirements.txt          Pinned Python dependencies
.env.example              Safe local configuration template
```

## Security and Data Boundaries

- Secrets are read from environment variables; `.env` is ignored.
- Production requires an explicit `SECRET_KEY` and can set `DEBUG=False`.
- `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` are configurable.
- Protected views require authentication.
- Notes, conversations, and RAG retrieval are scoped to the current student.
- Media uploads, SQLite, ChromaDB, virtual environments, caches, and collected static files are excluded from Git.

## Future Enhancements

- Add persistent production media and vector storage.
- Connect a separately hosted Ollama-compatible inference service.
- Expand automated authentication and end-to-end workflow coverage.
- Configure a persistent production PostgreSQL database.
