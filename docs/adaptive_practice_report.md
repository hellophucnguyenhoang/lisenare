# Báo cáo chi tiết: Chức năng Adaptive Practice

## 1. Tổng quan

Tính năng **Adaptive Practice** cho phép người học chọn nhiều `topic` để luyện tập câu hỏi dạng `REVIEW`. Backend tạo một **practice session tạm thời lưu trên Redis** (không tạo bảng session trong database), liên tục cập nhật theta của người học sau mỗi câu trả lời và chọn câu tiếp theo theo thuật toán IRT đơn giản dựa trên độ chênh giữa `theta` và `difficulty`.

### Đặc điểm chính

- **Một lần query DB duy nhất** ở thời điểm bắt đầu session để nạp toàn bộ `(question_id, difficulty)` vào Redis.
- Việc chọn câu tiếp theo chỉ dùng Redis Sorted Set, **không join 4 bảng mỗi lần**.
- DB chỉ được truy vấn theo primary key khi cần lấy chi tiết câu hỏi để chấm hoặc trả về cho FE.
- Mỗi session có `session_id` (UUID4 hex) và một bộ key Redis riêng để tránh lẫn dữ liệu giữa các người dùng.
- Tất cả Redis key đều có **TTL = 7200 giây** (mặc định, cấu hình được).
- Không bao giờ trả `correct_answer` của `next_question` cho FE.

---

## 2. Thiết kế Redis

Mỗi session sử dụng 2 key:

| Key | Kiểu | Mục đích |
|---|---|---|
| `practice:session:{session_id}:pool` | Sorted Set | Pool câu hỏi còn lại. `score = difficulty`, `member = question_id`. |
| `practice:session:{session_id}:state` | Hash | Trạng thái session. |

### Các trường của Hash state

| Field | Ý nghĩa |
|---|---|
| `learner_id` | ID người học sở hữu session |
| `theta` | Theta hiện tại của session |
| `current_question_id` | ID câu hỏi đang chờ trả lời |
| `topic_ids` | Danh sách topic ban đầu (string, join bằng dấu phẩy) |
| `started_at` | Thời điểm bắt đầu session (ISO 8601, UTC) |

**TTL** mặc định: `7200` giây — refresh sau mỗi lần `/practice/answer` để session “sống” trong quá trình người dùng đang thao tác.

---

## 3. Danh sách file đã tạo / chỉnh sửa

### File mới

| File | Vai trò |
|---|---|
| [app/redis_client.py](../app/redis_client.py) | Khởi tạo singleton Redis client từ `REDIS_URL`. Dùng làm FastAPI dependency. |
| [app/schemas/practice.py](../app/schemas/practice.py) | Pydantic models cho request/response của 3 API. |
| [app/services/practice_service.py](../app/services/practice_service.py) | Toàn bộ logic nghiệp vụ (start / answer / end / chọn câu / build payload). |
| [app/routers/practice_router.py](../app/routers/practice_router.py) | Khai báo 3 endpoint dưới prefix `/practice`. |
| [tests/test_practice.py](../tests/test_practice.py) | 9 test case dùng `fakeredis` + SQLite in-memory. |

### File chỉnh sửa

| File | Thay đổi |
|---|---|
| [app/config.py](../app/config.py) | Thêm `redis_url` (default `redis://localhost:6379/0`) và `practice_session_ttl=7200`. |
| [app/schemas/__init__.py](../app/schemas/__init__.py) | Thêm `from .practice import *` để re-export schemas. |
| [app/main.py](../app/main.py) | Import và `include_router(practice_router.router)`. |

> `pyproject.toml` **không cần chỉnh** vì `redis>=7.1.0` và `fakeredis>=2.35.1` đã có sẵn trong dependencies.

---

## 4. Chi tiết các schema

File [app/schemas/practice.py](../app/schemas/practice.py).

### Request

```python
class StartPracticeRequest(BaseModel):
    learner_id: int
    topic_ids: list[int] = Field(min_length=1)   # validate rỗng → 422

class AnswerPracticeRequest(BaseModel):
    session_id: str
    learner_id: int
    question_id: int
    user_answer: str

class EndPracticeRequest(BaseModel):
    session_id: str
    learner_id: int
```

### Response

```python
class PracticeQuestionResponse(BaseModel):
    id: int
    question: str | None
    content: str | None
    answer: str | None
    type: str | None
    difficulty: float
    # KHÔNG có correct_answer — tránh lộ đáp án cho FE

class StartPracticeResponse(BaseModel):
    session_id: str
    theta: float
    question: PracticeQuestionResponse

class AnswerPracticeResponse(BaseModel):
    is_correct: bool
    correct_answer: str | None      # đáp án của CÂU VỪA TRẢ LỜI (cho phép)
    theta: float
    practice_completed: bool
    next_question: PracticeQuestionResponse | None
```

