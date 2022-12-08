"""Core feature."""

from __future__ import annotations

# STDLIB
from dataclasses import dataclass
from typing import TYPE_CHECKING

# THIRD-PARTY
import flax.linen as nn
import jax.numpy as xp
from jax.scipy.special import logsumexp

# LOCAL
from stream_ml.core.mixture import MixtureModelBase
from stream_ml.core.params import Params
from stream_ml.core.utils.hashdict import FrozenDictField
from stream_ml.jax._typing import Array
from stream_ml.jax.base import Model

if TYPE_CHECKING:
    # LOCAL
    from stream_ml.jax._typing import DataT

__all__: list[str] = []


@dataclass(unsafe_hash=True)
class MixtureModel(nn.Module, MixtureModelBase[Array], Model):  # type: ignore[misc]
    """Full Model.

    Parameters
    ----------
    models : Mapping[str, Model], optional postional-only
        Mapping of Models. This allows for strict ordering of the Models and
        control over the type of the models attribute.
    **more_models : Model
        Additional Models.
    """

    # Need to override this because of the type hinting
    components: FrozenDictField[str, Model] = FrozenDictField()  # type: ignore[assignment]  # noqa: E501

    def setup(self) -> None:
        """Setup ML."""
        # TODO!

    def pack_params_to_arr(self, pars: Params[Array]) -> Array:
        """Pack parameters into an array.

        Parameters
        ----------
        pars : Params
            Parameter dictionary.

        Returns
        -------
        Array
        """
        return Model.pack_params_to_arr(self, pars)

    # ===============================================================
    # Statistics

    def ln_likelihood_arr(
        self, pars: Params[Array], data: DataT, *args: Array
    ) -> Array:
        """Log likelihood.

        Just the log-sum-exp of the individual log-likelihoods.

        Parameters
        ----------
        pars : Params[Array]
            Parameters.
        data : DataT
            Data.
        args : Array
            Additional arguments.

        Returns
        -------
        Array
        """
        # Get the parameters for each model, stripping the model name,
        # and use that to evaluate the log likelihood for the model.
        liks = tuple(
            model.ln_likelihood_arr(pars.get_prefixed(name), data, *args)
            for name, model in self.components.items()
        )
        # Sum over the models, keeping the data dimension
        return logsumexp(xp.hstack(liks), axis=1)[:, None]

    def ln_prior_arr(self, pars: Params[Array]) -> Array:
        """Log prior.

        Parameters
        ----------
        pars : Params[Array]
            Parameters.

        Returns
        -------
        Array
        """
        # Get the parameters for each model, stripping the model name,
        # and use that to evaluate the log prior for the model.
        lps = tuple(
            model.ln_prior_arr(pars.get_prefixed(name))
            for name, model in self.components.items()
        )
        lp = xp.hstack(lps).sum(dim=1)[:, None]

        # Plugin for priors
        for prior in self.priors.values():
            lp += prior.logpdf(pars, lp)

        # Sum over the priors
        return lp

    # ========================================================================
    # ML

    def __call__(self, *args: Array) -> Array:
        """Forward pass.

        Parameters
        ----------
        args : Array
            Input. Only uses the first argument.

        Returns
        -------
        Array
            fraction, mean, sigma
        """
        result = xp.concatenate(
            [model(*args) for model in self.components.values()], axis=1
        )

        # Call the prior to limite the range of the parameters
        for prior in self.priors.values():
            result = prior(result, self.param_names.flats)

        return result
