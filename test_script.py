import json
import urllib.request

req = urllib.request.Request(
    "http://127.0.0.1:8000/api/ai/generate-course",
    data=json.dumps({"prompt": "rust"}).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
with urllib.request.urlopen(req) as response:
    data = json.loads(response.read().decode("utf-8"))
    
print("Response keys:", data.keys())
print("Response content:", data.get("response")[:100])