---

## 5. Chi tiết các hàm trong `practice_service.py`

### 5.1. Hàm tiện ích Redis

```python
def _pool_key(session_id: str) -> str
def _state_key(session_id: str) -> str
```
Sinh key Redis theo convention `practice:session:{sid}:pool` / `:state`.

```python
def _load_state(r: redis.Redis, session_id: str) -> dict
```
Đọc Hash state, **raise 410** nếu không tồn tại (session expired hoặc sai `session_id`).

```python
def _assert_learner(state: dict, learner_id: int) -> None
```
So sánh `learner_id` trong request với `state.learner_id`, **raise 403** nếu khác.

---

### 5.2. `select_next_question_id(r, session_id, theta) -> int | None`

Thuật toán chọn câu tiếp theo dựa trên Redis Sorted Set.

```python
_WINDOWS = [0.405, 0.8, 1.2, 2.0]
```

Cơ sở: với mô hình IRT đơn giản `P(correct) = 1 / (1 + exp(-(theta - difficulty)))`, khoảng `|theta - difficulty| <= 0.405` tương ứng `P ∈ [0.4, 0.6]` — vùng “vừa sức”.

Luồng:
1. Lặp qua các window nửa-độ-rộng `0.405 → 0.8 → 1.2 → 2.0`.
2. Mỗi lần gọi `ZRANGEBYSCORE pool (theta - half) (theta + half)`.
3. Nếu có ứng viên, `random.choice` để tránh trùng lặp giữa các session.
4. Nếu **không có** câu nào trong window rộng nhất → lấy toàn bộ pool và chọn câu có `|difficulty - theta|` nhỏ nhất.
5. Trả `None` khi pool rỗng (kết thúc session).

> Câu đã trả lời được `ZREM` khỏi pool ngay sau khi xử lý, nên thuật toán không bao giờ chọn lại.

---

### 5.3. `get_question_public_payload(session, question_id) -> PracticeQuestionResponse`

Query Question theo primary key, **raise 404** nếu không có. Trả về payload **không bao gồm** `correct_answer`.

---

### 5.4. `_initial_theta(session, learner_id, topic_ids) -> float`

Tính theta khởi tạo cho session:

```sql
SELECT theta
FROM thetalearnerlesson
JOIN lesson ON thetalearnerlesson.lesson_id = lesson.id
WHERE learner_id = :learner_id AND lesson.topic_id IN :topic_ids
```

- Có dữ liệu → trả **trung bình cộng** các `theta` của lesson thuộc topic được chọn.
- Không có dữ liệu → fallback `0.0`.

Logic này tận dụng `ThetaLearnerLesson` đã được cập nhật bởi `insert_or_update_theta` ở các flow `grammar_router` hiện có.

---

### 5.5. `start_practice_session(session, r, learner_id, topic_ids)`

Đầu vào: SQLModel `Session`, Redis client, `learner_id`, `topic_ids`.

Các bước:

1. **Validate** `topic_ids` rỗng → 400 (FastAPI thực ra trả 422 do `Field(min_length=1)` ở schema).
2. **Một query duy nhất** join Question → Exercise → Lesson:
   ```python
   select(Question.id, Question.difficulty)
       .join(Exercise, Question.exercise_id == Exercise.id)
       .join(Lesson, Exercise.lesson_id == Lesson.id)
       .where(Lesson.topic_id.in_(topic_ids))
       .where(Exercise.exercise_type == ExerciseType.REVIEW)
   ```
   Dùng **enum `ExerciseType.REVIEW`** chứ không hardcode chuỗi.
3. Nếu rỗng → **404 `No REVIEW questions found for the selected topics`**.
4. Sinh `session_id = uuid.uuid4().hex`.
5. `ZADD` toàn bộ `(question_id, difficulty)` vào pool.
6. Tính `theta` khởi tạo qua `_initial_theta`.
7. Gọi `select_next_question_id` để chọn câu đầu tiên.
8. `HSET` state, `EXPIRE` 2 key bằng `settings.practice_session_ttl`.
9. Load chi tiết câu đầu qua `get_question_public_payload`.

Trả: `(session_id, theta, PracticeQuestionResponse)`.

---

### 5.6. `submit_practice_answer(session, r, session_id, learner_id, question_id, user_answer)`

Các bước:

1. `_load_state` (raise 410 nếu hết hạn).
2. `_assert_learner` (raise 403 nếu sai chủ).
3. Kiểm tra `question_id == state.current_question_id` → 400 nếu không khớp.
4. Query `Question` theo PK; nếu không có → 404.
5. **Chấm**: `is_correct = compare_strings(question.correct_answer, user_answer)`.
   `compare_strings` (đã có sẵn trong `history_answer_question_service`) tách theo dấu phẩy, trim, lower-case — dùng để đồng nhất với flow hiện có của `grammar_router`.
