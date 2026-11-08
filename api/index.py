import os
import sys
from pathlib import Path

# Ensure the root repository directory is at the front of sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Set working directory to root so relative paths to data/ and static/ resolve correctly
os.chdir(str(ROOT_DIR))

from urllib.parse import parse_qs

# Import the configured Flask application
from app_server import app as flask_app

class VercelWSGIHandler:
    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        query = environ.get("QUERY_STRING", "")
        
        # Check __vercel_subpath from rewrite
        subpath = None
        if "__vercel_subpath=" in query:
            qs = parse_qs(query, keep_blank_values=True)
            if "__vercel_subpath" in qs and qs["__vercel_subpath"]:
                subpath = qs["__vercel_subpath"][0]
                qs.pop("__vercel_subpath", None)
                new_q = []
                for k, vs in qs.items():
                    for v in vs:
                        new_q.append(f"{k}={v}")
                environ["QUERY_STRING"] = "&".join(new_q)
        
        # Determine effective path
        matched_uri = (
            (("/api/" + subpath.lstrip("/")) if subpath else None)
            or environ.get("HTTP_X_ORIGINAL_URI")
            or environ.get("HTTP_X_FORWARDED_URI")
            or environ.get("HTTP_X_MATCHED_PATH")
            or environ.get("HTTP_X_VERCEL_MATCHED_PATH")
            or environ.get("RAW_URI")
            or environ.get("REQUEST_URI")
            or ""
        )
        
        if "?" in matched_uri:
            matched_uri = matched_uri.split("?", 1)[0]
            
        if matched_uri and matched_uri.startswith("/api"):
            environ["PATH_INFO"] = matched_uri
        elif not path.startswith("/api") and any(path.startswith(p) for p in ["/sip", "/rag", "/analyze", "/results", "/reviews", "/trends", "/apps"]):
            environ["PATH_INFO"] = "/api" + path

        return self.application(environ, start_response)

# Vercel entry point
app = VercelWSGIHandler(flask_app)
