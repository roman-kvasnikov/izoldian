# Izoldian

Self-hosted note-taking and knowledge management app. Your knowledge under your control.

## Features

- **Markdown editor** with live preview, syntax highlighting, and MathJax/Mermaid support
- **File tree** with folders, drag-and-drop, and nested organization
- **Wikilinks** (`[[note-name]]`) with interactive graph visualization
- **Tags** extracted from YAML frontmatter with filtering
- **Full-text search** across all notes
- **Note sharing** via public links with unique tokens
- **Media uploads** (images, audio, video, documents up to 50MB)
- **7 built-in themes** (Dark, Light, Dracula, Nord, Monokai, Gruvbox, Catppuccin Mocha)
- **Localization** (English, Russian)
- **Multi-user** with internal auth or OIDC (Authelia, Keycloak, etc.)
- **Mobile-friendly** responsive layout

## Tech Stack

**Backend:** FastAPI, SQLite (aiosqlite), bcrypt, JWT, OIDC
**Frontend:** Alpine.js, Tailwind CSS, marked.js, highlight.js, vis-network, MathJax, Mermaid

## Quick Start (Docker)

```bash
mkdir izoldian && cd izoldian
curl -O https://raw.githubusercontent.com/roman-kvasnikov/izoldian/master/docker-compose.yml
docker compose up -d
```

Open [http://localhost:8000](http://localhost:8000) and create an account.

## Docker Compose

```yaml
services:
  izoldian:
    container_name: izoldian
    image: ghcr.io/roman-kvasnikov/izoldian:latest
    restart: unless-stopped
    environment:
      - CORS_ORIGINS=*

      # - HOST=0.0.0.0
      # - PORT=8000
      # - DATA_DIR=/app/data
      # - DB_PATH=/app/data/izoldian.db
      # - SESSION_MAX_AGE_DAYS=7

      # Authentication
      # - USER_SIGNUP=true
      # - DISABLE_INTERNAL_AUTH=false

      # - OIDC_ENABLED=true
      # - OIDC_ISSUER=https://auth.example.com
      # - OIDC_CLIENT_ID=izoldian
      # - OIDC_CLIENT_SECRET=your-client-secret
      # - OIDC_REDIRECT_URI=http://localhost:8000/api/auth/oidc/callback
      # - OIDC_SCOPES=openid profile email
    volumes:
      - ./data:/app/data
    ports:
      - 8000:8000
```

## Manual Setup

Requires Python 3.11+.

```bash
cd backend
pip install -r requirements.txt
python main.py
```

## Environment Variables

| Variable                | Default                | Description                                                 |
| ----------------------- | ---------------------- | ----------------------------------------------------------- |
| `HOST`                  | `0.0.0.0`              | Server bind address                                         |
| `PORT`                  | `8000`                 | Server port                                                 |
| `DATA_DIR`              | `./data`               | User data directory                                         |
| `DB_PATH`               | `./data/izoldian.db`   | SQLite database path                                        |
| `SESSION_MAX_AGE_DAYS`  | `7`                    | Session expiration (days)                                   |
| `USER_SIGNUP`           | `true`                 | Allow new user registration                                 |
| `DISABLE_INTERNAL_AUTH` | `false`                | Disable username/password login                             |
| `OIDC_ENABLED`          | `false`                | Enable OpenID Connect auth                                  |
| `OIDC_ISSUER`           |                        | OIDC provider URL                                           |
| `OIDC_CLIENT_ID`        |                        | OAuth2 client ID                                            |
| `OIDC_CLIENT_SECRET`    |                        | OAuth2 client secret                                        |
| `OIDC_REDIRECT_URI`     |                        | Callback URL (`https://your-domain/api/auth/oidc/callback`) |
| `OIDC_SCOPES`           | `openid profile email` | OIDC scopes                                                 |
| `CORS_ORIGINS`          | `*`                    | Allowed CORS origins (comma-separated)                      |

## OIDC Setup

1. Set `OIDC_ENABLED=true` and configure the OIDC variables
2. Your OIDC provider must use `client_secret_post` token endpoint auth method
3. Optionally set `DISABLE_INTERNAL_AUTH=true` and `USER_SIGNUP=false` for OIDC-only mode

## Project Structure

```
izoldian/
├── backend/
│   ├── main.py              # App entry point, middleware
│   ├── config.py            # Environment configuration
│   ├── database.py          # SQLite schema and connection
│   ├── auth.py              # Auth, sessions, OIDC
│   ├── models.py            # Pydantic models
│   ├── share.py             # Share token management
│   ├── requirements.txt
│   └── routes/
│       ├── auth_routes.py
│       ├── notes_routes.py
│       ├── folders_routes.py
│       ├── search_routes.py
│       ├── graph_routes.py
│       ├── share_routes.py
│       ├── media_routes.py
│       ├── theme_routes.py
│       └── locale_routes.py
├── frontend/
│   ├── index.html           # Login page
│   ├── app.html             # Main app
│   ├── css/styles.css
│   ├── js/app.js
│   ├── themes/              # 7 theme CSS files
│   └── locales/             # i18n JSON files
├── Dockerfile
├── docker-compose.yml
└── docker-compose.dev.yml
```

## License

MIT
