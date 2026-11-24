"""Minimal polar-code core used by the README animation.
Conventions match sim/polar/construction.py: natural order, x = u * F^{(x)n}, F = [[1,0],[1,1]].
BPSK: 0 -> +1, 1 -> -1.  LLR > 0 means bit 0.
"""
import numpy as np


def bhattacharyya_bec(N, z0):
    z = np.array([z0], dtype=float)
    for _ in range(int(np.log2(N))):
        z_new = np.empty(2 * len(z))
        z_new[0::2] = 2 * z - z ** 2   # minus (worse) channel
        z_new[1::2] = z ** 2           # plus  (better) channel
        z = z_new
    return z


def design_z0(design_snr_db, R):
    return np.exp(-R * 10 ** (design_snr_db / 10))


def get_frozen_mask(N, K, design_snr_db=0.0):
    z = bhattacharyya_bec(N, design_z0(design_snr_db, K / N))
    mask = np.ones(N, dtype=bool)
    mask[np.argsort(z, kind="stable")[:K]] = False
    return mask


def encode(u):
    """u: (B, N) uint8 -> x = u * F^{(x)n}  (natural order)."""
    x = u.copy()
    B, N = x.shape
    h = 1
    while h < N:
        v = x.reshape(B, N // (2 * h), 2, h)
        v[:, :, 0, :] ^= v[:, :, 1, :]
        h *= 2
    return x


def f_minsum(a, b):
    return np.sign(a) * np.sign(b) * np.minimum(np.abs(a), np.abs(b))


def g_func(a, b, u):
    return b + (1 - 2 * u.astype(float)) * a


def sc_decode(L, frozen):
    """Batch SC decoder (min-sum f). Rate-0 / rate-1 shortcuts give results identical to plain SC.
    Returns (u_hat, x_hat)."""
    B, n = L.shape
    if frozen.all():
        z = np.zeros((B, n), dtype=np.uint8)
        return z, z
    if not frozen.any():
        x = (L < 0).astype(np.uint8)
        return encode(x), x            # F^{(x)n} is its own inverse over GF(2)
    if n == 1:
        x = (L < 0).astype(np.uint8)
        return x, x
    h = n // 2
    La, Lb = L[:, :h], L[:, h:]
    ua, va = sc_decode(f_minsum(La, Lb), frozen[:h])
    ub, vb = sc_decode(g_func(La, Lb, va), frozen[h:])
    return np.concatenate([ua, ub], 1), np.concatenate([va ^ vb, vb], 1)
