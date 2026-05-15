import json
import os
from typing import Any
from urllib import error, request


HC_AI_API_URL = "https://ai.hackclub.com/proxy/v1/chat/completions"
HC_AI_MODEL = os.environ.get("HC_AI_MODEL", "qwen/qwen3-32b")
HC_AI_TIMEOUT_SECONDS = int(os.environ.get("HC_AI_TIMEOUT_SECONDS", "25"))

MAX_USER_PROMPT_CHARS = 1800
MAX_CODE_CHARS = 3500
MAX_TEST_RESULTS_CHARS = 1200

COURSE_MAX_TOKENS = int(os.environ.get("HC_AI_COURSE_MAX_TOKENS", "4200"))
QUESTIONS_MAX_TOKENS = int(os.environ.get("HC_AI_QUESTIONS_MAX_TOKENS", "1200"))
QA_MAX_TOKENS = int(os.environ.get("HC_AI_QA_MAX_TOKENS", "500"))
DEBUG_MAX_TOKENS = int(os.environ.get("HC_AI_DEBUG_MAX_TOKENS", "350"))
CHALLENGE_MAX_TOKENS = int(os.environ.get("HC_AI_CHALLENGE_MAX_TOKENS", "1400"))


def get_hc_ai_api_key() -> str:
    api_key = os.environ.get("HC_AI_API_KEY") or os.environ.get("HACKCLUB_AI_API_KEY")

    if not api_key:
        raise RuntimeError("HC_AI_API_KEY is not set")

    return api_key


def extract_json_response(response_text: str) -> str:
    trimmed_response = response_text.strip()

    if "```" in trimmed_response:
        start = trimmed_response.find("```json")
        if start != -1:
            start = trimmed_response.find("\n", start)
            end = trimmed_response.find("```", start + 1)
            if start != -1 and end != -1:
                return trimmed_response[start:end].strip()

        start = trimmed_response.find("```")
        if start != -1:
            start = trimmed_response.find("\n", start)
            end = trimmed_response.find("```", start + 1)
            if start != -1 and end != -1:
                return trimmed_response[start:end].strip()

    return trimmed_response


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated for latency]"


