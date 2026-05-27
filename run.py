import os
import sys

import uvicorn

if __name__ == "__main__":
    try:
        import matplotlib  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        print(
            "WARNING: matplotlib/Pillow is not installed in this Python environment.\n"
            "Executive workbook charts need matplotlib and Pillow. Use:\n"
            "  .venv\\Scripts\\pip install -r requirements.txt\n"
            "  .venv\\Scripts\\python.exe run.py\n",
            file=sys.stderr,
        )
    # Windows: 127.0.0.1 is more reliable than 0.0.0.0 for browser access.
    # Set CF_RELOAD=1 to enable auto-reload during development.
    host = os.environ.get("CF_HOST", "127.0.0.1")
    port = int(os.environ.get("CF_PORT", "8000"))
    reload = os.environ.get("CF_RELOAD", "").strip() in ("1", "true", "yes")

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
        reload_dirs=["app", "templates", "static"] if reload else None,
    )
