"""Core feature."""

from __future__ import annotations

# STDLIB
from dataclasses import KW_ONLY, dataclass
from math import inf
from typing import TYPE_CHECKING

# THIRD-PARTY
import torch as xp

# LOCAL
from stream_ml.core.data import Data
from stream_ml.core.prior.base import PriorBase
from stream_ml.pytorch.typing import Array
from stream_ml.pytorch.utils.misc import within_bounds

if TYPE_CHECKING:
    # LOCAL
    from stream_ml.core.base import Model
    from stream_ml.core.params.core import Params

__all__: list[str] = []


@dataclass(frozen=True)
class BoundedHardThreshold(PriorBase[Array]):
    """Threshold prior.

    Parameters
    ----------
    threshold : float, optional
        The threshold, by default 0.005
    lower : float, optional
        The lower bound in the domain of the prior, by default `-inf`.
    upper : float, optional
        The upper bound in the domain of the prior, by default `inf`.
    """

    threshold: float = 0.005
    _: KW_ONLY
    coord_name: str = "phi1"
    lower: float = -inf
    upper: float = inf

    def logpdf(
        self,
        mpars: Params[Array],
        data: Data[Array],
        model: Model[Array],
        current_lnpdf: Array | None = None,
        /,
    ) -> Array | float:
        """Evaluate the logpdf.

        This log-pdf is added to the current logpdf. So if you want to set the
        logpdf to a specific value, you can uses the `current_lnpdf` to set the
        output value such that ``current_lnpdf + logpdf = <want>``.

        Parameters
        ----------
        mpars : Params[Array], positional-only
            Model parameters. Note that these are different from the ML
            parameters.
        data : Data[Array], position-only
            The data for which evaluate the prior.
        model : Model, position-only
            The model for which evaluate the prior.
        current_lnpdf : Array | None, optional position-only
            The current logpdf, by default `None`. This is useful for setting
            the additive log-pdf to a specific value.

        Returns
        -------
        Array
            The logpdf.
        """
        lnp = xp.zeros_like(mpars[("weight",)])
        lnp[
            within_bounds(data[self.coord_name], self.lower, self.upper)
            & (mpars[("weight",)] < self.threshold)
        ] = -inf
        return lnp

    def __call__(self, nn: Array, data: Data[Array], model: Model[Array], /) -> Array:
        """Evaluate the forward step in the prior.

        Parameters
        ----------
        nn : Array, position-only
            The input to evaluate the prior at.
        data : Data[Array], position-only
            The data to evaluate the prior at.
        model : `~stream_ml.core.Model`, position-only
            The model to evaluate the prior at.

        Returns
        -------
        Array
        """
        im1 = model.param_names.flat.index("weight")
        where = within_bounds(data[self.coord_name][:, 0], self.lower, self.upper)

        out = nn.clone()
        out[where, im1] = xp.threshold(nn[where, im1], self.threshold, 0)

        return out