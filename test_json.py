import re
import json

content = """Sure, here are some suggestions:
```json
{
  "suggestions": [
     {"title": "A", "description": "B"}
  ]
}
```
Good luck!
"""

match = re.search(r'(\{[\s\S]*"suggestions"[\s\S]*\})', content)
if match:
    try:
        data = json.loads(match.group(1))
        print("SUCCESS:", data)
    except Exception as e:
        print("FAIL LOAD:", e)
else:
    print("NO MATCH")
