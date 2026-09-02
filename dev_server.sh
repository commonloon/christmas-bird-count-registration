#!/usr/bin/env bash
# Launches the local Flask dev server.
# Must use `flask run`, not `python app.py` directly - the latter hits a
# circular import (app.py -> routes/admin.py -> routes/auth.py -> from app
# import csrf, LANDING_HOST) that only resolves via Flask's own CLI loader.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

export FLASK_APP=app.py
exec .venv/Scripts/flask.exe run --host 127.0.0.1 --port 8080
