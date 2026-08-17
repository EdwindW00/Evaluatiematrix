"""Dev-server zonder automatisch een systeembrowser te openen (voor preview/tests)."""
from app.webapp.server import create_app

if __name__ == "__main__":
    app = create_app()
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.run(host="127.0.0.1", port=5151, threaded=True, debug=False)
