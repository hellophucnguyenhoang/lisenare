fastapi dev app/main.py  
fastapi dev app/main.py --host 0.0.0.0  
tensorboard --logdir training_output_continuous


# reset database
rm database.db  
uv run create_fast.py  
uv run refresh_embeddings.py  
uv run kmean_elbow.py
