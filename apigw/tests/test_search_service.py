"""
Tests for search_service: model version selection, embedding reuse,
concurrent creation, independent brick edits, semantic search, and access control.
"""

import hashlib
from unittest.mock import MagicMock, patch

import numpy as np
from sqlalchemy.exc import IntegrityError

import services.search_service as search_service
from schemas import BrickContextSearch

# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------


def _make_brick(
    id_=1,
    target_text="Hello world",
    native_text="Xin chào thế giới",
    target_lang="en",
    creator_id=1,
    embedding_id=None,
    is_private=False,
):
    b = MagicMock()
    b.id = id_
    b.target_text = target_text
    b.native_text = native_text
    b.target_lang = target_lang
    b.creator_id = creator_id
    b.embedding_id = embedding_id
    b.is_private = is_private
    b.target_audio_path = "audios/brick_1.mp3"
    return b


def _make_emb(
    id_=10,
    target_lang="en",
    model_version="sentence-transformers/all-MiniLM-L6-v2",
    source_text="Hello world Xin chào thế giới",
    embedding=None,
):
    e = MagicMock()
    e.id = id_
    e.target_lang = target_lang
    e.model_version = model_version
    e.source_text = source_text
    e.embedding = embedding or [0.1] * 384
    e.content_hash = hashlib.sha256(source_text.encode("utf-8")).digest()
    return e


# ---------------------------------------------------------------------------
# 1. Model selection
# ---------------------------------------------------------------------------


class TestModelSelection:
    def test_en_model_version(self):
        assert (
            search_service._model_version_for("en")
            == search_service._EN_MODEL_NAME
        )
        assert (
            search_service._model_version_for("en")
            == "sentence-transformers/all-MiniLM-L6-v2"
        )

    def test_ja_model_version(self):
        assert (
            search_service._model_version_for("ja")
            == search_service._JA_MODEL_NAME
        )
        assert (
            search_service._model_version_for("ja") == "cl-nagoya/ruri-v3-70m"
        )

    def test_unknown_lang_defaults_to_en(self):
        assert (
            search_service._model_version_for("es")
            == search_service._EN_MODEL_NAME
        )


# ---------------------------------------------------------------------------
# 2. Embedding reuse (same canonical text → same TextEmbedding row)
# ---------------------------------------------------------------------------


class TestEmbeddingReuse:
    def test_returns_existing_without_recomputing(self):
        emb = _make_emb()
        session = MagicMock()
        session.exec.return_value.first.return_value = emb

        with patch.object(search_service, "_embed_document") as mock_embed:
            result = search_service.get_or_create_embedding(
                session, "Hello world Xin chào thế giới", "en"
            )
            assert result is emb
            mock_embed.assert_not_called()
            session.add.assert_not_called()

    def test_creates_new_when_not_found(self):
        session = MagicMock()
        session.exec.return_value.first.return_value = None

        fake_vec = [0.05] * 384
        with patch.object(
            search_service,
            "_embed_document",
            return_value=(fake_vec, search_service._EN_MODEL_NAME),
        ):
            result = search_service.get_or_create_embedding(
                session, "New unique phrase", "en"
            )
            assert result is not None

        session.add.assert_called_once()
        session.flush.assert_called_once()

    def test_content_hash_matches_sha256(self):
        canonical = "some brick text"
        expected = hashlib.sha256(canonical.encode("utf-8")).digest()
        assert search_service._content_hash(canonical) == expected

    def test_canonical_text_format(self):
        brick = _make_brick(target_text="dog", native_text="con chó")
        assert search_service._canonical_text(brick) == "dog con chó"


# ---------------------------------------------------------------------------
# 3. Concurrent creation (IntegrityError race condition handling)
# ---------------------------------------------------------------------------


class TestConcurrentCreation:
    def test_integrity_error_retries_and_returns_existing_winner(self):
        emb = _make_emb()
        call_count = 0

        session = MagicMock()

        def fake_exec(stmt, **kw):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.first.return_value = None  # initial check misses
            else:
                result.first.return_value = (
                    emb  # winner row found after rollback
                )
            return result

        session.exec.side_effect = fake_exec
        session.flush.side_effect = IntegrityError("duplicate key", "", "")

        fake_vec = [0.1] * 384
        with patch.object(
            search_service,
            "_embed_document",
            return_value=(fake_vec, search_service._EN_MODEL_NAME),
        ):
            result = search_service.get_or_create_embedding(
                session, "concurrent text", "en"
            )

        session.rollback.assert_called_once()
        assert result is emb


# ---------------------------------------------------------------------------
# 4. Independent edits (changing target_text creates/links embedding independently)
# ---------------------------------------------------------------------------


