"""Beginner-friendly README animation: polar codes explained without math.

Scenes: title -> 1 noise -> 2 polarization -> 3 encoding -> 4 decoding -> 5 result -> outro.
Usage (from docs/animation):
        python make_polar_gif_simple.py ber_design2.0.json ../images/polar-codes-simple.gif
Shares the theme, helpers and the N=8 demo (data, noise, SC trace) with make_polar_gif.py.
"""
import json, os, subprocess, sys, tempfile
from math import erfc, sqrt
from multiprocessing import Pool

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle

import make_polar_gif as base
from make_polar_gif import (BG, PANEL, FG, MUTED, GRID, GREEN, BLUE, AMBER, NAVY, MID, ERR, CMAP, FPS,
                            ease, new_canvas, header, footer, bhattacharyya_bec,
                            FROZEN8, INFO8, DATA8, U8, X8, DEMO_L, DEMO_FLIPS, DEMO_EV)

SLATE = "#8597ad"
STEPS_S = ["1  Noise", "2  Polarization", "3  Encoding", "4  Decoding", "5  Result"]
RES = None


def tile(ax, x, y, txt, fc, tc, ec=None, w=3.4, h=3.4, alpha=1.0, fs=10, lw=1.2, z=3):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0,rounding_size=0.7",
                                fc=fc, ec=ec or fc, lw=lw, alpha=alpha, zorder=z))
    ax.text(x, y, txt, ha="center", va="center", fontsize=fs, color=tc, weight="bold", alpha=alpha, zorder=z + 1)


def bit_tile(ax, x, y, b, alpha=1.0, kind="data", **kw):
    if kind == "data":
        tile(ax, x, y, str(b), BLUE if b else "#dbe8fb", "white" if b else NAVY, alpha=alpha, **kw)
    elif kind == "frozen":
        tile(ax, x, y, str(b), "white", SLATE, ec=SLATE, alpha=alpha, **kw)
    elif kind == "err":
        tile(ax, x, y, str(b), "#fde8e7", ERR, ec=ERR, alpha=alpha, lw=1.6, **kw)


# ----------------------------------------------------------------------------- title / outro
def scene_title(ax, k, K, outro=False):
    a = ease(k / max(1, K * 0.35))
    if not outro:
        ax.text(50, 34, "Polar Codes", fontsize=34, color=FG, weight="bold", ha="center", va="center", alpha=a)
        ax.text(50, 26.5, "explained in 30 seconds — no math needed", fontsize=12, color=MUTED,
                ha="center", va="center", alpha=a)
        ax.text(50, 20.5, "how 5G phones fix the errors that noise causes", fontsize=10, color=BLUE,
                ha="center", va="center", alpha=a)
    else:
        ax.text(50, 35, "Polar codes protect the control data", fontsize=20, color=FG, weight="bold",
                ha="center", va="center", alpha=a)
        ax.text(50, 30, "of every 5G phone call", fontsize=20, color=FG, weight="bold", ha="center", va="center", alpha=a)
        ax.text(50, 22.5, "This project: building the decoder in FPGA hardware — faster and lower power than software",
                fontsize=10, color=BLUE, ha="center", va="center", alpha=a)
    for i in range(16):
        v = 1 - bhattacharyya_bec(16, 0.5)[i]
        ax.add_patch(Circle((26 + i * 3.2, 10), 0.9, color=CMAP(v), alpha=a))
    footer(ax)


# ----------------------------------------------------------------------------- 1 noise
MSG = np.array([1, 0, 1, 1, 0, 1, 0, 0], np.uint8)
MSG_FLIPS = [2, 5]
NOISE_FRAMES = 56


