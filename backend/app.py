import os

from flask import Flask, jsonify, request

from ai_service import (
    generate_answer_response,
    generate_course_response,
    generate_questions_response,
)


app = Flask(__name__)


def _get_prompt_payload() -> str:
    data = request.get_json(silent=True) or {}
    prompt = data.get("prompt", "")

    if not isinstance(prompt, str):
        return ""

    return prompt.strip()


def _handle_prompt_response(generator):
    prompt = _get_prompt_payload()

    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400

    try:
        return jsonify({"response": generator(prompt)}), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.get("/")
def index():
    return jsonify({
        "message": "Eureka AI backend is running",
        "routes": [
            "/health",
            "/api/ai/generate-course",
            "/api/ai/generate-questions",
            "/api/ai/qa",
        ],
    })


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.post("/api/ai/generate-course")
@app.post("/gc")
def generate_course():
    return _handle_prompt_response(generate_course_response)


@app.post("/api/ai/generate-questions")
@app.post("/gquestion")
def generate_questions():
    return _handle_prompt_response(generate_questions_response)


@app.post("/api/ai/qa")
@app.post("/qa")
def generate_answer():
    return _handle_prompt_response(generate_answer_response)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