6. Lưu lịch sử qua `insert_history_answer_question(...)`.
7. **Cập nhật theta** bằng `update_theta` reuse từ `theta_learner_lesson_service`:
   ```python
   new_theta = update_theta(theta,
                            items=[(1, difficulty)],
                            responses=[1 if is_correct else 0])
   ```
   Hệ số phân biệt `a = 1` (đơn giản hoá theo công thức trong file).
8. `ZREM` câu vừa trả lời khỏi pool.
9. Chọn câu kế tiếp:
   - Còn câu: cập nhật `current_question_id` & `theta` trong state, load detail, set `practice_completed = false`.
   - Hết câu: xoá `current_question_id` khỏi state, `practice_completed = true`, `next_question = null`.
10. Refresh TTL state (và pool nếu chưa kết thúc).

Trả dict:
```python
{
    "is_correct": bool,
    "correct_answer": str | None,    # của câu vừa trả lời, được phép trả
    "theta": float,
    "practice_completed": bool,
    "next_question": PracticeQuestionResponse | None,
}
```

---

### 5.7. `end_practice_session(r, session_id, learner_id)`

1. `_load_state` → 410 nếu không tồn tại.
2. `_assert_learner` → 403 nếu sai chủ.
3. `DEL` cả hai key (pool + state).
4. Trả `{"message": "Practice session ended"}`.

Nếu user không chủ động gọi end, Redis sẽ tự xoá khi hết TTL.

---

## 6. Chi tiết các API

### 6.1. `POST /practice/start`

| | |
|---|---|
| **Mục đích** | Bắt đầu một session adaptive practice |
| **Body** | `StartPracticeRequest` |
| **Response** | `StartPracticeResponse` |
| **Lỗi** | `422` topic_ids rỗng · `404` không có câu REVIEW |

Ví dụ:

```http
POST /practice/start
{
  "learner_id": 1,
  "topic_ids": [1, 2, 3]
}
```

Response:

```json
{
  "session_id": "5fae...c8b",
  "theta": 0.0,
  "question": {
    "id": 123,
    "question": "...",
    "content": "...",
    "answer": "A|B|C",
    "type": "multiple_choice",
    "difficulty": 0.2
  }
}
```

### 6.2. `POST /practice/answer`

| | |
|---|---|
| **Mục đích** | Chấm câu hiện tại, cập nhật theta, trả câu kế tiếp |
| **Body** | `AnswerPracticeRequest` |
| **Response** | `AnswerPracticeResponse` |
| **Lỗi** | `400` question_id không phải current · `403` learner mismatch · `404` question không tồn tại · `410` session expired |

Response khi vẫn còn câu:

```json
{
  "is_correct": true,
  "correct_answer": "A",
  "theta": 0.35,
  "practice_completed": false,
  "next_question": {
    "id": 456,
    "question": "...",
    "content": "...",
    "answer": "...",
    "type": "...",
    "difficulty": 0.4
  }
}
```

Response khi hết câu:

```json
{
  "is_correct": false,
  "correct_answer": "B",
  "theta": -0.21,
  "practice_completed": true,
  "next_question": null
}
```

### 6.3. `POST /practice/end`

| | |
|---|---|
| **Mục đích** | Kết thúc & dọn dẹp Redis ngay lập tức |
| **Body** | `EndPracticeRequest` |
| **Response** | `{"message": "Practice session ended"}` |
| **Lỗi** | `403` learner mismatch · `410` session expired |

---

## 7. Cấu hình môi trường

Bổ sung trong `.env` (hoặc biến môi trường):

```env
REDIS_URL=redis://localhost:6379/0
# Tuỳ chọn:
PRACTICE_SESSION_TTL=7200
```

Trên Windows, cần một Redis instance đang chạy (Docker, Memurai, hoặc WSL). Nếu chưa khởi động Redis, các API sẽ trả lỗi `ConnectionRefusedError`.

---

## 8. Test

File [tests/test_practice.py](../tests/test_practice.py) dùng **fakeredis** + **SQLite in-memory** (StaticPool để các connection share cùng DB) và override `get_session`, `get_redis` qua `app.dependency_overrides`.

### 8.1. Fixtures

| Fixture | Vai trò |
|---|---|
| `engine` | SQLite in-memory + `StaticPool`, chỉ `create_all` các bảng cần (Learner, Topic, Lesson, Exercise, Question, HistoryAnswerQuestion, ThetaLearnerLesson) để tránh JSONB-only của các bảng khác. |
| `fake_redis` | `fakeredis.FakeRedis(decode_responses=True)` |
| `db_session` | Seed dữ liệu mẫu: 2 learner, 1 topic, 1 lesson, 1 exercise REVIEW (3 câu), 1 exercise PRACTICE (1 câu — không được vào pool). |
| `client` | `TestClient` với dependency overrides cho session/redis. |

