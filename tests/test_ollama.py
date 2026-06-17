import requests
import time

print("Testing Ollama API...")

start_time = time.perf_counter()

response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "gemma4:e4b-it-qat",
        "prompt": "xin chào",
        "stream": False
    }
)

end_time = time.perf_counter()

result = response.json()["response"]

print("\n=== RESPONSE ===")
print(result)

print("\n=== PERFORMANCE ===")
print(f"Response time: {end_time - start_time:.2f} seconds")