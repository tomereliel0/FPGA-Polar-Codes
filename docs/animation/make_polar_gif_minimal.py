"""Minimal-text README animation: titles only, the rest is motion.

Scenes: title -> noise -> polarization tree -> encoding (signal pulses) -> SC decoding (LLR bars)
        -> BER waterfall -> outro.
Usage (from docs/animation):
        python make_polar_gif_minimal.py ber_design2.0.json ../images/polar-codes-minimal.gif
"""
import json, os, subprocess, sys, tempfile
from math import erfc, sqrt
from multiprocessing import Pool

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle

from make_polar_gif import (BG, PANEL, FG, MUTED, GRID, GREEN, BLUE, AMBER, NAVY, MID, ERR, CMAP, FPS,
                            ease, new_canvas, style_axes, bhattacharyya_bec, interp_curve,
                            FROZEN8, U8, X8, STAGES, DEMO_L, DEMO_FLIPS, DEMO_EV)
from make_polar_gif_simple import bit_tile, SLATE

RES = None
N_SCENES = 5


def chrome(ax, step, title, alpha=1.0):
    """Big title + progress dots — the only text on most frames."""
    ax.text(4, 49.5, title, fontsize=20, color=FG, weight="bold", va="center", alpha=alpha)
    for i in range(N_SCENES):
        x = 82 + i * 3.2
        if i == step:
            ax.add_patch(FancyBboxPatch((x - 1.6, 48.8), 3.2 + 1.2, 1.4, boxstyle="round,pad=0,rounding_size=0.7",
                                        fc=BLUE, ec="none"))
        else:
            ax.add_patch(Circle((x + (1.2 if i > step else 0), 49.5), 0.7, color=BLUE if i < step else GRID))


def xor_glyph(ax, x, y, r=1.0, color=MUTED, lw=1.1, z=4):
    ax.add_patch(Circle((x, y), r, fc="white", ec=color, lw=lw, zorder=z))
    ax.plot([x - r * 0.65, x + r * 0.65], [y, y], color=color, lw=lw, zorder=z + 1)
    ax.plot([x, x], [y - r * 0.65, y + r * 0.65], color=color, lw=lw, zorder=z + 1)


def glow(ax, x, y, r=0.7, color=AMBER, z=8):
    ax.add_patch(Circle((x, y), r * 2.0, color=color, alpha=0.18, lw=0, zorder=z))
    ax.add_patch(Circle((x, y), r, color=color, lw=0, zorder=z + 1))


# ----------------------------------------------------------------------------- title / outro
def motif(ax, a, t):
    """16 dots drifting from neutral grey to their polarized colours."""
    caps = 1 - bhattacharyya_bec(16, 0.5)
    for i, v in enumerate(caps):
        vv = 0.5 + (v - 0.5) * ease(t)
        ax.add_patch(Circle((26 + i * 3.2, 16 + (vv - 0.5) * 6 * ease(t)), 0.95, color=CMAP(vv), alpha=a))


def scene_title(ax, k, K, outro=False):
    a = ease(k / 6)
    ax.text(50, 34, "Polar Codes" if not outro else "Polar Codes  →  FPGA", fontsize=34 if not outro else 30,
            color=FG, weight="bold", ha="center", va="center", alpha=a)
    motif(ax, a, k / (K * 0.8) if not outro else 1.0)


# ----------------------------------------------------------------------------- 1 noise
NOISE_FRAMES = 50
BAND_X0, BAND_X1 = 36.0, 64.0
STREAM_Y = 25.0
rng0 = np.random.default_rng(7)
STREAM_BITS = rng0.integers(0, 2, 40)
STREAM_FLIP = rng0.random(40) < 0.22


