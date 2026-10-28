import os
import sys
from pathlib import Path

# Ensure the root repository directory is at the front of sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Set working directory to root so relative paths to data/ and static/ resolve correctly
os.chdir(str(ROOT_DIR))

# Import the configured Flask application
from app_server import app as flask_app

class VercelWSGIHandler:
    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        
        # If Vercel rewrites stripped /api prefix or routed to /api/index
        matched_uri = (
            environ.get("HTTP_X_MATCHED_PATH")
            or environ.get("HTTP_X_VERCEL_MATCHED_PATH")
            or environ.get("HTTP_X_FORWARDED_URI")
            or ""
        )
        if matched_uri and matched_uri.startswith("/api"):
            environ["PATH_INFO"] = matched_uri

        # If path starts directly with /sip, /rag, /analyze, /groww, prefix with /api
        elif not path.startswith("/api") and any(path.startswith(p) for p in ["/sip", "/rag", "/analyze", "/results", "/reviews", "/trends", "/apps"]):
            environ["PATH_INFO"] = "/api" + path

        return self.application(environ, start_response)

# Vercel entry point
app = VercelWSGIHandler(flask_app)
