import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader, random_split
import random
from app.database import get_session
from app.services.item_embeddings import get_random_embeddings
from app.config import settings

# -------------------------------
# Hyperparams
# -------------------------------
NUM_ITEMS = 200
EMBED_DIM = settings.item_embedding_dim  # e.g. 392
N = 5
K = 3
NUM_HIST = 100000
BATCH_SIZE = 64
LR = 1e-3
EPOCHS = 100
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# -------------------------------
# Step 1: Load embeddings & generate synthetic data
# -------------------------------
# --- Replace your current generate_synthetic_history with this improved version ---
import torch
import random
import torch.nn.functional as F

def generate_synthetic_history_improved(
    item_embeddings,
    num_hist=10000,
    n=5,
    k=3,
    gamma_reward=0.9,
    weight_text=0.7,
    weight_diff=0.3,
    sharpness=3.0,   # >1 makes probabilities more peaky
    seed=None
):
    """
    Improved synthetic generator:
      - uses text cosine similarity + difficulty dot
      - uses a sharpness parameter to increase signal
      - computes scalar discounted reward, then normalizes to [0,1]
    Returns list of (state, action, reward_norm)
    """
    if seed is not None:
        random.seed(seed)
        torch.manual_seed(seed)

    # defensive copy to avoid PyTorch warning about non-writable numpy arrays
    if not isinstance(item_embeddings, torch.Tensor):
        item_embeddings = torch.tensor(item_embeddings).float()
    else:
        item_embeddings = item_embeddings.clone().float()

    num_items, embed_dim = item_embeddings.shape
    DIFF_START = 384
    DIFF_END = 390  # 6 dims
    TXT_END = DIFF_START  # first 384 dims are text

    # reaction values (same as you had)
    reaction_values = [-1.0, -0.25, 0.1, 0.5, 0.8, 1.0]

    # Precompute discount denom for normalization:
    discounts = torch.tensor([gamma_reward**i for i in range(k)], dtype=torch.float32)
    min_total = discounts.sum() * min(reaction_values)  # if all -1
    max_total = discounts.sum() * max(reaction_values)  # if all 1

    hist = []
    sims_list = []
    rewards_list = []

    for _ in range(num_hist):
        # sample state and action
        s_idx = torch.randint(0, num_items, (n,))
        a_idx = torch.randint(0, num_items, (k,))
        s = item_embeddings[s_idx]  # (n, D)
        a = item_embeddings[a_idx]  # (k, D)

        # compute state summaries
        s_text_mean = s[:, :TXT_END].mean(0)          # (384,)
        s_diff_mean = s[:, DIFF_START:DIFF_END].mean(0)  # (6,)

        # for each action item, compute combined similarity in [0,1]
        r_vec = []
        per_item_sim = []
        for i in range(k):
            a_text = a[i, :TXT_END]
            a_diff = a[i, DIFF_START:DIFF_END]

            # text sim: cosine in [-1,1] -> map to [0,1]
            sim_text = F.cosine_similarity(s_text_mean.unsqueeze(0), a_text.unsqueeze(0)).item()
            sim_text = (sim_text + 1.0) / 2.0

            # diff sim: dot(state_diff_mean, a_diff) (both one-hot-ish) -> approx [0,1]
            sim_diff = float((s_diff_mean * a_diff).sum().item())

            # combined similarity
            comb = weight_text * sim_text + weight_diff * sim_diff
            comb = max(0.0, min(1.0, comb))

            # sharpen to make stronger signal
            comb_sharp = comb ** sharpness

            per_item_sim.append(comb_sharp)

            # convert comb_sharp to probabilities over reaction_values
            # higher comb -> higher chance of positive reactions
            # we build a score for each reaction, then softmax
            # reaction order: [-1.0, -0.25, 0.1, 0.5, 0.8, 1.0]
            # we set base scores so positive r get boosted by comb_sharp
            base_scores = torch.tensor([0.1, 0.2, 0.5, 1.0, 1.2, 1.0], dtype=torch.float32)
            # amplify positives proportional to comb_sharp
            pos_mask = torch.tensor([0.0, 0.0, 0.0, 1.0, 1.0, 1.0], dtype=torch.float32)
            scores = base_scores + pos_mask * (comb_sharp * 2.0)
            probs = F.softmax(scores, dim=0).numpy().tolist()
            chosen = random.choices(reaction_values, weights=probs)[0]
            r_vec.append(chosen)

        r_vec = torch.tensor(r_vec, dtype=torch.float32)  # (k,)
        # discounted scalar reward (Eq-like)
        total = (discounts * r_vec).sum().item()

        # normalize to [0,1] (affine)
        reward_norm = (total - min_total.item()) / (max_total.item() - min_total.item())

        hist.append((s, a, float(reward_norm)))
        sims_list.append(sum(per_item_sim) / len(per_item_sim))
        rewards_list.append(reward_norm)

    sims_t = torch.tensor(sims_list)
    rewards_t = torch.tensor(rewards_list)
    print("Synthetic generation stats: sim mean/std", sims_t.mean().item(), sims_t.std().item())
    print("Reward norm mean/std", rewards_t.mean().item(), rewards_t.std().item())
    # quick correlation
    try:
        corr = torch.corrcoef(torch.stack([sims_t, rewards_t]))[0,1].item()
        print("sim vs reward corr:", corr)
    except Exception:
        pass

    return hist