def scene_noise(fig, ax, k, K):
    chrome(ax, 0, "Noise")
    # animated noise band
    xs = np.linspace(BAND_X0, BAND_X1, 160)
    env = np.sin(np.pi * (xs - BAND_X0) / (BAND_X1 - BAND_X0)) ** 0.6
    r = np.random.default_rng(k)
    for j in range(5):
        y = STREAM_Y + env * (2.2 * np.sin(xs * (0.9 + 0.25 * j) + k * 0.5 + j) + r.normal(0, 0.9, xs.size))
        ax.plot(xs, y, color=SLATE, lw=0.8, alpha=0.35)
    # stream of bits
    speed, spacing = 1.45, 4.6
    for i in range(len(STREAM_BITS)):
        x = 46 + k * speed - i * spacing
        if x < -3 or x > 103:
            continue
        b = int(STREAM_BITS[i])
        inside = BAND_X0 < x < BAND_X1
        jit = 0.0
        if inside:
            e = np.sin(np.pi * (x - BAND_X0) / (BAND_X1 - BAND_X0))
            jit = e * 2.2 * np.sin(i * 3.1 + k * 1.3)
        if x >= (BAND_X0 + BAND_X1) / 2 and STREAM_FLIP[i]:
            bit_tile(ax, x, STREAM_Y + jit, b ^ 1, kind="err", w=3.2, h=3.2, fs=9, z=6)
        else:
            bit_tile(ax, x, STREAM_Y + jit, b, w=3.2, h=3.2, fs=9, z=6)


# ----------------------------------------------------------------------------- 2 polarization tree
LEVELS = 6
TREE_TOP, TREE_BOT = 40.0, 14.0
LVL_FR, BAR_FR, POL_HOLD = 8, 14, 16
POL_FRAMES = 6 + LEVELS * LVL_FR + BAR_FR + POL_HOLD
TCAPS = [1 - bhattacharyya_bec(2 ** l, 0.5) for l in range(LEVELS + 1)]


def tnode(l, j):
    return 10 + (j + 0.5) * 80 / 2 ** l, TREE_TOP - l * (TREE_TOP - TREE_BOT) / LEVELS


