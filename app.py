"""
Entrypoint wrapper that safely loads the application factory from the
`app` package directory even when this file is named `app.py` (which would
otherwise shadow the `app` package during imports). This avoids import-time
errors in deployment environments that expect an `app.py` module.
"""
import os
import sys
import importlib.util

# Load the package's __init__.py as a module named 'app' and
# ensure it's registered in sys.modules so intra-package imports
# (e.g. `from app.extensions.db import ...`) resolve even when this
# file is named `app.py` (which would otherwise shadow the package).
pkg_init = os.path.join(os.path.dirname(__file__), "app", "__init__.py")
# Create a module spec for the package using the package __init__.py
spec = importlib.util.spec_from_file_location("app", pkg_init)
app_pkg = importlib.util.module_from_spec(spec)

# Tell Python where to find subpackages/modules under the package name.
app_pkg.__path__ = [os.path.join(os.path.dirname(__file__), "app")]

# Register the loaded module under the package name so imports like
# `import app.extensions` find this module instead of the top-level
# `app.py` file that many hosting platforms import.
sys.modules["app"] = app_pkg

# Execute the package module (this runs app/__init__.py)
spec.loader.exec_module(app_pkg)

# Grab the factory and create the Flask app
create_app = getattr(app_pkg, "create_app")
app = create_app()


if __name__ == "__main__":
    # Run without the debugger in development / production by default.
    # To enable debugging explicitly set the FLASK_DEBUG env var when needed.
    app.run()