def _post_hc_ai_prompt(prompt: str, max_tokens: int) -> str:
    payload = json.dumps(
        {
            "model": HC_AI_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "/no_think\n"
                        "You are a fast JSON API. Be concise. Do not explain your reasoning. "
                        "Return only the requested JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }
    ).encode("utf-8")

    api_request = request.Request(
        HC_AI_API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "curl/8.0.0",
            "Authorization": f"Bearer {get_hc_ai_api_key()}",
        },
        method="POST",
    )

    try:
        with request.urlopen(api_request, timeout=HC_AI_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = ""
        try:
            body = exc.read().decode("utf-8")
            if body:
                details = f" - {body}"
        except Exception:
            details = ""
        raise RuntimeError(f"HC AI API error: {exc.code}{details}") from exc

    choices = data.get("choices", [])
    response_text = None

    if choices:
        response_text = choices[0].get("message", {}).get("content")

    if not response_text:
        raise RuntimeError("HC AI API returned an empty response")

    return extract_json_response(response_text)


def build_course_prompt(
    prompt: str,
    learning_context: dict[str, Any] | None = None,
) -> str:
    learning_context = learning_context or {}
    return f"""
You are a course writer. First decide whether the requested topic is coding/programming/software-development related.

CRITICAL: You MUST respond with ONLY valid JSON wrapped in ```json blocks. No other text before or after.
- Use exactly this JSON shape:
  {{
    "t": "Course Title",
    "d": "One sentence description",
    "l": "programming language if coding-related, otherwise general",
    "ic": true or false,
    "c": [
      {{
        "n": "Part title",
        "d": "Short part description",
        "s": [
          {{
            "t": "Section title",
            "c": [
              {{ "type": "p", "text": "80-140 word explanation" }},
              {{ "type": "code", "lang": "python", "code": "short example" }},
              {{ "type": "p", "text": "one sentence practice prompt" }}
            ]
          }}
        ]
      }}
    ]
  }}
- Set "ic" to true only for coding/programming/software-development topics.
- Set "ic" to false for non-coding topics like history, cooking, fitness, math, business, art, languages, science, etc.
- Create 5-7 parts/modules.
- Create 3-4 sections per part/module.
- Keep each paragraph under 450 characters.
- If "ic" is true, include at most one short code block per section.
- If "ic" is false, do not include code blocks at all; use only paragraph objects.
- Make the course substantial enough to feel like a real multi-module course.
- Do not include a separate review/revision pass.
- Adapt to this learner profile:
  - skill level: {learning_context.get("skill_level", "beginner")}
  - recent mistakes: {json.dumps(learning_context.get("recent_mistakes", []))}
  - pace: {learning_context.get("pace", "steady learner")}
- Simplify explanations and add fundamentals if the learner is struggling.
- Increase challenge and use deeper examples if the learner is advanced.
- Include targeted examples for weak areas when recent mistakes are available.

Course request: {_truncate_text(prompt, MAX_USER_PROMPT_CHARS)}

Remember: Respond with ONLY ```json [your json here] ``` and nothing else.
"""


def build_questions_prompt(prompt: str) -> str:
    return f"""
You are a generator that creates questions for a coding course.
You will be given the contents of a coding course, and your task is to generate questions that can be used to test the knowledge of the course.

CRITICAL: You MUST respond with ONLY valid JSON wrapped in ```json blocks. No other text before or after.

Create an array of question objects. Each question should be in this exact JSON format:
{{
    "q": "question text",
    "a1": "option 1", 
    "a2": "option 2",
    "a3": "option 3", 
    "a4": "option 4",
    "part": 0,
    "correct": "a1",
    "e": "2-3 sentence explanation of why the correct answer is right and why a common wrong answer is wrong"
}}

Guidelines:
- Generate 3-5 questions for the provided section or course content
- Make questions challenging but fair
- Ensure one answer is clearly correct
- Use the 0-based index for the "part" field
- Each question should be multiple choice with exactly 4 options
- The "correct" field must be one of: "a1", "a2", "a3", or "a4"
- The "e" field is required because the TUI shows it when the learner answers incorrectly

Here is the course content: {_truncate_text(prompt, MAX_USER_PROMPT_CHARS)}

Remember: Respond with ONLY ```json [your json array here] ``` and nothing else.
"""


def build_answer_prompt(prompt: str, learning_context: dict[str, Any] | None = None) -> str:
    learning_context = learning_context or {}
    return f"""
You are an AI assistant specialized in answering coding questions for beginners.

CRITICAL: You MUST respond with ONLY valid JSON wrapped in ```json blocks. No other text before or after.

Guidelines:
- If the question is not coding-related, politely decline in the answer field
- For coding questions, provide clear, beginner-friendly explanations
- If a language is specified, focus on that language; otherwise use Python or give general advice
- Include practical examples when helpful
- Keep answers informative but concise (max 1000 characters)
- Adapt to this learner profile:
  - skill level: {learning_context.get("skill_level", "beginner")}
  - recent mistakes: {json.dumps(learning_context.get("recent_mistakes", []))}
  - pace: {learning_context.get("pace", "steady learner")}
  - recommendations: {json.dumps(learning_context.get("recommendations", []))}
- If the learner is struggling or moving slowly, simplify the explanation and use a smaller example.
- If the learner is advanced and making few mistakes, increase the difficulty slightly.
- Include a targeted example that addresses recent mistakes when possible.

Response format:
{{
    "a": "your detailed answer here",
    "l": "programming language (python/javascript/general/etc)"
}}

Examples:
For "What is a variable?":
{{
    "a": "A variable is a container that stores data values. Think of it like a labeled box where you can put information and retrieve it later. In Python, you create variables like: name = 'John' or age = 25. You can then use these variables throughout your program.",
    "l": "python"
}}

For non-coding questions:
{{
    "a": "I'm sorry, but I specialize in coding questions. I'd be happy to help you with programming concepts, syntax, or development practices instead!",
    "l": "general"
}}

Question: {_truncate_text(prompt, MAX_USER_PROMPT_CHARS)}

Remember: Respond with ONLY ```json [your json here] ``` and nothing else.
"""


def build_debug_coach_prompt(
    code: str,
    language: str,
    attempt_count: int,
    hint_level: int,
    previous_feedback: str = "",
    learning_context: dict[str, Any] | None = None,
) -> str:
    learning_context = learning_context or {}
    code = _truncate_text(code, MAX_CODE_CHARS)
    previous_feedback = _truncate_text(previous_feedback, 800)
    return f"""
You are Eureka's Debug Coach. Your job is to guide a learner through debugging.

CRITICAL RULES:
- Respond with ONLY valid JSON wrapped in ```json blocks. No other text before or after.
- NEVER return full fixed code unless hint_level is 4.
- Do not solve the problem immediately at hint levels 1, 2, or 3.
- Always ask the learner to try again.

Hint level behavior:
- level 1: identify the issue category and give a vague conceptual hint.
- level 2: point to the specific line or small area most likely involved.
- level 3: provide a partial fix or small code fragment, but not the full solution.
- level 4: provide the full solution and explain why it works.

Learner context:
- skill level: {learning_context.get("skill_level", "beginner")}
- recent mistakes: {json.dumps(learning_context.get("recent_mistakes", []))}
- pace: {learning_context.get("pace", "steady learner")}

Buggy {language} code:
```{language}
{code}
```

Attempt count: {attempt_count}
Current hint_level: {hint_level}
Previous feedback: {previous_feedback}

Response format:
{{
  "hint_level": {hint_level},
  "hint": "your hint here",
  "encouragement": "brief encouragement here",
  "next_step": "what the learner should try next"
}}

Remember: Respond with ONLY ```json [your json here] ``` and nothing else.
"""


def build_challenge_hint_prompt(
    instructions: str,
    code: str,
    test_results: list[dict[str, Any]],
    hint_level: int,
    learning_context: dict[str, Any] | None = None,
) -> str:
    learning_context = learning_context or {}
    summarized_results = _truncate_text(json.dumps(test_results), MAX_TEST_RESULTS_CHARS)
    return build_debug_coach_prompt(
        code=(
            f"Challenge instructions:\n{instructions}\n\n"
            f"Current learner code:\n{code}\n\n"
            f"Latest test results:\n{summarized_results}"
        ),
        language="python",
        attempt_count=max(1, hint_level),
        hint_level=hint_level,
        previous_feedback="The learner is working inside an interactive challenge block.",
        learning_context=learning_context,
    )


def build_challenge_prompt(
    title: str,
    body: str,
    code: str = "",
    language: str = "python",
    learning_context: dict[str, Any] | None = None,
) -> str:
    learning_context = learning_context or {}
    return f"""
You are an interactive coding challenge generator for a terminal coding tutor.

CRITICAL: You MUST respond with ONLY valid JSON wrapped in ```json blocks. No other text before or after.

Generate one runnable Python practice challenge for this lesson section.

JSON shape:
{{
  "topic": "short topic name",
  "language": "python",
  "instructions": "Clear 2-4 sentence task. Tell the learner exactly what function to complete.",
  "starter_code": "Python code with one incomplete function and helpful TODO comments",
  "tests": [
    {{
      "name": "test name",
      "code": "assert function_name(example_input) == expected_output"
    }}
  ]
}}

Rules:
- Use Python even if the lesson is about another language, because the terminal runner supports Python.
- Make the challenge directly related to the section concept.
- Include exactly one function for the learner to complete.
- Include 3-5 tests.
- Tests must be simple Python assert snippets that can run after starter_code.
- Tests must not require network, file system access, packages, stdin, random values, or hidden state.
- If testing printed output, use this exact pattern inside the test:
  import io, contextlib
  stream = io.StringIO()
  with contextlib.redirect_stdout(stream):
      result = function_name(...)
  assert result is None
  assert "expected text" in stream.getvalue()
- Do not call sys.stdout.getvalue().
- Keep starter_code under 40 lines.
- Adapt difficulty to:
  - skill level: {learning_context.get("skill_level", "beginner")}
  - recent mistakes: {json.dumps(learning_context.get("recent_mistakes", []))}
  - pace: {learning_context.get("pace", "steady learner")}

Section title: {_truncate_text(title, 200)}
Section explanation: {_truncate_text(body, MAX_USER_PROMPT_CHARS)}
Existing example code:
```{language}
{_truncate_text(code, 1200)}
```

Remember: Respond with ONLY ```json [your json here] ``` and nothing else.
"""


def generate_course_response(prompt: str, learning_context: dict[str, Any] | None = None) -> str:
    return _post_hc_ai_prompt(build_course_prompt(prompt, learning_context), COURSE_MAX_TOKENS)


def generate_questions_response(prompt: str) -> str:
    return _post_hc_ai_prompt(build_questions_prompt(prompt), QUESTIONS_MAX_TOKENS)


def generate_answer_response(prompt: str, learning_context: dict[str, Any] | None = None) -> str:
    return _post_hc_ai_prompt(build_answer_prompt(prompt, learning_context), QA_MAX_TOKENS)


def generate_debug_coach_response(
    code: str,
    language: str = "python",
    attempt_count: int = 1,
    hint_level: int = 1,
    previous_feedback: str = "",
    learning_context: dict[str, Any] | None = None,
) -> str:
    prompt = build_debug_coach_prompt(
        code=code,
        language=language,
        attempt_count=attempt_count,
        hint_level=max(1, min(4, hint_level)),
        previous_feedback=previous_feedback,
        learning_context=learning_context,
    )
    return _post_hc_ai_prompt(prompt, DEBUG_MAX_TOKENS)


def generate_challenge_hint_response(
    instructions: str,
    code: str,
    test_results: list[dict[str, Any]],
    hint_level: int,
    learning_context: dict[str, Any] | None = None,
) -> str:
    return _post_hc_ai_prompt(
        build_challenge_hint_prompt(
            instructions=instructions,
            code=code,
            test_results=test_results,
            hint_level=max(1, min(4, hint_level)),
            learning_context=learning_context,
        ),
        DEBUG_MAX_TOKENS,
    )


def generate_challenge_response(
    title: str,
    body: str,
    code: str = "",
    language: str = "python",
    learning_context: dict[str, Any] | None = None,
) -> str:
    return _post_hc_ai_prompt(
        build_challenge_prompt(
            title=title,
            body=body,
            code=code,
            language=language,
            learning_context=learning_context,
        ),
        CHALLENGE_MAX_TOKENS,
    )
