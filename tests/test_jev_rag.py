import pytest
from unittest.mock import MagicMock, patch
from typesafe_sdk import SystemOneResponse, NoulAnswer, ChoiceAnswer, Usage
from src.adapters.jev import JevAdapter, get_jev_adapter
from src.knowledge.rag_service import KnowledgeRAG
from fastapi.testclient import TestClient
from src.web.app import app

client = TestClient(app)


def test_jev_adapter_availability_and_config():
    # 1. Default without API key is unavailable
    adapter = JevAdapter(api_key="", enabled=True)
    assert adapter.is_available() is False

    # 2. Disabled explicitly
    adapter_disabled = JevAdapter(api_key="ts_test_key", enabled=False)
    assert adapter_disabled.is_available() is False

    # 3. Available when key is present and enabled
    adapter_enabled = JevAdapter(api_key="ts_test_key", enabled=True, model_name="jev-1.13")
    assert adapter_enabled.is_available() is True
    assert adapter_enabled.model_name == "jev-1.13"

    info = adapter_enabled.get_info()
    assert info["available"] is True
    assert info["model_name"] == "jev-1.13"


def test_jev_adapter_rerank_with_mock_client():
    mock_client = MagicMock()

    # Define mock response behavior based on chunk title
    def fake_system_one(state, questions, model=None):
        title = state.get("knowledge_title", "")
        if "Chính sách đổi trả" in title:
            # High relevance
            return SystemOneResponse(
                model=model or "jev-latest",
                usage=Usage(input_tokens=50, output_tokens=2),
                answers={
                    "is_relevant": NoulAnswer(type="noul", noul=0.96),
                    "relevance_level": ChoiceAnswer(
                        type="choice",
                        choice="direct",
                        confidence=0.95,
                        probabilities={"direct": 0.95, "related": 0.04, "irrelevant": 0.01}
                    )
                }
            )
        elif "Chính sách vận chuyển" in title:
            # Medium relevance
            return SystemOneResponse(
                model=model or "jev-latest",
                usage=Usage(input_tokens=50, output_tokens=2),
                answers={
                    "is_relevant": NoulAnswer(type="noul", noul=0.70),
                    "relevance_level": ChoiceAnswer(
                        type="choice",
                        choice="related",
                        confidence=0.80,
                        probabilities={"direct": 0.10, "related": 0.80, "irrelevant": 0.10}
                    )
                }
            )
        else:
            # Irrelevant
            return SystemOneResponse(
                model=model or "jev-latest",
                usage=Usage(input_tokens=50, output_tokens=2),
                answers={
                    "is_relevant": NoulAnswer(type="noul", noul=0.10),
                    "relevance_level": ChoiceAnswer(
                        type="choice",
                        choice="irrelevant",
                        confidence=0.98,
                        probabilities={"direct": 0.01, "related": 0.01, "irrelevant": 0.98}
                    )
                }
            )

    mock_client.system_one.side_effect = fake_system_one

    adapter = JevAdapter(enabled=True, client=mock_client)
    assert adapter.is_available() is True

    candidate_chunks = [
        {
            "id": "c1",
            "title": "Chính sách vận chuyển",
            "content": "Giao hàng toàn quốc từ 2-4 ngày.",
            "score": 0.75  # high initial vector score
        },
        {
            "id": "c2",
            "title": "Chính sách đổi trả bảo hành",
            "content": "Bảo hành làm sáng trọn đời, đổi mới trong 7 ngày nếu lỗi sản xuất.",
            "score": 0.60  # lower initial vector score
        },
        {
            "id": "c3",
            "title": "Giới thiệu thương hiệu",
            "content": "Viễn Chí Bảo thành lập từ năm 2015.",
            "score": 0.55
        }
    ]

    reranked = adapter.rerank(
        query="em muốn đổi sản phẩm trong bao lâu ạ",
        chunks=candidate_chunks,
        top_k=2,
        min_score=0.35
    )

    assert len(reranked) == 2
    # Chunk 2 (đổi trả) should be ranked #1 by Jev decision despite lower vector score
    assert reranked[0]["id"] == "c2"
    assert reranked[0]["jev_evaluated"] is True
    assert reranked[0]["jev_choice"] == "direct"
    assert reranked[0]["jev_score"] >= 0.9

    # Chunk 3 (irrelevant) should be filtered out
    ids = [c["id"] for c in reranked]
    assert "c3" not in ids


