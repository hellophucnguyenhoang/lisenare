from sqlmodel import Session, create_engine
from app.services import readings, item_embeddings
from app.config import settings
import numpy as np
from reading_env import Reader
import pandas as pd
import matplotlib.pyplot as plt

# ------------------------
# Chuẩn bị environment
# ------------------------
def reading_vector(reading):
    return np.frombuffer(reading.reading_embedding.vector_blob, dtype=np.float32).copy()

# Kết nối database
engine = create_engine("sqlite:///database.db")
with Session(engine) as session:

    # Khởi tạo user state cố định
    user_level = 1
    user_preference = item_embeddings.init_user_embedding_by_level(session, user_level)
    reader = Reader(settings.item_embedding_dim)
    reader.reset(seed_item_emb=user_preference)
    reader.history.append({
        "reward": -5
    })
    nearest_readings = readings.get_nearest_readings(session, user_preference)

    reader.recent_embs = [reading_vector(r) for r in nearest_readings]

    # print(Reader.diversity(reader.recent_embs))
    # exit()

    # Lấy tất cả embedding và difficulty
    reading_embeddings, item_ids = readings.get_all_embeddings(session)

    # Chạy simulation trên nhiều item random
    n_samples = 100000  # số lượng item random để probe
    history = []
    difficulties = []
    rng = np.random.default_rng(123)
    count = 0
    for _ in range(n_samples):
        selected_idx = rng.choice(item_ids)
        reading = readings.get_full_reading_by_id(session, int(selected_idx))
        difficulty = reading.difficulty
        reading_embed = np.frombuffer(reading.reading_embedding.vector_blob, dtype=np.float32)

        # Lấy info từ reader.step, nhưng KHÔNG cập nhật state
        info = reader.step(reading_embed, update_state=False)
        # if count < 3:
        #     print(info)
        #     count += 1
        # else:
        #     break


        history.append(info)
        difficulties.append(difficulty)

# ------------------------
# Chuyển difficulty sang nhãn CEFR
# ------------------------
difficulty_map = {0:'A1', 1:'A2', 2:'B1', 3:'B2', 4:'C1', 5:'C2'}
labels = [difficulty_map.get(int(d), str(d)) for d in difficulties]

# ------------------------
# Chuẩn bị DataFrame chỉ với event và difficulty
# ------------------------
df = pd.DataFrame({
    'difficulty': labels,
    'event': [h['event'] for h in history],
})

# ------------------------
# Biểu đồ: stacked bar chart - event distribution per difficulty
# ------------------------
event_types = ['dislike','skip','view','submit','like']
count_data = df.groupby(['difficulty','event']).size().unstack(fill_value=0)
count_data = count_data[event_types]  # giữ thứ tự event

# Chuyển sang tỉ lệ %
count_data = count_data.div(count_data.sum(axis=1), axis=0)

# Vẽ stacked bar chart
ax = count_data.plot(kind='bar', stacked=True, figsize=(10,6), colormap='tab20')
plt.ylabel('Proportion')
plt.xlabel('Difficulty')
plt.title(f'User event proportion per difficulty (fixed user level {difficulty_map[user_level]})')
plt.tight_layout()

# Đảo legend để dễ nhìn (cột 'like' lên trên cùng, 'dislike' xuống dưới)
handles, labels = ax.get_legend_handles_labels()
ax.legend(handles[::-1], labels[::-1], title='Event')

# Lưu hình
plt.savefig('event_proportion_per_difficulty_target_diverse.png')
