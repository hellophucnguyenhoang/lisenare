import pickle
from sqlmodel import Session, select
from app.database import get_session
from app.models import Interaction, UserState, Reading, ReadingEmbedding
import torch
from collections import defaultdict
from datetime import datetime
import numpy as np  # in case embeddings are np arrays

def preprocess_data():
    with next(get_session()) as session:
        statement = select(Interaction).order_by(Interaction.event_time)
        results = session.exec(statement).all()

        # Reward map (adjust if needed)
        reward_map = {'skip': 0, 'view': 1, 'click': 1, 'submit': 5}

        # Group by user_state_id to handle duplicates on same item
        groups = defaultdict(list)
        for inter in results:
            groups[inter.user_state_id].append(inter)

        seq = []
        for us_id in sorted(groups, key=lambda uid: min([i.event_time for i in groups[uid]])):
            group = groups[us_id]
            item = group[0].item_id  # assume same for group
            events = set([i.event_type for i in group])  # unique events
            max_event = max(events, key=lambda e: reward_map.get(e, 0))
            reward = reward_map.get(max_event, 0)
            time = min([i.event_time for i in group])
            user_state = group[0].user_state  # the state before interaction
            seq.append({'item_id': item, 'reward': reward, 'time': time, 'us_id': us_id, 'user_state': user_state})

        # Get EMBED_DIM from first embedding if available
        EMBED_DIM = 392  # default fallback
        if results:
            first_reading = results[0].item
            if first_reading.reading_embedding:
                emb = pickle.loads(first_reading.reading_embedding.vector_blob)
                EMBED_DIM = emb.shape[0] if hasattr(emb, 'shape') else len(emb)

        STATE_LEN = 5  # N, adjust as needed
        LIST_LEN = 3   # K, adjust as needed

        # Cache for embeddings
        item_to_emb = {}

        def get_emb(reading_id, session):
            if reading_id not in item_to_emb:
                stmt = select(ReadingEmbedding).where(ReadingEmbedding.reading_id == reading_id)
                emb_obj = session.exec(stmt).first()
                if emb_obj:
                    emb = pickle.loads(emb_obj.vector_blob)
                    # Convert to torch.tensor
                    if isinstance(emb, np.ndarray):
                        item_to_emb[reading_id] = torch.from_numpy(emb).float()
                    elif isinstance(emb, list):
                        item_to_emb[reading_id] = torch.tensor(emb).float()
                    else:
                        item_to_emb[reading_id] = emb.float()  # assume torch
                else:
                    item_to_emb[reading_id] = torch.zeros(EMBED_DIM)
            return item_to_emb[reading_id]

        historical_data = []

        # For simplicity, assume one big session; if multiple users, group by user_id
        current_state_items = []  # running positive item_ids (but DB has states, we use running for Alg.1)

        items_seq = [d['item_id'] for d in seq]
        rewards_seq = [d['reward'] for d in seq]

        L = len(items_seq)
        for l in range(0, L, LIST_LEN):
            start = l
            end = min(l + LIST_LEN, L)
            a_ids = items_seq[start:end]
            r_list = rewards_seq[start:end]

            # Pad if less than K
            while len(a_ids) < LIST_LEN:
                a_ids.append(0)  # dummy id 0
                r_list.append(0)

            # State s: use running, but you can override with DB user_state if needed
            s_embs = [get_emb(iid, session) for iid in current_state_items[-STATE_LEN:] if iid != 0]
            pad_len = STATE_LEN - len(s_embs)
            if pad_len > 0:
                pad = torch.zeros(pad_len, EMBED_DIM)
                s = torch.cat([pad, torch.stack(s_embs)]) if s_embs else torch.zeros(STATE_LEN, EMBED_DIM)
            else:
                s = torch.stack(s_embs)

            # Alternative: use DB user_state for s (more accurate if DB stores the state)
            # For the first in chunk, get user_state.item_ids
            # us = seq[start]['user_state']
            # if us.item_ids:
            #     past_ids = [int(i) for i in us.item_ids.split(',') if i]
            #     s_embs = [get_emb(iid, session) for iid in past_ids[-STATE_LEN:]]
            #     # pad as above
            # But since paper uses running update, stick with running

            a = torch.stack([get_emb(iid, session) for iid in a_ids])

            r_vec = torch.tensor(r_list, dtype=torch.float)  # float for RL

            historical_data.append(((s, a), r_vec))

            # Update running state
            for k in range(LIST_LEN):
                if r_list[k] > 0 and a_ids[k] != 0:
                    current_state_items.append(a_ids[k])

        # Save
        with open('historical_data.pkl', 'wb') as f:
            pickle.dump(historical_data, f)

        print(f"Built and saved historical_data.pkl with {len(historical_data)} entries")
        print(f"Example entry: s shape {historical_data[0][0][0].shape}, a shape {historical_data[0][0][1].shape}, r {historical_data[0][1]}")

def main():
    preprocess_data()

if __name__ == "__main__":
    main()