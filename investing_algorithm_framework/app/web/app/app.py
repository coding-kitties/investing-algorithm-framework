import threading
import webbrowser
import uvicorn

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


class WebApp:

    def __init__(self, configuration_service):
        self.app = FastAPI()
        self.configuration_service = configuration_service

        # Serve React static files
        self.app.mount(
            "/",
            StaticFiles(
                directory="static/build", html=True
            ),
            name="static"
        )

    def run(self):
        threading.Thread(target=self._start_server, daemon=True).start()
        webbrowser.open("http://127.0.0.1:8000")

    def _start_server(self):
        """Start the FastAPI server."""
        uvicorn.run(self.app, host="127.0.0.1", port=8000, log_level="info")
