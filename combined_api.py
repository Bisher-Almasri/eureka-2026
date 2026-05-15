from flask import Flask, jsonify
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple
import os

from ai_backend.app import app as ai_app
from face_backend.app import app as face_app

main_app = Flask(__name__)


@main_app.route("/")
def index():
    return jsonify({
        "message": "Eureka combined API is running",
        "mounted_apps": ["/ai", "/face"],
    })


application = DispatcherMiddleware(main_app, {"/ai": ai_app, "/face": face_app})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    run_simple("0.0.0.0", port, application, use_reloader=debug, use_debugger=debug)
