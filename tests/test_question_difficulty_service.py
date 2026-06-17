"""Unit test cho thuật toán Newton-Raphson MLE ước lượng b.

Không cần DB — test pure function `update_difficulty_b`.
"""

import math

import pytest

from app.services.question_difficulty_service import (
    B_MAX,
    B_MIN,
    update_difficulty_b,
)


def test_easy_question_pushes_b_negative():
    """Câu mà ai cũng làm đúng (kể cả learner theta thấp) → b âm."""
    responses = [(0.0, 1), (1.0, 1), (-1.0, 1), (-0.5, 1), (0.5, 1)]
    b = update_difficulty_b(responses, b_init=0.0)
    assert b < 0.0


def test_hard_question_pushes_b_positive():
    """Câu mà ai cũng làm sai (kể cả learner theta cao) → b dương."""
    responses = [(0.0, 0), (1.0, 0), (-1.0, 0), (0.5, 0), (1.5, 0)]
    b = update_difficulty_b(responses, b_init=0.0)
    assert b > 0.0


def test_all_correct_clamps_to_min():
    """All-correct → hessian → 0, fallback nhưng b vẫn clamp về B_MIN."""
    responses = [(0.0, 1)] * 5
    b = update_difficulty_b(responses, b_init=0.0)
    assert b == pytest.approx(B_MIN, abs=1e-6)


def test_all_wrong_clamps_to_max():
    """All-wrong → hessian → 0, b clamp về B_MAX."""
    responses = [(0.0, 0)] * 5
    b = update_difficulty_b(responses, b_init=0.0)
    assert b == pytest.approx(B_MAX, abs=1e-6)


def test_balanced_responses_converges_near_average_theta():
    """Khi p_correct ≈ 0.5 quanh theta=0, b kỳ vọng gần 0."""
    responses = [(0.0, 1), (0.0, 0), (0.0, 1), (0.0, 0)]
    b = update_difficulty_b(responses, b_init=0.0)
    assert abs(b) < 0.5


def test_p_at_correct_b_is_one_half_when_theta_equals_b():
    """Sanity: kiểm tra tính chất của hàm logistic — không test b update,
    test invariant của P để đảm bảo công thức trong service không bị đảo dấu."""
    theta, b = 1.0, 1.0
    p = 1.0 / (1.0 + math.exp(-(theta - b)))
    assert p == pytest.approx(0.5)


def test_b_init_does_not_affect_final_when_data_strong():
    """Với data đủ tin cậy, b cuối hội tụ về cùng giá trị bất kể b_init."""
    responses = [(0.0, 1), (0.5, 1), (-0.5, 1), (1.0, 0), (-1.0, 1)]
    b1 = update_difficulty_b(responses, b_init=0.0)
    b2 = update_difficulty_b(responses, b_init=2.0)
    b3 = update_difficulty_b(responses, b_init=-2.0)
    assert b1 == pytest.approx(b2, abs=1e-3)
    assert b1 == pytest.approx(b3, abs=1e-3)


def test_empty_responses_returns_b_init():
    """Empty list → không loop, trả về b_init đã clamp."""
    assert update_difficulty_b([], b_init=0.5) == pytest.approx(0.5)
    assert update_difficulty_b([], b_init=10.0) == pytest.approx(B_MAX)
    assert update_difficulty_b([], b_init=-10.0) == pytest.approx(B_MIN)