### 8.2. Test cases

| # | Test | Kiểm tra |
|---|---|---|
| 1 | `test_start_creates_redis_pool` | Start tạo pool có **đúng 3 câu REVIEW** (loại câu PRACTICE), state có `learner_id`, TTL > 0, không lộ `correct_answer`. |
| 2 | `test_start_with_no_review_questions_returns_404` | Topic không tồn tại → 404. |
| 3 | `test_start_empty_topic_ids_returns_422` | `topic_ids = []` → 422. |
| 4 | `test_answer_correct_returns_next_and_updates_theta` | Đáp đúng → `is_correct=true`, `theta > 0`, next_question.id khác câu hiện tại. |
| 5 | `test_answer_wrong_returns_next_and_updates_theta` | Đáp sai → `is_correct=false`, `theta < 0`. |
| 6 | `test_answered_question_not_repicked` | Trả lời lần lượt cả 3 câu, đảm bảo không chọn lại câu cũ, pool cuối cùng rỗng. |
| 7 | `test_end_deletes_redis_keys` | Sau `/end`, cả pool key & state key đều bị xoá. |
| 8 | `test_other_learner_cannot_use_session` | Learner khác gọi `/answer` hoặc `/end` → 403. |
| 9 | `test_expired_session_returns_410` | `session_id` không tồn tại → 410. |

Kết quả: **9 passed in 9.12s** (`uv run pytest tests/test_practice.py`).

---

## 9. Bảo mật / Quy ước nhất quán với codebase

- **Không** trả `correct_answer` của `next_question` — chỉ trả của câu vừa trả lời để FE có thể hiển thị giải thích nếu cần.
- **Không** lưu `content` / `options` / `correct_answer` đầy đủ vào Redis — Redis chỉ giữ `question_id` và `difficulty`.
- Mọi key Redis đều set TTL → tránh “rò” memory nếu user không gọi `/end`.
- Dùng enum `ExerciseType.REVIEW` thay cho hardcode `"review"` / `"REVIEW"`.
- Validate đầy đủ ranh giới lỗi: `topic_ids` rỗng, không có câu REVIEW, session hết hạn, learner mismatch, question_id không phải current, question không tồn tại.
- `learner_id` lấy từ body (giữ nhất quán với pattern hiện tại trong [grammar_router.py](../app/routers/grammar_router.py) — chưa dùng auth token).
- Cập nhật theta tái dùng `update_theta` đã có sẵn trong [theta_learner_lesson_service.py](../app/services/theta_learner_lesson_service.py) thay vì viết lại công thức IRT.

---

## 10. Luồng hoạt động end-to-end

```
FE                 Backend                   Redis                  DB
 │                    │                        │                     │
 ├─ POST /start ─────►│                        │                     │
 │                    ├─ join 4 bảng ──────────┼────────────────────►│
 │                    │◄─ (qid, difficulty) ───┼─────────────────────┤
 │                    ├─ ZADD pool ───────────►│                     │
 │                    ├─ HSET state ──────────►│                     │
 │                    ├─ EXPIRE 7200 ─────────►│                     │
 │                    ├─ ZRANGEBYSCORE ───────►│                     │
 │                    │◄─ first qid ───────────┤                     │
 │                    ├─ SELECT Question ──────┼────────────────────►│
 │◄─ sid + question ──┤                        │                     │
 │                    │                        │                     │
 ├─ POST /answer ────►│                        │                     │
 │                    ├─ HGETALL state ───────►│                     │
 │                    ├─ SELECT Question ──────┼────────────────────►│
 │                    ├─ chấm + update_theta ──│                     │
 │                    ├─ INSERT history ───────┼────────────────────►│
 │                    ├─ ZREM (qid) ──────────►│                     │
 │                    ├─ ZRANGEBYSCORE ───────►│                     │
 │                    ├─ HSET (theta, qid) ───►│                     │
 │◄─ result + next ───┤                        │                     │
 │                    │                        │                     │
 ├─ POST /end ───────►│                        │                     │
 │                    ├─ DEL pool, state ─────►│                     │
 │◄─ ok ──────────────┤                        │                     │
```

---

## 11. Hướng mở rộng (gợi ý)

- Thêm authentication: lấy `learner_id` từ JWT thay vì body.
- Lưu lịch sử session (tổng số câu, tỉ lệ đúng) vào DB sau khi kết thúc để hỗ trợ báo cáo tiến độ.
- Hỗ trợ "skip" câu hỏi: đưa câu bị skip xuống cuối pool với score xa theta.
- Cấu hình `_WINDOWS` qua settings để tuning thuật toán mà không cần deploy lại code.
- Thêm rate-limit theo `session_id` để chống abuse.
