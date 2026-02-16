from __future__ import annotations

import asyncio
import logging
import sys

import structlog
from dotenv import load_dotenv

from packages.core.config import load_config
from packages.core.orchestrator import ScanOrchestrator
from packages.policy.engine import PolicyEngine
from packages.policy.loader import load_policies
from packages.providers.factory import get_provider


def setup_logging(level: str = "INFO", structured: bool = True) -> None:
    """Configure structured logging."""
    if structured:
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.dev.ConsoleRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
        )
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO))


async def run_scan() -> None:
    """Run the full scanning pipeline."""
    load_dotenv()

    config = load_config("config.yml")
    setup_logging(config.logging.level, config.logging.structured)

    logger = logging.getLogger(__name__)
    logger.info("Starting Cold Trader Scanner")

    policy = load_policies(config)
    provider = get_provider(config)
    engine = PolicyEngine()

    orchestrator = ScanOrchestrator(
        config=config,
        provider=provider,
        policy=policy,
        policy_engine=engine,
    )

    result = await orchestrator.run()

    logger.info(
        "Scan complete: %d tickers scanned, %d setups found, %d passed risk gate",
        result.meta.tickers_scanned,
        result.meta.setups_found,
        result.meta.setups_passed_risk,
    )

    if result.cash_is_position:
        logger.info("CASH IS A POSITION - No setups passed all filters")
    else:
        for r in result.results:
            logger.info(
                "#%d %s %s | Entry: %s | Stop: %s | T1: %s | RR: %.1f | Score: %.1f",
                r.rank,
                r.symbol,
                r.direction.upper(),
                r.setup.entry,
                r.setup.stop,
                r.setup.target_1,
                r.setup.rr_ratio,
                r.score.total,
            )


def main() -> None:
    asyncio.run(run_scan())


if __name__ == "__main__":
    main()