def scene_polar(fig, ax, k, K):
    chrome(ax, 1, "Polarization")
    kk = k - 6
    lv = LEVELS if kk >= LEVELS * LVL_FR else max(0, kk // LVL_FR)
    t = 1.0 if kk >= LEVELS * LVL_FR else (ease((kk % LVL_FR) / (LVL_FR - 2)) if kk >= 0 else 0.0)
    rad = lambda l: max(0.35, 1.5 - 0.19 * l)
    # finished levels
    for l in range(0, min(lv, LEVELS) + 1):
        grow = 1.0 if l < lv or kk >= LEVELS * LVL_FR else (t if l > 0 else 1.0)
        if l == lv and l > 0 and kk < LEVELS * LVL_FR:
            grow = t
        for j in range(2 ** l):
            x, y = tnode(l, j)
            if l > 0:
                px, py = tnode(l - 1, j // 2)
                cx, cy = px + (x - px) * grow, py + (y - py) * grow
                ax.plot([px, cx], [py, cy], color=GRID, lw=0.8, zorder=1)
                v = TCAPS[l - 1][j // 2] + (TCAPS[l][j] - TCAPS[l - 1][j // 2]) * grow
            else:
                cx, cy, v = x, y, TCAPS[0][0]
            ax.add_patch(Circle((cx, cy), rad(l), color=CMAP(v), zorder=3))
    # bars under the last level
    if kk >= LEVELS * LVL_FR:
        bt = ease((kk - LEVELS * LVL_FR) / BAR_FR)
        for j, v in enumerate(TCAPS[LEVELS]):
            x, _ = tnode(LEVELS, j)
            h = 9.5 * v * bt
            if h > 0.05:
                ax.add_patch(FancyBboxPatch((x - 0.5, 1.5), 1.0, h, boxstyle="round,pad=0,rounding_size=0.3",
                                            fc=CMAP(v), ec="none"))


# ----------------------------------------------------------------------------- 3 encoding
COLS = [16, 34, 52, 70]
ROWS = [37.0 - i * 4.4 for i in range(8)]
E_IN, E_ST, E_OUT, E_HOLD = 12, 15, 12, 12
ENC_FRAMES = E_IN + 3 * E_ST + E_OUT + E_HOLD


def enc_node(ax, x, y, b, frozen=False, alpha=1.0, r=1.35):
    if frozen:
        ax.add_patch(Circle((x, y), r, fc="white", ec=SLATE, lw=1, ls="--", alpha=alpha, zorder=5))
        ax.text(x, y, "0", ha="center", va="center", fontsize=7.5, color=SLATE, alpha=alpha, zorder=6)
    else:
        ax.add_patch(Circle((x, y), r, fc=BLUE if b else "white", ec=BLUE, lw=1.1, alpha=alpha, zorder=5))
        ax.text(x, y, str(b), ha="center", va="center", fontsize=7.5, color="white" if b else NAVY,
                weight="bold", alpha=alpha, zorder=6)


def scene_encode(fig, ax, k, K):
    chrome(ax, 2, "Encoding")
    # inputs slide in from the left
    a = ease(k / E_IN)
    for i in range(8):
        x = COLS[0] - 10 * (1 - a)
        enc_node(ax, x, ROWS[i], int(U8[i]), frozen=bool(FROZEN8[i]), alpha=a)
    kk = k - E_IN
    for s, h in enumerate((1, 2, 4)):
        st = (kk - s * E_ST) / E_ST
        if st <= 0:
            continue
        c0, c1 = COLS[s], COLS[s + 1]
        xo = c0 + 0.62 * (c1 - c0)
        act = st < 1
        wcol = MID if act else GRID
        for j in range(8):
            ax.plot([c0 + 1.35, c1 - 1.35], [ROWS[j]] * 2, color=wcol, lw=1.1, zorder=1)
            if (j // h) % 2 == 0:
                ax.plot([c0 + 1.1, xo], [ROWS[j + h], ROWS[j]], color=wcol, lw=1.1, zorder=1)
                xor_glyph(ax, xo, ROWS[j], color=AMBER if act else SLATE)
        if act:
            p = ease(min(st / 0.75, 1))
            for j in range(8):
                srcb = STAGES[s][j]
                if srcb:   # pulses only carry 1s — 0s are silent
                    glow(ax, c0 + (c1 - c0) * p, ROWS[j])
                    if (j // h) % 2 == 1:    # this row also feeds the XOR above it
                        q = min(1.0, p / 0.62)
                        glow(ax, c0 + (xo - c0) * q, ROWS[j] + (ROWS[j - h] - ROWS[j]) * q)
        if st > 0.8:
            na = ease((st - 0.8) / 0.2)
            for j in range(8):
                enc_node(ax, c1, ROWS[j], int(STAGES[s + 1][j]), alpha=na)
    ot = (kk - 3 * E_ST) / E_OUT
    if ot > 0:
        for j in range(8):
            tt = ease((ot - j * 0.05) / 0.6)
            if tt > 0:
                ax.plot([COLS[3] + 1.35, COLS[3] + 1.35 + 10 * tt], [ROWS[j]] * 2, color=GRID, lw=1.1, zorder=1)
                bit_tile(ax, COLS[3] + 4 + 12 * tt, ROWS[j], int(X8[j]), w=3.0, h=3.0, fs=8.5, alpha=tt)


# ----------------------------------------------------------------------------- 4 decoding
EV = DEMO_EV          # (root "show" already stripped in make_polar_gif)
D_IN, D_EV, D_FIX, D_HOLD = 12, 3, 14, 14
DEC_FRAMES = D_IN + D_EV * len(EV) + D_FIX + D_HOLD
TX0, TW = 6.0, 88.0
LVY = [31.5, 23.0, 14.5, 6.0]
BH = 4.2
RX_Y = 39.5


def dnode(d, kidx):
    w = TW / 2 ** d
    return TX0 + (kidx + 0.5) * w, LVY[d], w - 1.4


def llr_bars(ax, cx, cy, w, L, alpha=1.0):
    n = len(L)
    slot = w / n
    bw = min(slot * 0.55, 3.2)
    for i, v in enumerate(L):
        x = cx - w / 2 + (i + 0.5) * slot
        hgt = 1.9 * min(abs(v) / 4.5, 1.0) ** 0.8
        if v >= 0:
            ax.add_patch(plt.Rectangle((x - bw / 2, cy), bw, hgt, color=MID, alpha=alpha, lw=0, zorder=4))
        else:
            ax.add_patch(plt.Rectangle((x - bw / 2, cy - hgt), bw, hgt, color=NAVY, alpha=alpha, lw=0, zorder=4))
    ax.plot([cx - w / 2 + 0.4, cx + w / 2 - 0.4], [cy, cy], color=GRID, lw=0.6, alpha=alpha, zorder=3)


def scene_decode(fig, ax, k, K):
    chrome(ax, 3, "Decoding")
    a = ease(k / D_IN)
    nev = 0 if k < D_IN else min(len(EV), (k - D_IN) // D_EV + 1)
    fix_t = ease((k - D_IN - D_EV * len(EV)) / D_FIX) if k >= D_IN + D_EV * len(EV) else 0.0
    shown = {(0, 0): (DEMO_L, None)}
    leaves, flash = {}, None
    for e in EV[:nev]:
        if e[0] == "show":
            shown[(e[1], e[2])] = (e[3], e[4])
        elif e[0] == "leaf":
            leaves[(e[1], e[2])] = e[3]
    cur = EV[nev - 1] if 0 < nev and fix_t == 0 else None
    # received row (hard decisions) — the flipped ones get fixed at the end
    for i in range(8):
        x = TX0 + (i + 0.5) * TW / 8
        rx = int(DEMO_L[i] < 0)
        if i in DEMO_FLIPS:
            if fix_t < 0.5:
                bit_tile(ax, x, RX_Y, rx, kind="err", alpha=a, w=3.2, h=3.2, fs=9)
            else:
                bit_tile(ax, x, RX_Y, int(X8[i]), alpha=1.0, w=3.2, h=3.2, fs=9)
                ax.add_patch(Circle((x, RX_Y), 2.6 + 2.5 * (fix_t - 0.5), fc="none", ec=GREEN,
                                    lw=1.5, alpha=max(0, 1 - 2 * (fix_t - 0.5)), zorder=7))
        else:
            bit_tile(ax, x, RX_Y, rx, alpha=a, w=3.2, h=3.2, fs=9)
    # edges
    for (d, kidx), (L, op) in shown.items():
        if d == 0:
            continue
        px, py, _ = dnode(d - 1, kidx // 2)
        cx, cy, _ = dnode(d, kidx)
        act = cur is not None and cur[0] in ("show", "leaf") and (cur[1], cur[2]) == (d, kidx)
        ax.plot([px, cx], [py - BH / 2, cy + BH / 2], color=AMBER if act else GRID, lw=2.0 if act else 1.0, zorder=1)
        if act and cur[0] == "show":
            p = ease(((k - D_IN) % D_EV + 1) / D_EV)
            glow(ax, px + (cx - px) * p, (py - BH / 2) + ((cy + BH / 2) - (py - BH / 2)) * p, r=0.55)
    # beta flash: edge back to the parent
    if cur is not None and cur[0] == "beta" and cur[1] > 0:
        d, kidx = cur[1], cur[2]
        px, py, _ = dnode(d - 1, kidx // 2)
        cx, cy, _ = dnode(d, kidx)
        p = ease(((k - D_IN) % D_EV + 1) / D_EV)
        ax.plot([px, cx], [py - BH / 2, cy + BH / 2], color=NAVY, lw=2.0, zorder=2)
        glow(ax, cx + (px - cx) * p, (cy + BH / 2) + ((py - BH / 2) - (cy + BH / 2)) * p, r=0.55, color=NAVY)
    # boxes
    for (d, kidx), (L, op) in shown.items():
        cx, cy, w = dnode(d, kidx)
        act = cur is not None and (cur[1], cur[2]) == (d, kidx)
        ec = (NAVY if cur[0] == "beta" else AMBER) if act else GRID
        al = a if d == 0 else 1.0
        if d == 3 and (d, kidx) in leaves:
            idx = kidx
            b = leaves[(d, kidx)]
            bit_tile(ax, cx, cy, b, kind="frozen" if FROZEN8[idx] else "data", w=3.6, h=3.6, fs=9.5)
            if act:
                ax.add_patch(FancyBboxPatch((cx - 2.6, cy - 2.6), 5.2, 5.2, boxstyle="round,pad=0,rounding_size=1",
                                            fc="none", ec=AMBER, lw=2, zorder=7))
            continue
        ax.add_patch(FancyBboxPatch((cx - w / 2, cy - BH / 2), w, BH, boxstyle="round,pad=0,rounding_size=0.8",
                                    fc=PANEL, ec=ec, lw=2.0 if act else 0.9, alpha=al, zorder=2))
        llr_bars(ax, cx, cy, w, L, alpha=al)


# ----------------------------------------------------------------------------- 5 result
R_U, R_P, R_G, R_HOLD = 18, 26, 12, 20
RES_FRAMES = R_U + R_P + R_G + R_HOLD


def qf(x):
    return 0.5 * erfc(x / sqrt(2))


def scene_result(fig, ax, k, K):
    chrome(ax, 4, "Result")
    r = RES
    a1 = fig.add_axes([0.09, 0.1, 0.84, 0.68]); style_axes(a1)
    a1.set_yscale("log"); a1.set_xlim(0, 9.2); a1.set_ylim(1e-6, 1)
    a1.set_xlabel("Eb/N0 [dB]", fontsize=8); a1.set_ylabel("bit error rate", fontsize=8)
    a1.grid(color=GRID, lw=0.5, alpha=0.7)
    a1.set_facecolor("white")
    tu = ease(k / R_U)
    ex = np.linspace(0, 9.2 * tu, max(2, int(200 * tu)))
    a1.plot(ex, [qf(np.sqrt(2 * 10 ** (e / 10))) for e in ex], ls="--", color=SLATE, lw=1.6)
    tp = ease((k - R_U) / R_P) if k >= R_U else 0
    xs = np.array(r["ebn0"])
    if tp > 0:
        bx, by = interp_curve(xs, r["ber"], xs[0] + (xs[-1] - xs[0]) * tp)
        a1.plot(bx, by, "-", color=BLUE, lw=2.6)
        a1.plot(bx[-1:], by[-1:], "o", color=BLUE, ms=6)
        a1.plot(bx[-1:], by[-1:], "o", color=BLUE, ms=14, alpha=0.18)
    if k >= R_U + R_P:
        g = ease((k - R_U - R_P) / R_G)
        xu = 8.4; xp = float(np.interp(-4, np.log10(r["ber"])[::-1], xs[::-1]))
        x_end = xu - (xu - xp) * g
        a1.annotate("", xy=(x_end, 1e-4), xytext=(xu, 1e-4),
                    arrowprops=dict(arrowstyle="-|>", color=GREEN, lw=2, mutation_scale=14))
        a1.text((xu + xp) / 2, 2.2e-4, f"{xu - xp:.0f} dB", ha="center", fontsize=13, color=GREEN, weight="bold",
                alpha=g)
        a1.text(7.2, 0.3, "uncoded", fontsize=8.5, color=SLATE, alpha=g)
        a1.text(3.9, 3e-6, "polar", fontsize=8.5, color=BLUE, weight="bold", alpha=g)


# ----------------------------------------------------------------------------- render
TL = (
    [("title", i, 18) for i in range(18)]
    + [("noise", i, NOISE_FRAMES) for i in range(NOISE_FRAMES)]
    + [("polar", i, POL_FRAMES) for i in range(POL_FRAMES)]
    + [("enc", i, ENC_FRAMES) for i in range(ENC_FRAMES)]
    + [("dec", i, DEC_FRAMES) for i in range(DEC_FRAMES)]
    + [("res", i, RES_FRAMES) for i in range(RES_FRAMES)]
    + [("outro", i, 22) for i in range(22)]
)
FN = {"noise": scene_noise, "polar": scene_polar, "enc": scene_encode, "dec": scene_decode, "res": scene_result}


def render(args):
    idx, (name, k, K), outdir = args
    fig, ax = new_canvas()
    if name in ("title", "outro"):
        scene_title(ax, k, K, outro=name == "outro")
    else:
        FN[name](fig, ax, k, K)
    fig.savefig(os.path.join(outdir, f"f{idx:04d}.png"), facecolor=BG)
    plt.close(fig)


def init(res):
    global RES
    RES = res


def main():
    res = json.load(open(sys.argv[1])); out = sys.argv[2]
    outdir = tempfile.mkdtemp(prefix="polar_min_")
    with Pool(os.cpu_count(), initializer=init, initargs=(res,)) as p:
        p.map(render, [(i, t, outdir) for i, t in enumerate(TL)], chunksize=8)
    print(f"{len(TL)} frames ({len(TL) / FPS:.1f} s) -> {outdir}")
    pal = os.path.join(outdir, "palette.png")
    src = ["-framerate", str(FPS), "-i", os.path.join(outdir, "f%04d.png")]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *src, "-vf", "palettegen=max_colors=96:stats_mode=full", pal], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *src, "-i", pal, "-lavfi",
                    "paletteuse=dither=none:diff_mode=rectangle", "-loop", "0", out], check=True)
    print(out, os.path.getsize(out) / 1e6, "MB")


if __name__ == "__main__":
    main()
