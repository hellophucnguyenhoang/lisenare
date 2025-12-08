import numpy as np

filepath = "latency_item_rec_eval_result.txt"

values = []

with open(filepath, "r") as f:
    for i, line in enumerate(f, start=1):
        if 267 <= i <= 280:   # adjust if needed to include/exclude
            try:
                values.append(float(line.strip()))
            except ValueError:
                pass  # skip non-numeric lines if any

values = np.array(values)

mean_val = values.mean()
std_val = values.std()

print("Count:", len(values))
print("Mean:", mean_val)
print("Std:", std_val)
