import pytest

from cim_generator import CIMGenerator


class _FakeRAG:
    async def get_all_context_async(self, queries, max_chars=12000):
        return "[Source: acme_overview.txt]\nAcme Corp: $22M revenue, 40 employees."

    async def get_context_async(self, query, k=8):
        return "[Source: acme_overview.txt]\nAcme Corp: $22M revenue, 40 employees."


class _StubGateway:
    def __init__(self, canned_response: str):
        self.canned_response = canned_response
        self.calls = []

    async def generate(self, request):
        self.calls.append(request)
        return self.canned_response


@pytest.mark.asyncio
async def test_generate_section_returns_content_and_charts() -> None:
    generator = CIMGenerator(_FakeRAG(), {"llm_provider": "demo", "llm_model": "demo-stub-v1"})
    canned = (
        "Acme Corp grew revenue 22% year over year.\n"
        "```chart_data\n"
        '{"type": "bar", "title": "Revenue", "labels": ["2023", "2024"], "values": [18, 22]}\n'
        "```\n"
    )
    generator.gateway = _StubGateway(canned)

    result = await generator.generate_section("executive_summary")

    assert result["section"] == "executive_summary"
    assert "Acme Corp" in result["content"]
    assert len(result["charts"]) == 1
    assert result["charts"][0]["title"] == "Revenue"
    assert generator.gateway.calls[0].provider == "demo"


@pytest.mark.asyncio
async def test_chat_answers_using_rag_context() -> None:
    generator = CIMGenerator(_FakeRAG(), {"llm_provider": "demo", "llm_model": "demo-stub-v1"})
    generator.gateway = _StubGateway("Acme Corp had $22M in revenue last year.")

    answer = await generator.chat("What was Acme's revenue?")

    assert "22M" in answer
