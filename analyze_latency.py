import re
import numpy as np

LOG_FILE = "latency_item_rec.log"

# Regex to extract numbers like "total=71.70 ms"
pattern = re.compile(
    r"total=([\d.]+) ms \| inference=([\d.]+) ms \| db=([\d.]+) ms"
)

totals = []
inferences = []
dbs = []

with open(LOG_FILE, "r") as f:
    for line in f:
        match = pattern.search(line)
        if match:
            total, inf, db = map(float, match.groups())
            totals.append(total)
            inferences.append(inf)
            dbs.append(db)

def summarize(name, values):
    mean = np.mean(values)
    std = np.std(values)
    print(f"{name}: mean={mean:.3f} ms, std={std:.3f} ms")

print("=== Latency Summary ===")
summarize("Total", totals)
summarize("Inference", inferences)
summarize("DB", dbs)