def noise_cloud(ax, k, x0=40, x1=60, y0=23, y1=35, n=90, alpha=1.0):
    r = np.random.default_rng(k)
    ax.add_patch(FancyBboxPatch((x0, y0), x1 - x0, y1 - y0, boxstyle="round,pad=0,rounding_size=2",
                                fc=PANEL, ec=GRID, lw=1, alpha=alpha, zorder=1))
    ax.scatter(r.uniform(x0 + 1, x1 - 1, n), r.uniform(y0 + 1, y1 - 1, n), s=r.uniform(2, 10, n),
               color=SLATE, alpha=0.45 * alpha, lw=0, zorder=2)
    ax.text((x0 + x1) / 2, y0 - 2, "noisy channel (radio, cable …)", ha="center", fontsize=8, color=MUTED, alpha=alpha)


def scene_noise(fig, ax, k, K):
    header(ax, 0, "The problem: noise flips bits",
           "Every real channel adds noise. Some bits arrive wrong — and the receiver can't tell which.", STEPS_S)
    noise_cloud(ax, k)
    ax.text(6, 37.5, "sent", fontsize=9, color=MUTED, weight="bold")
    ax.text(94, 37.5, "received", fontsize=9, color=MUTED, weight="bold", ha="right")
    t = ease((k - 6) / 34)
    for i, b in enumerate(MSG):
        xs = 6 + i * 4.0
        bit_tile(ax, xs + 1.7, 29, b, alpha=0.35 if t > 0 else 1.0)
        x = xs + 1.7 + t * 56.0
        passed = x > 50
        flipped = passed and i in MSG_FLIPS
        bb = b ^ 1 if flipped else b
        bit_tile(ax, x, 29, bb, kind="err" if flipped else "data", z=5)
    if k > 44:
        a = ease((k - 44) / 8)
        for i in MSG_FLIPS:
            ax.text(63.7 + i * 4.0, 25.4, "✗", ha="center", fontsize=11, color=ERR, weight="bold", alpha=a)
        ax.text(50, 14, "2 of 8 bits are wrong. Re-sending costs time — can we fix them instead?",
                ha="center", fontsize=11, color=FG, weight="bold", alpha=a)
    footer(ax)


