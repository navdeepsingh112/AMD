import requests

url = "http://134.199.195.53:5000/v1/chat/completions"
headers = {"Content-Type": "application/json"}
data = {
    "model": "/home/user/Models/meta-llama/Llama-3.3-70B-Instruct",
    "messages": [
        {
            "role": "system",
            "content": "provide to the point answer."
        },
        {
            "role": "user",
            "content": "What is day on 08-9-2025?"
        }
    ],
    "stream": False,
    "max_tokens": 128
}

response = requests.post(url, headers=headers, json=data)
print(response.json())

# HIP_VISIBLE_DEVICES=0 vllm serve /home/user/Models/Qwen/Qwen2-7B-Instruct \
#         --gpu-memory-utilization 0.9 \
#         --swap-space 16 \
#         --disable-log-requests \
#         --dtype float16 \
#         --max-model-len 2048 \
#         --tensor-parallel-size 1 \
#         --host 0.0.0.0 \
#         --port 5000 \
#         --num-scheduler-steps 10 \
#         --max-num-seqs 128 \
#         --max-num-batched-tokens 2048 \
#         --max-model-len 2048 \
# #         --distributed-executor-backend "mp"
# !HIP_VISIBLE_DEVICES=0 vllm serve /home/user/Models/meta-llama/Llama-3.3-70B-Instruct \
#         --gpu-memory-utilization 0.9 \
#         --swap-space 16 \
#         --disable-log-requests \
#         --dtype float16 \
#         --max-model-len 2048 \
#         --tensor-parallel-size 1 \
#         --host 0.0.0.0 \
#         --port 5000 \
#         --num-scheduler-steps 10 \
#         --max-num-seqs 128 \
#         --max-num-batched-tokens 2048 \
#         --max-model-len 2048 \
#         --distributed-executor-backend "mp"