class TestIndependentEdits:
    def test_attach_embedding_only_updates_target_brick(self):
        brick1 = _make_brick(id_=1, target_text="original", embedding_id=10)
        brick2 = _make_brick(id_=2, target_text="original", embedding_id=10)

        # Brick1 changes text to "updated"
        brick1.target_text = "updated"
        new_emb = _make_emb(id_=20, source_text="updated Xin chào thế giới")

        with patch.object(
            search_service, "get_or_create_embedding", return_value=new_emb
        ):
            session = MagicMock()
            search_service.attach_embedding(session, brick1)

        # Brick1 has the new embedding
        assert brick1.embedding_id == 20
        # Brick2 is unaffected and still references old embedding
        assert brick2.embedding_id == 10

    def test_remove_brick_embedding_nullifies_only_target_brick(self):
        brick1 = _make_brick(id_=1, embedding_id=42)
        brick2 = _make_brick(id_=2, embedding_id=42)

        session = MagicMock()
        search_service.remove_brick_embedding(session, brick1)

        assert brick1.embedding_id is None
        assert brick2.embedding_id == 42
        session.add.assert_called_once_with(brick1)


# ---------------------------------------------------------------------------
# 5. Semantic search & MMR
# ---------------------------------------------------------------------------


def _make_search_row(
    id_=1, target_text="hello", native_text="xin chào", embedding=None
):
    row = MagicMock()
    row.id = id_
    row.target_text = target_text
    row.native_text = native_text
    row.target_audio_path = "audio.mp3"
    row.is_private = False
    row.embedding = embedding or list(np.random.randn(384).astype(np.float32))
    return row


class TestSemanticSearch:
    def test_semantic_search_empty_when_no_rows(self):
        session = MagicMock()
        session.exec.return_value.all.return_value = []
        with patch.object(
            search_service, "_embed_query", return_value=[0.0] * 384
        ):
            result = search_service.search_bricks_semantic(session, "query")
        assert result == []

    def test_deduplicates_identical_target_text(self):
        session = MagicMock()
        # Two bricks with identical target_text "apple", one with "banana"
        rows = [
            _make_search_row(id_=1, target_text="apple"),
            _make_search_row(id_=2, target_text="apple"),
            _make_search_row(id_=3, target_text="banana"),
        ]
        session.exec.return_value.all.return_value = rows

        query_vec = [0.1] * 384
        with patch.object(
            search_service, "_embed_query", return_value=query_vec
        ):
            result = search_service.search_bricks_semantic(
                session, "fruit", limit=10
            )

        target_texts = [r.target_text for r in result]
        assert len(target_texts) == len(set(target_texts))
        assert len(result) == 2

    def test_respects_limit(self):
        session = MagicMock()
        rows = [
            _make_search_row(id_=i, target_text=f"brick_{i}")
            for i in range(10)
        ]
        session.exec.return_value.all.return_value = rows

        query_vec = [0.1] * 384
        with patch.object(
            search_service, "_embed_query", return_value=query_vec
        ):
            result = search_service.search_bricks_semantic(
                session, "test", limit=3
            )

        assert len(result) <= 3

    def test_returns_brick_context_search_instances(self):
        session = MagicMock()
        rows = [_make_search_row(id_=99, target_text="mountain")]
        session.exec.return_value.all.return_value = rows

        with patch.object(
            search_service, "_embed_query", return_value=[0.1] * 384
        ):
            result = search_service.search_bricks_semantic(session, "nature")

        assert len(result) == 1
        assert isinstance(result[0], BrickContextSearch)
        assert result[0].brick_id == 99


# ---------------------------------------------------------------------------
# 6. Maximal Marginal Relevance (MMR)
# ---------------------------------------------------------------------------


class TestMMR:
    def test_prefers_relevant_then_diverse(self):
        q = np.array([0.8, 0.6], dtype=np.float32)
        r1 = MagicMock()
        r1.embedding = [1.0, 0.0]  # First pick: rel = 0.8
        r2 = MagicMock()
        r2.embedding = [
            1.0,
            0.0,
        ]  # Redundant duplicate: rel = 0.8, red = 1.0 -> score = -0.1
        r3 = MagicMock()
        r3.embedding = [
            0.0,
            1.0,
        ]  # Diverse: rel = 0.6, red = 0.0 -> score = +0.3

        result = search_service._mmr(q, [r1, r2, r3], k=2, lambda_mult=0.5)
        assert result[0] is r1
        assert result[1] is r3

    def test_empty_rows(self):
        assert search_service._mmr(np.array([1.0, 0.0]), [], k=5) == []


# ---------------------------------------------------------------------------
# 7. Relevance search for learner profiles
# ---------------------------------------------------------------------------


class TestRelevantBricks:
    def test_returns_empty_when_no_bricks(self):
        session = MagicMock()
        session.exec.return_value.all.return_value = []
        result = search_service.get_relevant_bricks(session, [0.1] * 384)
        assert result == []

    def test_returns_brick_ids(self):
        session = MagicMock()
        r1 = MagicMock(id=101, embedding=[0.5] * 384)
        r2 = MagicMock(id=102, embedding=[-0.5] * 384)
        session.exec.return_value.all.return_value = [r1, r2]

        result = search_service.get_relevant_bricks(
            session, [0.5] * 384, limit=2
        )
        assert 101 in result
        assert len(result) <= 2