# ----------------------------------------------------------------------------- 2 polarization
CAP = [np.repeat(1 - bhattacharyya_bec(2 ** l, 0.5), 8 // 2 ** l) for l in range(4)]
POL_HOLD0, POL_STEP, POL_END = 14, 13, 30
POLS_FRAMES = POL_HOLD0 + 3 * POL_STEP + POL_END
LANE_X = [17 + i * 7.6 for i in range(8)]
BAR_Y0, BAR_H = 8.5, 26.0


def bars(ax, vals, alpha=1.0, labels=True, colors=None, top_txt=True):
    for i, v in enumerate(vals):
        x = LANE_X[i]
        ax.add_patch(FancyBboxPatch((x - 2.4, BAR_Y0), 4.8, BAR_H, boxstyle="round,pad=0,rounding_size=0.6",
                                    fc=PANEL, ec=GRID, lw=0.8, alpha=alpha, zorder=1))
        c = colors[i] if colors else CMAP(v)
        if v > 0.004:
            ax.add_patch(FancyBboxPatch((x - 2.4, BAR_Y0), 4.8, max(BAR_H * v, 0.6),
                                        boxstyle="round,pad=0,rounding_size=0.6", fc=c, ec="none", alpha=alpha, zorder=2))
        if top_txt:
            ax.text(x, BAR_Y0 + BAR_H + 1.4, f"{v * 100:.0f}%", ha="center", fontsize=8.5, color=FG, alpha=alpha,
                    weight="bold")
        if labels:
            ax.text(x, BAR_Y0 - 2.0, f"lane {i + 1}", ha="center", fontsize=7.5, color=MUTED, alpha=alpha)


def scene_polar(fig, ax, k, K):
    header(ax, 1, "The trick: polarization",
           "Mix 8 copies of the same so-so channel with simple XORs → some “lanes” become very reliable, others useless.",
           STEPS_S)
    if k < POL_HOLD0:
        lvl, t = 0, 0.0
    else:
        s = (k - POL_HOLD0) // POL_STEP
        if s >= 3:
            lvl, t = 3, 0.0
        else:
            lvl, t = s, ease(((k - POL_HOLD0) % POL_STEP) / (POL_STEP - 3))
    vals = CAP[lvl] if t == 0 else CAP[lvl] + t * (CAP[lvl + 1] - CAP[lvl])
    bars(ax, vals)
    ax.text(5.5, BAR_Y0 + BAR_H / 2 + 2, "how often", fontsize=8, color=MUTED, ha="center")
    ax.text(5.5, BAR_Y0 + BAR_H / 2 - 0.6, "a bit gets", fontsize=8, color=MUTED, ha="center")
    ax.text(5.5, BAR_Y0 + BAR_H / 2 - 3.2, "through", fontsize=8, color=MUTED, ha="center")
    shown = lvl + (1 if t > 0.5 else 0)
    ax.text(82.5, 35.5, f"mixing rounds: {shown}", fontsize=10, color=BLUE, weight="bold")
    if k >= POL_HOLD0 + 3 * POL_STEP:
        a = ease((k - POL_HOLD0 - 3 * POL_STEP) / 8)
        ax.text(82.5, 26, "good lanes", fontsize=10, color=GREEN, weight="bold", alpha=a)
        ax.text(82.5, 23, "→ almost always right", fontsize=8.5, color=FG, alpha=a)
        ax.text(82.5, 17, "bad lanes", fontsize=10, color=SLATE, weight="bold", alpha=a)
        ax.text(82.5, 14, "→ almost always wrong", fontsize=8.5, color=FG, alpha=a)
        ax.text(82.5, 8.5, "5G uses up to 1024\nlanes: the split gets\nnearly perfect", fontsize=8, color=MUTED, alpha=a)
    footer(ax)


# ----------------------------------------------------------------------------- 3 encoding
ENC_IN, ENC_DROP, ENC_MIX, ENC_HOLD = 10, 24, 18, 14
ENCS_FRAMES = ENC_IN + ENC_DROP + ENC_MIX + ENC_HOLD


def scene_encode(fig, ax, k, K):
    header(ax, 2, "Encoding: data on the good lanes",
           "Real data rides the reliable lanes. The bad lanes carry fixed 0s that the receiver already knows.", STEPS_S)
    vals = CAP[3]
    cols = [GREEN if not f else "#c5d0dc" for f in FROZEN8]
    bars(ax, vals, alpha=0.55, colors=cols, top_txt=False, labels=False)
    # data / frozen labels
    a = ease(k / ENC_IN)
    ax.text(5, 38.6, "your data:", fontsize=9, color=FG, weight="bold", alpha=a, va="center")
    for j, d in enumerate(DATA8):
        bit_tile(ax, 21 + j * 4.2, 38.6, d, alpha=a)
    # drop tiles into lanes
    t = (k - ENC_IN) / ENC_DROP
    for i in range(8):
        frozen = FROZEN8[i]
        order = i / 8
        tt = ease((t - order * 0.5) / 0.5)
        if tt <= 0:
            continue
        y = 38.6 + (BAR_Y0 + BAR_H - 4 - 38.6) * tt
        if frozen:
            x = LANE_X[i]
            bit_tile(ax, x, y, 0, kind="frozen", alpha=tt)
        else:
            j = list(INFO8).index(i)
            x0 = 21 + j * 4.2
            x = x0 + (LANE_X[i] - x0) * tt
            bit_tile(ax, x, y, int(U8[i]), alpha=1.0)
        if tt >= 1:
            ax.text(LANE_X[i], BAR_Y0 - 2.0, "data" if not frozen else "fixed 0", ha="center", fontsize=7.5,
                    color=GREEN if not frozen else SLATE, weight="bold")
    # mixer -> codeword
    mt = (k - ENC_IN - ENC_DROP) / ENC_MIX
    if mt > 0:
        ma = ease(mt)
        ax.annotate("", xy=(85.5, 21.5), xytext=(80.5, 21.5),
                    arrowprops=dict(arrowstyle="-|>", color=BLUE, lw=1.5, alpha=ma))
        ax.text(83, 24, "XOR\nmix", ha="center", fontsize=8, color=BLUE, weight="bold", alpha=ma, va="bottom")
        ax.text(93, 38.5, "sent", ha="center", fontsize=8.5, color=MUTED, weight="bold", alpha=ma)
        for i in range(8):
            if mt > i / 10:
                bit_tile(ax, 93, 35.0 - i * 3.75, int(X8[i]), alpha=ease((mt - i / 10) / 0.25), w=3.2, h=3.2, fs=9)
    if k >= ENC_IN + ENC_DROP + ENC_MIX:
        ha = ease((k - ENC_IN - ENC_DROP - ENC_MIX) / 6)
        ax.text(50, 2.6, "4 data bits → 8 sent bits: the extra bits are what lets the receiver fix errors",
                ha="center", fontsize=9, color=NAVY, weight="bold", alpha=ha)
    footer(ax)


# ----------------------------------------------------------------------------- 4 decoding
LEAF_ORDER = [e for e in DEMO_EV if e[0] == "leaf"]          # (kind, d, k, u, idx) in decoding order
DEC_IN, DEC_BIT, DEC_END = 16, 8, 26
DECS_FRAMES = DEC_IN + DEC_BIT * 8 + DEC_END


def scene_decode(fig, ax, k, K):
    header(ax, 3, "Decoding: one bit at a time",
           "The receiver decides lane 1, then lane 2, … each decision uses every bit decided before it.", STEPS_S)
    a = ease(k / 10)
    ax.text(5, 36.2, "received", fontsize=9, color=FG, weight="bold", alpha=a)
    ax.text(5, 33.6, "(2 damaged)", fontsize=7.5, color=ERR, alpha=a)
    for i in range(8):
        rx = int(DEMO_L[i] < 0)
        bit_tile(ax, LANE_X[i], 35.0, rx, kind="err" if i in DEMO_FLIPS else "data", alpha=a)
    ax.text(5, 20.2, "decoded", fontsize=9, color=FG, weight="bold", alpha=a)
    for i in range(8):
        ax.add_patch(FancyBboxPatch((LANE_X[i] - 1.7, 19.3 - 1.7), 3.4, 3.4, boxstyle="round,pad=0,rounding_size=0.7",
                                    fc="white", ec=GRID, lw=1, ls="--", alpha=a, zorder=1))
        ax.text(LANE_X[i], 15.0, f"lane {i + 1}", ha="center", fontsize=7.5, color=MUTED, alpha=a)
    nb = (k - DEC_IN) / DEC_BIT
    cur = int(np.floor(nb)) if nb >= 0 else -1
    for n in range(min(cur + 1, 8)):
        _, _, _, u, idx = LEAF_ORDER[n]
        fz = FROZEN8[idx]
        pop = ease((nb - n) / 0.5)
        bit_tile(ax, LANE_X[idx], 19.3, u, kind="frozen" if fz else "data", alpha=pop)
        if pop >= 1 and n < cur or (n == cur and pop >= 1):
            ax.text(LANE_X[idx], 23.3, "known" if fz else "✓", ha="center", fontsize=7.5 if fz else 10,
                    color=SLATE if fz else GREEN, weight="bold")
    if 0 <= cur < 8:
        idx = LEAF_ORDER[cur][4]
        # arrows from received bits + previous decisions into the current lane
        ax.add_patch(FancyBboxPatch((LANE_X[idx] - 2.6, 19.3 - 2.6), 5.2, 5.2, boxstyle="round,pad=0,rounding_size=1",
                                    fc="none", ec=AMBER, lw=2, zorder=6))
        if not FROZEN8[idx]:
            for i in range(8):
                ax.plot([LANE_X[i], LANE_X[idx]], [33.1, 21.4], color=AMBER, lw=0.7, alpha=0.5, zorder=0)
            for n in range(cur):
                j = LEAF_ORDER[n][4]
                ax.add_patch(FancyBboxPatch((LANE_X[j] - 2.2, 19.3 - 2.2), 4.4, 4.4,
                                            boxstyle="round,pad=0,rounding_size=0.9", fc="none", ec=NAVY,
                                            lw=1.0, ls=":", zorder=6))
            ax.text(50, 7.5, "data lane: combine the received signal with all earlier decisions",
                    ha="center", fontsize=9, color=AMBER, weight="bold")
        else:
            ax.text(50, 7.5, "fixed lane: it's 0 by design — no guessing needed, and it helps the next lanes",
                    ha="center", fontsize=9, color=SLATE, weight="bold")
    if cur >= 8:
        ea = ease((k - DEC_IN - 8 * DEC_BIT) / 8)
        ax.text(50, 7.5, "✓  data 1 0 1 1 recovered — both damaged bits were fixed", ha="center", fontsize=11,
                color=GREEN, weight="bold", alpha=ea)
    footer(ax)


# ----------------------------------------------------------------------------- 5 result
RESS_COUNT, RESS_HOLD = 34, 30
RESS_FRAMES = RESS_COUNT + RESS_HOLD


def scene_result(fig, ax, k, K):
    r = RES
    snr = r["ebn0"][-1]
    ber_c = r["ber"][-1]
    ber_u = 0.5 * erfc(sqrt(2 * 10 ** (snr / 10)) / sqrt(2))
    eu, ec = ber_u * 1e6, ber_c * 1e6
    header(ax, 4, "The result: almost no errors",
           f"Wrong bits per 1,000,000 data bits, same transmit power — simulated with the real 5G-size code "
           f"(1024 bits), {sum(r['frames']) / 1e6:.1f} M blocks.", STEPS_S)
    t = ease(k / RESS_COUNT)
    ymax = 70.0
    rows = [("without coding", eu, SLATE, 30.0), ("with a polar code", ec, BLUE, 16.0)]
    for name, val, c, y in rows:
        ax.text(5, y, name, fontsize=11, color=FG, weight="bold", va="center")
        ax.add_patch(FancyBboxPatch((28, y - 3), ymax - 28 + 1, 6, boxstyle="round,pad=0,rounding_size=1",
                                    fc=PANEL, ec=GRID, lw=0.8))
        w = (ymax - 28 + 1) * (val / eu) * t
        if w > 0.3:
            ax.add_patch(FancyBboxPatch((28, y - 3), max(w, 0.8), 6, boxstyle="round,pad=0,rounding_size=1",
                                        fc=c, ec="none"))
        else:
            ax.add_patch(FancyBboxPatch((28, y - 3), 0.8 * min(1, t * 3), 6, boxstyle="round,pad=0,rounding_size=0.4",
                                        fc=c, ec="none"))
        shown = val * t
        if val > 50 and t >= 1:
            shown = round(val, -2)
        ax.text(ymax + 3, y, f"{shown:,.0f}", fontsize=18, color=c, weight="bold", va="center")
    if k >= RESS_COUNT:
        a = ease((k - RESS_COUNT) / 8)
        ax.text(50, 6.5, f"≈ {float(f'{eu / ec:.2g}'):,.0f}× fewer errors", ha="center", fontsize=20, color=GREEN, weight="bold", alpha=a)
    footer(ax)


# ----------------------------------------------------------------------------- render
TL = (
    [("title", i, 20) for i in range(20)]
    + [("noise", i, NOISE_FRAMES) for i in range(NOISE_FRAMES)]
    + [("polar", i, POLS_FRAMES) for i in range(POLS_FRAMES)]
    + [("enc", i, ENCS_FRAMES) for i in range(ENCS_FRAMES)]
    + [("dec", i, DECS_FRAMES) for i in range(DECS_FRAMES)]
    + [("res", i, RESS_FRAMES) for i in range(RESS_FRAMES)]
    + [("outro", i, 24) for i in range(24)]
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
    outdir = tempfile.mkdtemp(prefix="polar_simple_")
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
