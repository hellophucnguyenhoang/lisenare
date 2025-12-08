fastapi dev app/main.py  
fastapi dev app/main.py --host 0.0.0.0  
fastapi run app/main.py --host 0.0.0.0  
tensorboard --logdir training_output_continuous
uv run python -m spacy download en_core_web_sm

# reset database
rm database.db  
uv run create_fast.py  
uv run refresh_embeddings.py  
uv run kmean_elbow.py

!curl -L "https://huggingface.co/unsloth/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q8_0.gguf" --output llama-3.2-3B-Instruct-f8.gguf
!curl -L "https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-f16.gguf" --output llama-3.2-1B-Instruct-f16.gguf
