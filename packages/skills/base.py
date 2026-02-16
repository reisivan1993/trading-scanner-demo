from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class BaseSkill(ABC):
    """Base class for all scanner skills."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique skill name."""
        ...

    @abstractmethod
    def analyze(self, df: pd.DataFrame, **kwargs: Any) -> Any:
        """Run skill analysis on a DataFrame with indicators."""
        ...
