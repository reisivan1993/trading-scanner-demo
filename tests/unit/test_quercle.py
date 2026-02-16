from __future__ import annotations

import pytest

from packages.tools.quercle import QuercleTool
from packages.tools.web_intel import WebIntelProcessor


class TestQuercleTool:
    async def test_quercle_search_parses_response(self, mocker) -> None:
        mock_resp = mocker.MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = mocker.MagicMock()
        mock_resp.json.return_value = {
            "results": [
                {"title": "AAPL beats estimates", "snippet": "Strong quarter", "sentiment": "positive"}
            ]
        }

        mock_client = mocker.AsyncMock()
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock(return_value=False)
        mock_client.get = mocker.AsyncMock(return_value=mock_resp)

        mocker.patch("packages.tools.quercle.httpx.AsyncClient", return_value=mock_client)
        mocker.patch.dict("os.environ", {"QUERCLE_API_KEY": "test_key"})

        tool = QuercleTool()
        results = await tool.search("AAPL", "market_sentiment")

        assert len(results) == 1
        assert results[0]["title"] == "AAPL beats estimates"

    async def test_quercle_search_graceful_on_error(self, mocker) -> None:
        mock_client = mocker.AsyncMock()
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock(return_value=False)
        mock_client.get = mocker.AsyncMock(side_effect=Exception("Connection refused"))

        mocker.patch("packages.tools.quercle.httpx.AsyncClient", return_value=mock_client)
        mocker.patch.dict("os.environ", {"QUERCLE_API_KEY": "test_key"})

        tool = QuercleTool()
        results = await tool.search("AAPL", "market_sentiment")

        assert results == []


class TestWebIntelProcessor:
    async def test_web_intel_positive_catalyst(self, mocker) -> None:
        tool = QuercleTool()
        mocker.patch.object(tool, "search", return_value=[
            {"title": "Analyst upgrade for AAPL", "snippet": "catalyst for growth"}
        ])

        processor = WebIntelProcessor(tool)
        modifier, notes = await processor.get_modifier("AAPL")

        assert modifier > 0
        assert any("Positive catalyst" in n for n in notes)

    async def test_web_intel_negative_sentiment(self, mocker) -> None:
        tool = QuercleTool()
        mocker.patch.object(tool, "search", return_value=[
            {"title": "AAPL downgrade by analyst", "snippet": "concerns about growth"}
        ])

        processor = WebIntelProcessor(tool)
        modifier, notes = await processor.get_modifier("AAPL")

        assert modifier < 0

    async def test_web_intel_earnings_penalty(self, mocker) -> None:
        tool = QuercleTool()
        mocker.patch.object(tool, "search", return_value=[
            {"title": "AAPL earnings report next week", "snippet": "EPS expectations"}
        ])

        processor = WebIntelProcessor(tool)
        modifier, notes = await processor.get_modifier("AAPL")

        assert modifier == -0.10

    async def test_web_intel_graceful_degradation(self, mocker) -> None:
        tool = QuercleTool()
        mocker.patch.object(tool, "search", side_effect=Exception("API down"))

        processor = WebIntelProcessor(tool)
        modifier, notes = await processor.get_modifier("AAPL")

        assert modifier == 0.0
        assert "unavailable" in notes[0].lower()

    async def test_web_intel_modifier_capped(self, mocker) -> None:
        tool = QuercleTool()
        mocker.patch.object(tool, "search", return_value=[
            {"title": "SEC investigation into downgrade", "snippet": "earnings miss warning recall lawsuit short interest heavily shorted"}
        ])

        processor = WebIntelProcessor(tool)
        modifier, notes = await processor.get_modifier("AAPL")

        assert modifier >= -0.30
        assert modifier <= 0.10
