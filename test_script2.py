import json
import urllib.request
from main import Course, Part, Section

req = urllib.request.Request(
    "http://127.0.0.1:8000/api/ai/generate-course",
    data=json.dumps({"prompt": "rust"}).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
with urllib.request.urlopen(req) as response:
    data = json.loads(response.read().decode("utf-8"))
    
course_data_str = data.get("response", "")
print("RAW STRING:", repr(course_data_str[:50]))
course_data = json.loads(course_data_str)

course = Course(title=course_data.get("t", "Unknown Course"), parts=[])
course_lang = course_data.get("l", "text")
for part_data in course_data.get("c", []):
    part = Part(title=part_data.get("n", "Unknown Part"), sections=[])
    for sec_data in part_data.get("s", []):
        sec_title = sec_data.get("t", "Unknown Section")
        body_parts = []
        code = None
        code_lang = course_lang
        footer_parts = []
        
        found_code = False
        for content in sec_data.get("c", []):
            if content.get("type") == "p":
                if not found_code:
                    body_parts.append(content.get("text", ""))
                else:
                    footer_parts.append(content.get("text", ""))
            elif content.get("type") == "code":
                code = content.get("code", "")
                code_lang = content.get("lang", course_lang)
                found_code = True
                
        sec = Section(
            title=sec_title,
            body="\n\n".join(body_parts),
            code=code,
            code_lang=code_lang,
            footer="\n\n".join(footer_parts) if footer_parts else None
        )
        part.sections.append(sec)
    course.parts.append(part)

print("Parsed course:", course.title, len(course.parts), "parts")
