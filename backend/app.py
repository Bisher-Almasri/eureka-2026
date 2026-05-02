import json
import os

from flask import Flask, jsonify, request

from ai_service import (
    generate_challenge_hint_response,
    generate_challenge_response,
    generate_answer_response,
    generate_course_response,
    generate_debug_coach_response,
    generate_questions_response,
)
from code_runner import run_code
from user_profile import DEFAULT_USER_ID, ai_learning_context, get_user_state, update_progress


app = Flask(__name__)
DEBUG_SESSIONS: dict[str, dict[str, object]] = {}


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


def _json_payload() -> dict:
    data = request.get_json(silent=True) or {}
    return data if isinstance(data, dict) else {}


def _parse_ai_json(response_text: str) -> dict:
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        return {"raw": response_text}
    return parsed if isinstance(parsed, dict) else {"raw": parsed}


@app.get("/")
def index():
    return jsonify({
        "message": "Eureka AI backend is running",
        "routes": [
            "/health",
            "/api/ai/generate-course",
            "/api/ai/generate-questions",
            "/api/ai/qa",
            "/api/ai/debug-coach",
            "/api/ai/generate-challenge",
            "/api/ai/challenge-hint",
            "/run-code",
            "/update-progress",
            "/user-state",
            "/hardware/buzz",
        ],
    })


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.post("/api/ai/generate-course")
@app.post("/gc")
def generate_course():
    data = _json_payload()
    prompt = _get_prompt_payload()

    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400

    user_id = str(data.get("user_id") or DEFAULT_USER_ID)
    topic = str(data.get("topic") or prompt)
    try:
        context = ai_learning_context(user_id, topic)
        return jsonify({"response": generate_course_response(prompt, context)}), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.post("/api/ai/generate-questions")
@app.post("/gquestion")
def generate_questions():
    return _handle_prompt_response(generate_questions_response)


@app.post("/api/ai/qa")
@app.post("/qa")
def generate_answer():
    data = _json_payload()
    prompt = _get_prompt_payload()

    if not prompt:
        return jsonify({"error": "No prompt provided"}), 400

    user_id = str(data.get("user_id") or DEFAULT_USER_ID)
    topic = str(data.get("topic") or "general")
    try:
        context = ai_learning_context(user_id, topic)
        return jsonify({"response": generate_answer_response(prompt, context)}), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.post("/api/ai/debug-coach")
@app.post("/debug-coach")
def debug_coach():
    data = _json_payload()
    code = str(data.get("code") or "").strip()
    if not code:
        return jsonify({"error": "No code provided"}), 400

    session_id = str(data.get("session_id") or "default-debug-session")
    language = str(data.get("language") or "python")
    user_id = str(data.get("user_id") or DEFAULT_USER_ID)
    topic = str(data.get("topic") or "debugging")

    session = DEBUG_SESSIONS.setdefault(
        session_id,
        {"attempt_count": 0, "hint_level": 0, "previous_feedback": ""},
    )
    session["attempt_count"] = int(session.get("attempt_count", 0)) + 1
    session["hint_level"] = min(4, int(session.get("hint_level", 0)) + 1)

    try:
        response = generate_debug_coach_response(
            code=code,
            language=language,
            attempt_count=int(session["attempt_count"]),
            hint_level=int(session["hint_level"]),
            previous_feedback=str(session.get("previous_feedback") or ""),
            learning_context=ai_learning_context(user_id, topic),
        )
        parsed = _parse_ai_json(response)
        session["previous_feedback"] = parsed.get("hint", response)
        return jsonify(
            {
                "session_id": session_id,
                "attempt_count": session["attempt_count"],
                "hint_level": session["hint_level"],
                "response": parsed,
            }
        ), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.post("/api/ai/challenge-hint")
@app.post("/challenge-hint")
def challenge_hint():
    data = _json_payload()
    code = str(data.get("code") or "")
    instructions = str(data.get("instructions") or "Help the learner debug this challenge.")
    test_results = data.get("test_results") or []
    hint_level = int(data.get("hint_level") or 1)
    user_id = str(data.get("user_id") or DEFAULT_USER_ID)
    topic = str(data.get("topic") or "practice")

    try:
        response = generate_challenge_hint_response(
            instructions=instructions,
            code=code,
            test_results=test_results if isinstance(test_results, list) else [],
            hint_level=hint_level,
            learning_context=ai_learning_context(user_id, topic),
        )
        return jsonify({"response": _parse_ai_json(response)}), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.post("/api/ai/generate-challenge")
@app.post("/generate-challenge")
def generate_challenge():
    data = _json_payload()
    title = str(data.get("title") or data.get("topic") or "").strip()
    body = str(data.get("body") or data.get("prompt") or "").strip()
    code = str(data.get("code") or "")
    language = str(data.get("language") or "python")
    user_id = str(data.get("user_id") or DEFAULT_USER_ID)
    topic = title or "practice"

    if not title and not body:
        return jsonify({"error": "No section content provided"}), 400

    try:
        response = generate_challenge_response(
            title=title or topic,
            body=body,
            code=code,            language=language,
            learning_context=ai_learning_context(user_id, topic),
        )
        return jsonify({"response": _parse_ai_json(response)}), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.post("/run-code")
@app.post("/api/run-code")
def execute_code():
    data = _json_payload()
    code = str(data.get("code") or "")
    if not code.strip():
        return jsonify({"error": "No code provided"}), 400

    tests = data.get("tests") or []
    if not isinstance(tests, list):
        return jsonify({"error": "tests must be a list"}), 400

    result = run_code(
        code=code,
        language=str(data.get("language") or "python"),
        tests=tests,
        timeout_seconds=int(data.get("timeout_seconds") or 5),
    )
    return jsonify(result), 200


@app.post("/update-progress")
@app.post("/api/update-progress")
def update_user_progress():
    try:
        return jsonify(update_progress(_json_payload())), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.get("/user-state")
@app.get("/api/user-state")
def user_state():
    user_id = request.args.get("user_id") or DEFAULT_USER_ID
    return jsonify(get_user_state(user_id)), 200


@app.post("/hardware/buzz")
def hardware_buzz():
    """Send a buzz signal when user loses focus. 
    
    Expects JSON payload with 'seconds' parameter (number of modals).
    """
    data = _json_payload()
    seconds = int(data.get("seconds") or 0)
    
    # TODO: Implement actual hardware buzzer control here
    # For now, just acknowledge the request
    return jsonify({
        "ok": True,
        "message": f"Buzz signal received - {seconds} modal(s) active",
        "seconds": seconds
    }), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
