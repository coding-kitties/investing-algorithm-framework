from flask_cors import CORS


def setup_cors(app):
    CORS(app)
    return app
