from groq import Groq

client = Groq(api_key="")

messages = []

while True:
    user_input = input("Bạn: ")
    if user_input == "exit":
        break

    messages.append({"role": "user", "content": user_input})

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile", messages=messages
    )

    reply = response.choices[0].message.content
    messages.append({"role": "assistant", "content": reply})

    print(f"AI: {reply}\n")
