a = []


for i in range(5):
    a.append({"text": "abc", "start": i})

for chunk in a:
    print(chunk["text"])
    print(chunk["start"])
    print()