import json
import os
from typing import Any
from urllib import error, request


GEMINI_MODEL = "gemini-flash-latest"
GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)


def get_gemini_api_key() -> str:
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

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


def _post_gemini_prompt(prompt: str) -> str:
    payload = json.dumps(
        {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt,
                        }
                    ]
                }
            ]
        }
    ).encode("utf-8")

    api_request = request.Request(
        f"{GEMINI_API_URL}?key={get_gemini_api_key()}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(api_request) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise RuntimeError(f"Gemini API error: {exc.code}") from exc

    response_text = (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text")
    )

    if not response_text:
        raise RuntimeError("Gemini API returned an empty response")

    return extract_json_response(response_text)


def build_course_prompt(prompt: str) -> str:
    return f"""
You are a coding course writer. You write courses that teach coding to beginners.
You will be given a prompt that describes the course you need to write.

CRITICAL: You MUST respond with ONLY valid JSON wrapped in ```json blocks. No other text before or after.
For each course, you will create a w3school-style course outline with a title, description, language, and structured parts.

A section's content, "c", MUST be an array of objects. Each object can be a paragraph or a code block.
- For a paragraph, use: {{ "type": "p", "text": "your paragraph text here" }}
- For a code block, use: {{ "type": "code", "lang": "language-name", "code": "your code here" }}

Your task is to generate a course outline in JSON format with the following structure (This is an example of a Python course, the contents are single sentences, but you HAVE to write detailed explinations and examples):
{{
    "t": "Python for Beginners: A Comprehensive Introduction",
    "d": "This course provides a friendly and accessible introduction to Python programming. Learn the fundamentals of Python syntax, data structures, control flow, and object-oriented programming. Build practical projects to solidify your understanding and gain the skills necessary to write your own Python programs.",
    "l": "python",
    "c": [
        {{
            "n": "Part 1: Getting Started with Python",
            "d": "Introduction to Python, installation, setting up a development environment, and basic syntax. Covering variables, data types (integers, floats, strings, booleans), and simple operations. Using the print() function. Examples: simple calculations, string concatenation, and basic input using input().",
            "s": [
                {{
                    "t": "Introduction to Python",
                    "c": [
                        {{ "type": "p", "text": "Python is a high-level, interpreted programming language known for its readability and simple syntax. It was created by Guido van Rossum and first released in 1991." }},
                        {{ "type": "p", "text": "It is used in web development, data science, artificial intelligence, and more. This section will introduce you to the fundamental concepts of Python." }},
                        {{ "type": "code", "lang": "python", "code": "print('Hello, World!')" }},
                        {{ "type": "p", "text": "The code above is a simple Python program that prints 'Hello, World!' to the console. The print() function is a built-in function that outputs text." }}
                    ]
                }},
                {{
                    "t": "Setting up your Environment",
                    "c": [{{ "type": "p", "text": "Installing Python, choosing an IDE (VS Code, PyCharm), running your first Python program."}}]
                }},
                {{
                    "t": "Variables and Data Types",
                    "c": [{{ "type": "p", "text": "Understanding variables, assigning values, exploring integers, floats, strings, and booleans."}}]
                }},
                {{
                    "t": "Basic Operations",
                    "c": [{{"type": "p", "text": "Performing arithmetic operations (+, -, *, /), string concatenation, and working with input."}}]
                }}
            ]
        }},
        {{
            "n": "Part 2: Control Flow and Looping",
            "d": "Exploring conditional statements (if, elif, else) and loop structures (for loops, while loops). Learning about logical operators (and, or, not) and how to use them in control flow. Examples: building a simple calculator, implementing a guessing game, and iterating through lists.",
            "s": [
                {{
                    "t": "Conditional Statements",
                    "c": [{{"type": "p", "text": "Using `if`, `elif`, and `else` to make decisions based on conditions."}}]
                }},
                {{
                    "t": "For Loops",
                    "c": [{{"type": "p", "text": "Iterating through sequences (lists, strings, ranges) using `for` loops."}}]
                }},
                {{
                    "t": "While Loops",
                    "c": [{{"type": "p", "text": "Repeating code blocks as long as a condition is true using `while` loops."}}]
                }},
                {{
                    "t": "Logical Operators",
                    "c": [{{"type": "p", "text": "Combining conditions using `and`, `or`, and `not`."}}]
                }}
            ]
        }},
        {{
            "n": "Part 3: Data Structures: Lists and Dictionaries",
            "d": "In-depth look at lists and dictionaries, two fundamental Python data structures. Covering list operations (accessing elements, slicing, appending, inserting, removing), dictionary operations (adding, accessing, modifying, deleting key-value pairs), and common use cases. Examples: creating a to-do list, managing student records, and counting word frequencies.",
            "s": [
                {{
                    "t": "Lists: Introduction",
                    "c": [{{"type": "p", "text": "Creating lists, accessing elements, list slicing."}}]
                }},
                {{
                    "t": "Lists: Operations",
                    "c": [{{"type": "p", "text": "Appending, inserting, removing, sorting, and searching within lists."}}]
                }},
                {{
                    "t": "Dictionaries: Introduction",
                    "c": [{{"type": "p", "text": "Creating dictionaries, adding key-value pairs, accessing values."}}]
                }},
                {{
                    "t": "Dictionaries: Operations",
                    "c": [{{"type": "p", "text": "Modifying, deleting, iterating through dictionaries."}}]
                }}
            ]
        }},
        {{
            "n": "Part 4: Functions and Modules",
            "d": "Understanding functions for code reusability and modularity. Defining functions, passing arguments, returning values, and using built-in functions. Introduction to modules and importing external libraries. Examples: creating a function to calculate the area of a rectangle, writing a module for mathematical operations, and using the `math` module.",
            "s": [
                {{
                    "t": "Defining Functions",
                    "c": [{{"type": "p", "text": "Creating your own functions with parameters and return values."}}]
                }},
                {{
                    "t": "Function Arguments",
                    "c": [{{"type": "p", "text": "Passing arguments by position and keyword."}}]
                }},
                {{
                    "t": "Built-in Functions",
                    "c": [{{"type": "p", "text": "Exploring useful built-in functions like `len()`, `range()`, and `sum()`."}}]
                }},
                {{
                    "t": "Modules",
                    "c": [{{"type": "p", "text": "Importing and using external libraries like `math` and `random`."}}]
                }}
            ]
        }}
    ]
}}

Guidelines:
- Make each part comprehensive but concise (max 800 characters per part)
- Include practical examples and explanations
- Structure each part with clear headings and content
- Use markdown formatting within content strings
- Create 3-5 parts for a complete course

Here is the prompt: {prompt}

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
    "correct": "a1"
}}

Guidelines:
- Generate 1-2 questions per course part
- Make questions challenging but fair
- Ensure one answer is clearly correct
- Use the 0-based index for the "part" field
- Each question should be multiple choice with exactly 4 options
- The "correct" field must be one of: "a1", "a2", "a3", or "a4"

Here is the course content: {prompt}

Remember: Respond with ONLY ```json [your json array here] ``` and nothing else.
"""


def build_answer_prompt(prompt: str) -> str:
    return f"""
You are an AI assistant specialized in answering coding questions for beginners.

CRITICAL: You MUST respond with ONLY valid JSON wrapped in ```json blocks. No other text before or after.

Guidelines:
- If the question is not coding-related, politely decline in the answer field
- For coding questions, provide clear, beginner-friendly explanations
- If a language is specified, focus on that language; otherwise use Python or give general advice
- Include practical examples when helpful
- Keep answers informative but concise (max 1000 characters)

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

Question: {prompt}

Remember: Respond with ONLY ```json [your json here] ``` and nothing else.
"""


def generate_course_response(prompt: str) -> str:
    return _post_gemini_prompt(build_course_prompt(prompt))


def generate_questions_response(prompt: str) -> str:
    return _post_gemini_prompt(build_questions_prompt(prompt))


def generate_answer_response(prompt: str) -> str:
    return _post_gemini_prompt(build_answer_prompt(prompt))
