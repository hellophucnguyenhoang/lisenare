import torch

o = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(o)
