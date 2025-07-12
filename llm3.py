import requests

url = "http://134.199.195.53:5000/v1/chat/completions"
headers = {"Content-Type": "application/json"}
data = {
    "model": "/home/user/Models/deepseek-ai/deepseek-llm-7b-chat",
    "messages": [
        {
            "role": "system",
            "content": "You are an expert in the field of AI. Make sure to provide an explanation in few sentences."
        },
        {
            "role": "user",
            "content": "Explain the concept of AI Agents."
        }
    ],
    "stream": False,
    "max_tokens": 128
}

response = requests.post(url, headers=headers, json=data)
print(response.json())
