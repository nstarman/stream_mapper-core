"""Core feature."""

from __future__ import annotations

# STDLIB
from collections.abc import Iterable, Mapping
from dataclasses import replace
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeVar, cast, overload

# LOCAL
from stream_ml.core.prior.bounds import NoBounds, PriorBounds
from stream_ml.core.typing import Array
from stream_ml.core.utils.frozen_dict import FrozenDict
from stream_ml.core.utils.sentinel import MISSING, Sentinel

if TYPE_CHECKING:
    # LOCAL
    from stream_ml.core.params.names import ParamNames

    Self = TypeVar("Self", bound="ParamBounds[Array]")  # type: ignore[valid-type]

__all__: list[str] = []


#####################################################################


class ParamBounds(
    FrozenDict[str, PriorBounds[Array] | FrozenDict[str, PriorBounds[Array]]]
):
    """A frozen (hashable) dictionary of parameters."""

    def __init__(self, m: Any = (), /, **kwargs: Any) -> None:
        # Initialize, with validation.
        # TODO: not cast to dict if already a ParamBounds
        pb: dict[str, PriorBounds[Array] | FrozenDict[str, PriorBounds[Array]]] = {}
        for k, v in dict(m, **kwargs).items():
            if not isinstance(k, str):
                msg = f"Invalid key type: {type(k)}"
                raise TypeError(msg)

            if isinstance(v, PriorBounds):
                pb[k] = v
            elif v is None:
                pb[k] = NoBounds()
            elif isinstance(v, Mapping):
                pb[k] = FrozenDict(
                    {
                        kk: (vv if isinstance(vv, PriorBounds) else NoBounds())
                        for kk, vv in v.items()
                    }
                )
            else:
                msg = f"Invalid element type: {type(v)}"
                raise TypeError(msg)

        super().__init__(pb, __unsafe_skip_copy__=True)

    @classmethod
    def from_names(
        cls, names: ParamNames, default: PriorBounds[Array]
    ) -> ParamBounds[Array]:
        """Create a new ParamBounds instance.

        Parameters
        ----------
        names : ParamNames, positional-only
            The parameter names.
        default : PriorBounds
            The default prior bounds.

        Returns
        -------
        ParamBounds
        """
        m: dict[str, PriorBounds[Array] | FrozenDict[str, PriorBounds[Array]]] = {}
        for pn in names:
            if isinstance(pn, str):  # e.g. "weight"
                m[pn] = replace(default, param_name=(pn,))
            else:  # e.g. ("phi2", ("mu", "sigma"))
                m[pn[0]] = FrozenDict(
                    {k: replace(default, param_name=(pn[0], k)) for k in pn[1]}
                )
        return cls(m)

    # =========================================================================
    # Mapping

    @overload
    def __getitem__(
        self, key: str
    ) -> PriorBounds[Array] | FrozenDict[str, PriorBounds[Array]]:
        ...

    @overload
    def __getitem__(self, key: tuple[str]) -> PriorBounds[Array]:  # Flat key
        ...

    @overload
    def __getitem__(self, key: tuple[str, str]) -> PriorBounds[Array]:  # Flat key
        ...

    def __getitem__(
        self, key: str | tuple[str] | tuple[str, str]
    ) -> PriorBounds[Array] | FrozenDict[str, PriorBounds[Array]]:
        if isinstance(key, str):  # e.g. "weight"
            value = super().__getitem__(key)
        elif len(key) == 1:  # e.g. ("weight",)
            value = super().__getitem__(key[0])
            if not isinstance(value, PriorBounds):
                raise KeyError(key)
        else:  # e.g. ("phi2", "mu")
            key = cast("tuple[str, str]", key)  # TODO: remove cast
            v = super().__getitem__(key[0])
            if not isinstance(v, FrozenDict):
                raise KeyError(key)
            value = v[key[1]]
        return value  # noqa: RET504

    @overload
    def __contains__(self, o: str, /) -> bool:
        ...

    @overload
    def __contains__(self, o: tuple[str] | tuple[str, str], /) -> bool:
        ...

    @overload
    def __contains__(self, o: object, /) -> bool:
        ...

    def __contains__(self, o: Any, /) -> bool:
        """Check if a key is in the ParamBounds instance."""
        if isinstance(o, str):
            return bool(super().__contains__(o))
        else:
            try:
                self[o]
            except KeyError:
                return False
            else:
                return True

    # =========================================================================
    # Flat

    def flatitems(
        self,
    ) -> Iterable[tuple[tuple[str] | tuple[str, str], PriorBounds[Array]]]:
        """Flattened items."""
        for name, bounds in self.items():
            if isinstance(bounds, PriorBounds):
                yield (name,), bounds
            else:
                for subname, subbounds in bounds.items():
                    yield (name, subname), subbounds

    def flatkeys(self) -> tuple[tuple[str] | tuple[str, str], ...]:
        """Flattened keys."""
        return tuple(k for k, _ in self.flatitems())

    def flatvalues(self) -> tuple[PriorBounds[Array], ...]:
        """Flattened values."""
        return tuple(v for _, v in self.flatitems())

    # =========================================================================
    # Misc

    # TODO: better method name
    def _fixup_param_names(self: Self) -> Self:
        """Set the parameter name in the prior bounds."""
        new = dict[str, PriorBounds[Array] | dict[str, PriorBounds[Array]]]()
        for k, v in self.items():
            if isinstance(v, PriorBounds):
                new[k] = replace(v, param_name=(k,))
            else:
                new[k] = {kk: replace(vv, param_name=(k, kk)) for kk, vv in v.items()}
        return type(self)(new)

    def validate(self, names: ParamNames, *, error: bool = False) -> bool | None:
        """Check that the paramter bounds are consistendt with the model."""
        if self.flatkeys() != names.flats:
            if error:
                # TODO: more informative error.
                msg = "param_bounds keys do not match param_names"
                raise ValueError(msg)
            else:
                return False

        return True


class ParamBoundsField(Generic[Array]):
    """Dataclass descriptor for parameter bounds.

    Parameters
    ----------
    default : ParamBounds or Mapping or None, optional
        The default parameter bounds, by default `None`. If `None`, there are no
        default bounds and the parameter bounds must be specified in the Model
        constructor. If not a `ParamBounds` instance, it will be converted to
        one.

    Notes
    -----
    See https://docs.python.org/3/library/dataclasses.html for more information
    on descriptor-typed fields for dataclasses.
    """

    def __init__(
        self,
        default: ParamBounds[Array]
        | Mapping[
            str, PriorBounds[Array] | None | Mapping[str, PriorBounds[Array] | None]
        ]
        | Literal[Sentinel.MISSING] = MISSING,
    ) -> None:
        self._default: ParamBounds[Array] | Literal[Sentinel.MISSING]
        self._default = ParamBounds(default) if default is not MISSING else MISSING

    def __set_name__(self, _: type, name: str) -> None:
        self._name = "_" + name

    def __get__(self, obj: object | None, _: type | None) -> ParamBounds[Array]:
        if obj is not None:
            val: ParamBounds[Array] = getattr(obj, self._name)
            return val

        default = self._default
        if default is MISSING:
            msg = f"no default value for {self._name}"
            raise AttributeError(msg)
        return default

    def __set__(self, obj: object, value: ParamBounds[Array]) -> None:
        dv: ParamBounds[Array] = ParamBounds(
            self._default if self._default is not MISSING else {}
        )
        value = ParamBounds(value)
        object.__setattr__(obj, self._name, dv | value)