def test_jev_adapter_gating_abstain_not_in_docs():
    """Verifies Jev + RAG Gating architecture: when all candidates are irrelevant, Jev abstains."""
    mock_client = MagicMock()
    mock_client.system_one.return_value = SystemOneResponse(
        model="jev-latest",
        usage=Usage(input_tokens=40, output_tokens=2),
        answers={
            "is_relevant": NoulAnswer(type="noul", noul=0.08),
            "relevance_level": ChoiceAnswer(
                type="choice",
                choice="irrelevant",
                confidence=0.99,
                probabilities={"direct": 0.0, "related": 0.01, "irrelevant": 0.99}
            )
        }
    )

    adapter = JevAdapter(enabled=True, client=mock_client)
    candidate_chunks = [
        {"id": "c1", "title": "Chính sách đổi trả", "content": "Đổi trả trong 7 ngày", "score": 0.40},
        {"id": "c2", "title": "Bảo hành bạc", "content": "Bảo hành làm sáng trọn đời", "score": 0.38}
    ]

    # Query is completely out of domain / not in docs
    reranked = adapter.rerank(query="shop có bán điện thoại iPhone không", chunks=candidate_chunks, top_k=2)
    # Jev Gating must abstain (return empty list) rather than injecting irrelevant documents into LLM
    assert reranked == []


def test_jev_adapter_graceful_error_fallback():
    mock_client = MagicMock()
    mock_client.system_one.side_effect = RuntimeError("TypeSafe API connection timeout")

    adapter = JevAdapter(enabled=True, client=mock_client)
    candidate_chunks = [
        {"id": "c1", "title": "Bảo hành", "content": "Bảo hành trọn đời", "score": 0.8},
        {"id": "c2", "title": "Vận chuyển", "content": "Ship hỏa tốc", "score": 0.7}
    ]

    # Should not raise exception
    reranked = adapter.rerank(query="ship bao lâu", chunks=candidate_chunks, top_k=2)
    assert len(reranked) == 2
    assert reranked[0]["id"] == "c1"


def test_jev_adapter_needs_knowledge_and_grounding():
    mock_client = MagicMock()
    mock_client.system_one.return_value = SystemOneResponse(
        model="jev-latest",
        usage=Usage(input_tokens=20, output_tokens=1),
        answers={
            "needs_knowledge": NoulAnswer(type="noul", noul=0.88),
            "is_grounded": NoulAnswer(type="noul", noul=0.94)
        }
    )

    adapter = JevAdapter(enabled=True, client=mock_client)
    res_need = adapter.needs_knowledge("nhẫn này bao nhiêu tiền")
    assert res_need["needs_knowledge"] is True
    assert res_need["probability"] == 0.88

    res_ground = adapter.verify_grounding(
        query="nhẫn này giá bao nhiêu",
        answer="Dạ nhẫn Bạc Thái có giá 680.000đ ạ.",
        context="Nhẫn Bạc Thái: giá 680.000đ"
    )
    assert res_ground["is_grounded"] is True
    assert res_ground["probability"] == 0.94


def test_knowledge_rag_search_with_jev(tmp_path):
    mock_client = MagicMock()
    mock_client.system_one.return_value = SystemOneResponse(
        model="jev-latest",
        usage=Usage(input_tokens=30, output_tokens=1),
        answers={
            "is_relevant": NoulAnswer(type="noul", noul=0.91),
            "relevance_level": ChoiceAnswer(type="choice", choice="direct", confidence=0.92, probabilities={"direct": 0.92})
        }
    )
    mock_jev = JevAdapter(enabled=True, client=mock_client, model_name="jev-latest")

    rag = KnowledgeRAG(jev_adapter=mock_jev)
    # Mock embedding adapter to return dummy vectors
    rag.embedding_adapter = MagicMock()
    rag.embedding_adapter.is_available.return_value = True
    rag.embedding_adapter.model_name = "test-model"
    rag.embedding_adapter.embed_query.return_value = [0.1] * 10

    # Mock vector_store.search
    rag.vector_store.search = MagicMock(return_value=[
        {"id": "doc1", "title": "Bảo hành bạc", "content": "Bảo hành làm sáng trọn đời", "score": 0.72},
        {"id": "doc2", "title": "Đổi trả 7 ngày", "content": "Đổi trả lỗi nhà sản xuất", "score": 0.65}
    ])
    rag._is_initialized = True

    results = rag.search(query="chính sách bảo hành", top_k=2, use_jev=True)
    assert len(results) == 2
    assert results[0]["jev_evaluated"] is True
    assert results[0]["jev_score"] >= 0.9

    stats = rag.get_stats()
    assert stats["jev_available"] is True
    assert stats["jev_model"] in ("jev-latest", "typesafe/jev")


