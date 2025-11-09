from sqlmodel import select
from app.database import get_session
from app.models import Interaction, ReadingEmbedding
import torch
from collections import defaultdict
import numpy as np
import pickle
from app.config import settings

def preprocess_data():
    with next(get_session()) as session:
        # Lấy tất cả interaction theo thời gian
        statement = select(Interaction).order_by(Interaction.event_time)
        results = session.exec(statement).all()

        reward_map = {
            "skip": -0.25,
            "view": 0.1,
            "click": 0.5,
            "submit": 0.8,
            "like": 1.0,
            "dislike": -1.0,
            "retry": 0.5
        }

        # Gom interactions theo user
        user_groups = defaultdict(list)
        for inter in results:
            user_id = inter.user_state.user_id
            user_groups[user_id].append(inter)

        EMBED_DIM = settings.item_embedding_dim
        STATE_LEN = 4  # N
        LIST_LEN = 3   # K

        # Cache embedding để không query DB nhiều lần
        item_to_emb = {}

        def get_emb(reading_id):
            if reading_id not in item_to_emb:
                stmt = select(ReadingEmbedding).where(ReadingEmbedding.reading_id == reading_id)
                emb_obj = session.exec(stmt).first()
                if emb_obj and emb_obj.vector_blob:
                    emb = np.frombuffer(emb_obj.vector_blob, dtype=np.float32)
                    emb = torch.from_numpy(emb).float()
                    item_to_emb[reading_id] = emb
                else:
                    item_to_emb[reading_id] = torch.zeros(EMBED_DIM)
            return item_to_emb[reading_id]

        historical_data = []

        for user_id, inters in user_groups.items():
            # sort interaction theo thời gian
            inters.sort(key=lambda i: i.event_time)

            # gom theo item, chỉ lấy max reward
            item_seq = []
            item_rewards = {}
            for inter in inters:
                iid = inter.item_id
                r = reward_map.get(inter.event_type, 0)
                if iid not in item_rewards or r > item_rewards[iid]:
                    item_rewards[iid] = r
            # tạo danh sách item theo thứ tự interaction
            seen_items = []
            for inter in inters:
                iid = inter.item_id
                if iid not in seen_items:
                    item_seq.append((iid, item_rewards[iid]))
                    seen_items.append(iid)

            # trạng thái chạy (last N positive items)
            positive_items = []

            L = len(item_seq)
            for l in range(0, L, LIST_LEN):
                a_ids = [item_seq[i][0] for i in range(l, min(l + LIST_LEN, L))]
                r_list = [item_seq[i][1] for i in range(l, min(l + LIST_LEN, L))]

                # padding nếu thiếu K
                while len(a_ids) < LIST_LEN:
                    a_ids.append(0)
                    r_list.append(0)

                # build state s_t
                s_ids = positive_items[-STATE_LEN:]
                s_embs = [get_emb(iid) for iid in s_ids if iid != 0]
                pad_len = STATE_LEN - len(s_embs)
                if pad_len > 0:
                    pad = torch.zeros(pad_len, EMBED_DIM)
                    s = torch.cat([pad, torch.stack(s_embs)]) if s_embs else torch.zeros(STATE_LEN, EMBED_DIM)
                else:
                    s = torch.stack(s_embs)

                # build action a_t
                a_embs = [get_emb(iid) for iid in a_ids]
                a = torch.stack(a_embs)
                r_vec = torch.tensor(r_list, dtype=torch.float)

                historical_data.append(((s, a), r_vec))

                # update positive_items
                for k, iid in enumerate(a_ids):
                    if r_list[k] > 0 and iid != 0:
                        positive_items.append(iid)

        # save historical data
        with open('historical_data.pkl', 'wb') as f:
            pickle.dump(historical_data, f)

        print(f"Built and saved historical_data.pkl with {len(historical_data)} entries")
        if historical_data:
            print("Example shapes:")
            print("s:", historical_data[0][0][0].shape)
            print("a:", historical_data[0][0][1].shape)
            print("r:", historical_data[0][1])

def main():
    preprocess_data()

if __name__ == "__main__":
    main()