with next(get_session()) as session:
    item_embeddings = get_random_embeddings(session, NUM_ITEMS, EMBED_DIM)
historical_data = generate_synthetic_history_improved(item_embeddings,
                                                      num_hist=100000,
                                                      n=N, k=K,
                                                      gamma_reward=0.9,
                                                      weight_text=0.7,
                                                      weight_diff=0.3,
                                                      sharpness=3.0,
                                                      seed=42)
# Works whether r is float or tensor
reward_values = []
for entry in historical_data:
    # handle ((s, a), r) or (s, a, r)
    if isinstance(entry, tuple) and len(entry) == 2:
        (_, _), r = entry
    elif isinstance(entry, tuple) and len(entry) == 3:
        _, _, r = entry
    else:
        continue

    if isinstance(r, torch.Tensor):
        reward_values.append(r.mean().item())
    else:
        reward_values.append(float(r))

reward_values = torch.tensor(reward_values)
print("Reward mean:", reward_values.mean().item())
print("Reward std:", reward_values.std().item())

# -------------------------------
# Step 2: Dataset
# -------------------------------
class RewardDataset(Dataset):
    def __init__(self, data):
        self.data = data

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        s, a, r = self.data[idx]
        s_mean = s.mean(0)
        a_mean = a.mean(0)
        x = torch.cat([s_mean, a_mean], dim=-1)
        return x, torch.tensor(r, dtype=torch.float32)

# -------------------------------
# Step 3: Model
# -------------------------------
class RewardModel(nn.Module):
    def __init__(self, embed_dim, hidden_dims=[512, 256, 128, 64], dropout=0.2):
        """
        Deep feedforward network for reward prediction.

        Args:
            embed_dim (int): Dimension of state/action embedding.
            hidden_dims (list[int]): List of hidden layer sizes.
            dropout (float): Dropout probability.
        """
        super().__init__()
        layers = []
        input_dim = embed_dim * 2  # concatenate state_mean + action_mean
        for h in hidden_dims:
            layers.append(nn.Linear(input_dim, h))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(dropout))
            input_dim = h
        layers.append(nn.Linear(input_dim, 1))  # final scalar output
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        # x: (B, 2*embed_dim)
        return self.net(x).squeeze(-1)

# -------------------------------
# Step 4: Train / Val / Test split
# -------------------------------
dataset = RewardDataset(historical_data)
train_size = int(0.8 * len(dataset))
val_size = int(0.1 * len(dataset))
test_size = len(dataset) - train_size - val_size
train_set, val_set, test_set = random_split(dataset, [train_size, val_size, test_size])

train_loader = DataLoader(train_set, batch_size=BATCH_SIZE, shuffle=True)
val_loader = DataLoader(val_set, batch_size=BATCH_SIZE)
test_loader = DataLoader(test_set, batch_size=BATCH_SIZE)

# -------------------------------
# Step 5: Train
# -------------------------------
model = RewardModel(EMBED_DIM).to(DEVICE)
optimizer = optim.Adam(model.parameters(), lr=LR)
criterion = nn.MSELoss()

def evaluate(model, loader):
    model.eval()
    total_loss, preds, trues = 0, [], []
    with torch.no_grad():
        for x, y in loader:
            x, y = x.to(DEVICE), y.to(DEVICE)
            out = model(x)
            loss = criterion(out, y)
            total_loss += loss.item() * len(y)
            preds.extend(out.cpu().numpy())
            trues.extend(y.cpu().numpy())
    mse = total_loss / len(loader.dataset)
    preds, trues = torch.tensor(preds), torch.tensor(trues)
    r2 = 1 - torch.sum((preds - trues)**2) / torch.sum((trues - trues.mean())**2)
    return mse, r2.item()

best_val_loss = float("inf")
best_model_path = "reward_model_best.pth"

for epoch in range(1, EPOCHS + 1):
    # ----- Train -----
    model.train()
    total_train_loss = 0.0
    for x, y in train_loader:
        x, y = x.to(DEVICE), y.to(DEVICE)
        optimizer.zero_grad()
        out = model(x)
        loss = criterion(out, y)
        loss.backward()
        optimizer.step()
        total_train_loss += loss.item() * len(y)
    train_mse = total_train_loss / len(train_loader.dataset)

    # ----- Validate -----
    val_mse, val_r2 = evaluate(model, val_loader)

    # ----- Log -----
    print(f"Epoch {epoch:02d}: "
          f"Train MSE={train_mse:.4f} | "
          f"Val MSE={val_mse:.4f} | "
          f"Val R²={val_r2:.4f}")

    # ----- Save if improved -----
    if val_mse < best_val_loss:
        best_val_loss = val_mse
        torch.save(model.state_dict(), best_model_path)
        print(f"🟢 Saved new best model (Val MSE = {best_val_loss:.4f})")

# ----- Test the best model -----
model.load_state_dict(torch.load(best_model_path))
test_mse, test_r2 = evaluate(model, test_loader)
print(f"\n✅ Test MSE={test_mse:.4f} | Test R²={test_r2:.4f}")