def test_api_rag_search_endpoint_with_jev():
    with patch("src.knowledge.rag_service.get_rag_service") as mock_get_rag:
        mock_rag = MagicMock()
        mock_rag.search.return_value = [
            {
                "id": "c1",
                "title": "Chính sách đổi hàng",
                "content": "Đổi trong 7 ngày",
                "score": 0.88,
                "jev_score": 0.92,
                "jev_evaluated": True
            }
        ]
        mock_rag.jev_adapter.is_available.return_value = True
        mock_get_rag.return_value = mock_rag

        resp = client.post(
            "/api/rag/search",
            json={"query": "chính sách đổi hàng", "top_k": 3, "use_jev": True}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["use_jev"] is True
        assert data["jev_available"] is True
        assert data["results"][0]["jev_evaluated"] is True


def test_rag_chunker_includes_sales_standards_and_new_rules():
    from src.knowledge.chunker import KnowledgeChunker
    chunker = KnowledgeChunker()
    all_chunks = chunker.chunk_all()
    chunk_ids = {c.id for c in all_chunks}
    titles = [c.title for c in all_chunks]

    # 1. Verify Sales Team Test Standards from brand_voice are chunked
    sales_standards = [c for c in all_chunks if "Sales Team Test Standards" in c.title or "Custom Orders" in c.title or "Ring Sizing" in c.title or "Bạc Có Bị Đen" in c.title]
    assert len(sales_standards) > 0

    # 2. Verify new specialized rules are chunked with Trigger Keywords
    gold_rule = next((c for c in all_chunks if "meta_ask_gold_material_any" in c.id or "tiktok_ask_gold_material_any" in c.id), None)
    assert gold_rule is not None
    assert "Trigger Keywords:" in gold_rule.content
    assert "gold" in gold_rule.content.lower()

    # 3. Verify Edge Case chunks have Triggers, DO, DO NOT, and Keywords
    scam_ec = next((c for c in all_chunks if "meta_edge_scam_legitimacy_inquiry" in c.id), None)
    assert scam_ec is not None
    assert "Trigger:" in scam_ec.content
    assert "Instructions (DO):" in scam_ec.content
    assert "Trigger Keywords:" in scam_ec.content
    assert "Huy K" in scam_ec.content

    # 4. Verify new rules for unidentified product, bank qr, and video reality are chunked
    unidentified_rule = next((c for c in all_chunks if "meta_ask_unidentified_product_any" in c.id or "tiktok_ask_unidentified_product_any" in c.id), None)
    assert unidentified_rule is not None
    assert "Moissanite" in unidentified_rule.content

    bank_qr_rule = next((c for c in all_chunks if "meta_ask_bank_qr_payment_any" in c.id or "tiktok_ask_bank_qr_payment_any" in c.id), None)
    assert bank_qr_rule is not None
    assert "PayPal" in bank_qr_rule.content

    video_reality_ec = next((c for c in all_chunks if "meta_edge_video_reality_inquiry" in c.id or "tiktok_edge_video_reality_inquiry" in c.id), None)
    assert video_reality_ec is not None
    assert "spotlight" in video_reality_ec.content.lower() or "lighting" in video_reality_ec.content.lower()


def test_jev_adapter_circuit_breaker_tripping():
    import time
    adapter = JevAdapter(
        api_key="ts_test_key",
        enabled=True,
        base_url="https://dead-tunnel-url-that-does-not-exist.trycloudflare.com",
        timeout=0.2
    )
    assert adapter.is_available() is True

    # 1. First error increments consecutive failures
    res1 = adapter.evaluate_chunk("test query", {"title": "Doc 1", "content": "Content 1", "score": 0.5})
    assert res1["evaluated"] is False
    assert adapter._consecutive_failures == 1
    assert adapter.is_available() is True

    # 2. Second error trips circuit breaker
    res2 = adapter.evaluate_chunk("test query", {"title": "Doc 2", "content": "Content 2", "score": 0.5})
    assert res2["evaluated"] is False
    assert adapter._consecutive_failures == 2
    assert adapter._circuit_open_until > time.time()
    # is_available must now return False in 0ms!
    assert adapter.is_available() is False

    # 3. Rerank bypasses Jev immediately when circuit is open
    t0 = time.time()
    chunks = [{"title": "Doc A", "score": 0.8}, {"title": "Doc B", "score": 0.7}]
    reranked = adapter.rerank("test query", chunks, top_k=2)
    elapsed = time.time() - t0
    assert len(reranked) == 2
    assert elapsed < 0.05  # bypassed in milliseconds!
