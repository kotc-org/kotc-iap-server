import json

with open('institutes.json', encoding="utf8") as inp:
    data = json.loads(inp.read())
    print(len(data))
