from collections import namedtuple
from typing import Optional
from typing import Tuple
from typing import Union
from typing import cast

import torch
from torch import Tensor

from pfhedge._utils.str import _addindent
from pfhedge._utils.typing import TensorOrScalar

from ._utils import cast_state
from .cir import generate_cir


class HestonTuple(namedtuple("HestonTuple", ["spot", "variance"])):

    __module__ = "pfhedge.stochastic"

    def __repr__(self) -> str:
        items_str_list = []
        for field, tensor in self._asdict().items():
            items_str_list.append(field + "=\n" + str(tensor))
        items_str = _addindent("\n".join(items_str_list), 2)
        return self.__class__.__name__ + "(\n" + items_str + "\n)"

    @property
    def volatility(self) -> Tensor:
        return self.variance.clamp(min=0.0).sqrt()


def generate_heston(
    n_paths: int,
    n_steps: int,
    init_state: Optional[Tuple[TensorOrScalar, ...]] = None,
    kappa: float = 1.0,
    theta: float = 0.04,
    sigma: float = 0.2,
    rho: float = -0.7,
    dt: float = 1 / 250,
    dtype: Optional[torch.dtype] = None,
    device: Optional[torch.device] = None,
) -> HestonTuple:
    """Returns time series following Heston model.

    The time evolution of the process is given by:

    .. math::

        dS(t) = S(t) \\sqrt{V(t)} dW_1(t) \\,, \\\\
        dV(t) = \\kappa (\\theta - V(t)) dt + \\sigma \\sqrt{V(t)} dW_2(t) \\,.

    The correlation between :math:`dW_1` and :math:`dW_2` is :math:`\\rho`.

    Time-series is generated by Andersen's QE-M method (See Reference for details).

    References:
        - Heston, S.L., 1993. A closed-form solution for options with stochastic volatility
          with applications to bond and currency options.
          The review of financial studies, 6(2), pp.327-343.
        - Andersen, Leif B.G., Efficient Simulation of the Heston Stochastic
          Volatility Model (January 23, 2007). Available at SSRN:
          https://ssrn.com/abstract=946405 or http://dx.doi.org/10.2139/ssrn.946404

    Args:
        n_paths (int): The number of simulated paths.
        n_steps (int): The number of time steps.
        init_state (tuple[torch.Tensor | float], optional): The initial state of
            the time series.
            This is specified by a tuple :math:`(S(0), V(0))`.
            If ``None`` (default), it uses :math:`(1.0, \\theta)`.
        kappa (float, default=1.0): The parameter :math:`\\kappa`.
        theta (float, default=0.04): The parameter :math:`\\theta`.
        sigma (float, default=2.0): The parameter :math:`\\sigma`.
        rho (float, default=-0.7): The parameter :math:`\\rho`.
        dt (float, default=1/250): The intervals of the time steps.
        dtype (torch.dtype, optional): The desired data type of returned tensor.
            Default: If ``None``, uses a global default
            (see :func:`torch.set_default_tensor_type()`).
        device (torch.device, optional): The desired device of returned tensor.
            Default: If ``None``, uses the current device for the default tensor type
            (see :func:`torch.set_default_tensor_type()`).
            ``device`` will be the CPU for CPU tensor types and the current CUDA device
            for CUDA tensor types.

    Shape:
        - spot: :math:`(N, T)` where
          :math:`N` is the number of paths and
          :math:`T` is the number of time steps.
        - variance: :math:`(N, T)`.

    Returns:
        (torch.Tensor, torch.Tensor): A namedtuple ``(spot, variance)``.

    Examples:
        >>> from pfhedge.stochastic import generate_heston
        ...
        >>> _ = torch.manual_seed(42)
        >>> spot, variance = generate_heston(2, 5)
        >>> spot
        tensor([[1.0000, 0.9941, 0.9905, 0.9846, 0.9706],
                [1.0000, 1.0031, 0.9800, 0.9785, 0.9735]])
        >>> variance
        tensor([[0.0400, 0.0408, 0.0411, 0.0417, 0.0422],
                [0.0400, 0.0395, 0.0452, 0.0434, 0.0446]])
    """
    if init_state is None:
        init_state = (1.0, theta)

    init_state = cast_state(init_state, dtype=dtype, device=device)

    GAMMA1 = 0.5
    GAMMA2 = 0.5

    variance = generate_cir(
        n_paths=n_paths,
        n_steps=n_steps,
        init_state=init_state[1:],
        kappa=kappa,
        theta=theta,
        sigma=sigma,
        dt=dt,
        dtype=dtype,
        device=device,
    )

    log_spot = torch.empty_like(variance)
    log_spot[:, 0] = init_state[0].log()
    randn = torch.randn_like(variance)

    for i_step in range(n_steps - 1):
        # Compute log S(t + 1): Eq(33)
        k0 = -rho * kappa * theta * dt / sigma
        k1 = GAMMA1 * dt * (kappa * rho / sigma - 0.5) - rho / sigma
        k2 = GAMMA2 * dt * (kappa * rho / sigma - 0.5) + rho / sigma
        k3 = GAMMA1 * dt * (1 - rho ** 2)
        k4 = GAMMA2 * dt * (1 - rho ** 2)
        v0 = variance[:, i_step]
        v1 = variance[:, i_step + 1]
        log_spot[:, i_step + 1] = (
            log_spot[:, i_step]
            + k0
            + k1 * v0
            + k2 * v1
            + (k3 * v0 + k4 * v1).sqrt() * randn[:, i_step]
        )

    return HestonTuple(log_spot.exp(), variance)
