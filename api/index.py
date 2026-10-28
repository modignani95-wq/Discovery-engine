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
from app_server import app

# Vercel WSGI entry point
# Vercel looks for the WSGI application named 'app'
