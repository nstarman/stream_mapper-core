"""Core feature."""

from __future__ import annotations

# STDLIB
from abc import abstractmethod
from collections.abc import Iterator
from dataclasses import KW_ONLY, dataclass
from math import inf
from typing import TYPE_CHECKING, Any, TypeVar

# LOCAL
from stream_ml.core.data import Data
from stream_ml.core.params.names import FlatParamName
from stream_ml.core.prior.base import PriorBase
from stream_ml.core.typing import Array, BoundsT

if TYPE_CHECKING:
    # LOCAL
    from stream_ml.core.base import Model
    from stream_ml.core.params.core import Params

__all__: list[str] = []


Self = TypeVar("Self", bound="PriorBounds")  # type: ignore[type-arg]


@dataclass(frozen=True)
class PriorBounds(PriorBase[Array]):
    """Base class for prior bounds."""

    lower: float
    upper: float
    _: KW_ONLY
    param_name: FlatParamName | None = None

    @abstractmethod
    def logpdf(
        self,
        mpars: Params[Array],
        data: Data[Array],
        model: Model[Array],
        current_lnpdf: Array | None = None,
        /,
    ) -> Array | float:
        """Evaluate the logpdf."""
        ...

    @abstractmethod
    def __call__(self, nn: Array, data: Data[Array], model: Model[Array], /) -> Array:
        """Evaluate the forward step in the prior."""
        ...

    # =========================================================================

    @classmethod
    def from_tuple(
        cls: type[Self],
        t: BoundsT,
        /,
        param_name: FlatParamName | None = None,
    ) -> Self:
        """Create from tuple."""
        return cls(*t, param_name=param_name)

    def as_tuple(self) -> BoundsT:
        """Get as tuple."""
        return self.lower, self.upper

    @property
    def bounds(self) -> BoundsT:
        """Get the bounds."""
        return self.as_tuple()

    # =========================================================================

    def __iter__(self) -> Iterator[float]:
        """Iterate over the bounds."""
        yield from self.bounds


################################################################################


@dataclass(frozen=True)
class NoBounds(PriorBounds[Any]):
    """No bounds."""

    lower: float = -inf
    upper: float = inf

    def __post_init__(self, /) -> None:
        """Post-init."""
        if self.lower != -inf or self.upper != inf:
            msg = "lower and upper must be -inf and inf"
            raise ValueError(msg)

    def logpdf(
        self,
        mpars: Params[Array],
        data: Data[Array],
        model: Model[Array],
        current_lnpdf: Array | None = None,
        /,
    ) -> Array | float:
        """Evaluate the logpdf."""
        if self.param_name is None:
            msg = "need to set param_name"
            raise ValueError(msg)
        return 0

    def __call__(self, nn: Array, data: Data[Array], model: Model[Array], /) -> Array:
        """Evaluate the forward step in the prior."""
        return nn