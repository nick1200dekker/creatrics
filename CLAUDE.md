# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Flask-based web application called Creator Tools that provides various features for content creators including:
- Soccer/football analytics (player stats, team stats, match center)
- Third-party analytics integration
- Payment processing via Stripe
- User authentication and subscription management
- Integration with multiple AI providers (OpenAI, Anthropic, Google, Replicate, etc.)

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
python run.py

# Run with gunicorn (production)
gunicorn --bind :8080 --workers 1 --threads 8 --timeout 0 wsgi:app

# Run tests
python test_fdf_scoring.py

# Docker commands
docker-compose up
docker build -t creator-tools .
```

## Architecture

### Core Structure

The application follows a blueprint-based Flask architecture:

- **Entry Points**:
  - `run.py` - Development server entry point with Flask app initialization
  - `wsgi.py` - Production WSGI entry point for Gunicorn

- **Main App Directory (`app/`)**:
  - `routes/` - Blueprint-based route modules organized by feature
  - `system/` - Core system modules (auth, services, AI providers)
  - `templates/` - Jinja2 HTML templates
  - `static/` - CSS, JavaScript, and static assets
  - `scripts/` - Utility scripts
  - `config.py` - Configuration management

### Key Routes

Routes are organized as Flask blueprints in `app/routes/`:
- `core/` - Core application routes
- `home/` - Home page routes
- `payment/` - Stripe payment integration
- `player_stats/`, `team_stats/`, `tp_analytics/`, `match_center/` - Soccer analytics features
- `cron/` - Scheduled task endpoints

### Authentication & Services

- **Authentication**: Custom middleware in `app/system/auth/middleware.py` handles request authentication
- **Firebase**: Used for user management and storage (credentials in `firebase-credentials.json`)
- **Supabase**: Alternative backend service integration
- **AI Providers**: Multiple AI service integrations in `app/system/ai_provider/`

### Environment Variables

Required environment variables (stored in `.env`):
- `SECRET_KEY` - Flask secret key (required in production)
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY` - Supabase configuration
- `FIREBASE_STORAGE_BUCKET` - Firebase storage configuration
- `PORT` - Server port (default: 8080)
- `FLASK_ENV` - Environment mode (development/production)

### Testing

Test files are located in the root directory (e.g., `test_fdf_scoring.py`). Run individual test files directly with Python.

## Important Patterns

1. **Blueprint Registration**: All routes are registered as blueprints in `run.py`
2. **Context Processors**: Global template variables injected via `@app.context_processor`
3. **Middleware Pattern**: Authentication handled via `@app.before_request`
4. **Service Layer**: Business logic separated in `app/system/services/`
5. **Config Management**: Centralized configuration through `app/config.py`