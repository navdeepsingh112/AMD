import requests

url = "http://134.199.195.53:5000/llm"
data = {
    "message": "hi"
}

response = requests.post(url, json=data)

print("Status Code:", response.status_code)
print("Response Body:", response.text)
