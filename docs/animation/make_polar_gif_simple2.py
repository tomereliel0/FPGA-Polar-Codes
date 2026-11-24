"""Beginner-friendly README animation, variant 2: signal-bar metaphor, one caption per scene.

Scenes: title -> 1 noise (phone -> tower) -> 2 polarization (lanes + signal bars) -> 3 use the strong lanes
        -> 4 decode one bit at a time -> 5 result (bit grids) -> outro.
Usage (from docs/animation):
        python make_polar_gif_simple2.py ber_design2.0.json ../images/polar-codes-simple-2.gif
"""
import json, os, subprocess, sys, tempfile
from math import erfc, sqrt
from multiprocessing import Pool

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle, Polygon, Arc

from make_polar_gif import (BG, PANEL, FG, MUTED, GRID, GREEN, BLUE, AMBER, NAVY, MID, ERR, CMAP, FPS,
                            ease, new_canvas, bhattacharyya_bec,
                            FROZEN8, INFO8, DATA8, U8, X8, DEMO_L, DEMO_FLIPS, DEMO_EV)
from make_polar_gif_simple import bit_tile, SLATE, MSG, MSG_FLIPS

RES = None
TOTAL = None          # total frame count, set after the timeline is built


# ----------------------------------------------------------------------------- shared chrome
def chrome(ax, step, title, caption, gidx, cap_alpha=1.0):
    ax.text(4, 49.5, title, fontsize=18, color=FG, weight="bold", va="center")
    if step is not None:
        ax.text(96, 49.5, f"{step} / 5", fontsize=11, color=MUTED, weight="bold", va="center", ha="right")
    if caption:
        ax.text(50, 4.6, caption, fontsize=10.5, color=NAVY, ha="center", va="center", alpha=cap_alpha)
    # global progress line
    ax.add_patch(FancyBboxPatch((0, 0), 100, 0.9, boxstyle="square,pad=0", fc=GRID, ec="none"))
    ax.add_patch(FancyBboxPatch((0, 0), 100 * gidx / max(1, TOTAL - 1), 0.9, boxstyle="square,pad=0", fc=BLUE, ec="none"))


def signal_icon(ax, x, y, level, s=1.0, alpha=1.0, color=None):
    """Phone-style signal bars; level 0..1 (continuous)."""
    c = color or CMAP(level)
    for i in range(4):
        h = (0.9 + i * 0.75) * s
        fill = np.clip(level * 4 - i, 0, 1)
        bx = x + i * 1.05 * s
        ax.add_patch(FancyBboxPatch((bx, y), 0.75 * s, h, boxstyle="round,pad=0,rounding_size=0.15",
                                    fc=GRID, ec="none", alpha=alpha, zorder=3))
        if fill > 0:
            ax.add_patch(FancyBboxPatch((bx, y), 0.75 * s, h, boxstyle="round,pad=0,rounding_size=0.15",
                                        fc=c, ec="none", alpha=alpha * fill, zorder=4))


def phone(ax, x, y, alpha=1.0):
    ax.add_patch(FancyBboxPatch((x - 2.3, y - 4.2), 4.6, 8.4, boxstyle="round,pad=0,rounding_size=0.9",
                                fc="white", ec=NAVY, lw=1.6, alpha=alpha, zorder=3))
    ax.add_patch(FancyBboxPatch((x - 1.6, y - 2.9), 3.2, 6.0, boxstyle="round,pad=0,rounding_size=0.3",
                                fc="#dbe8fb", ec="none", alpha=alpha, zorder=4))
    ax.add_patch(Circle((x, y - 3.6), 0.25, color=NAVY, alpha=alpha, zorder=4))


def tower(ax, x, y, alpha=1.0, k=0):
    ax.add_patch(Polygon([[x - 2.6, y - 5], [x + 2.6, y - 5], [x, y + 3]], closed=True, fc="none", ec=NAVY,
                         lw=1.6, alpha=alpha, zorder=3))
    ax.plot([x - 1.7, x + 1.7], [y - 2.3, y - 2.3], color=NAVY, lw=1.2, alpha=alpha)
    ax.plot([x - 0.9, x + 0.9], [y + 0.2, y + 0.2], color=NAVY, lw=1.2, alpha=alpha)
    ax.add_patch(Circle((x, y + 3.4), 0.6, color=BLUE, alpha=alpha, zorder=4))
    for r in (2.0, 3.4):
        ph = (k * 0.15 + r) % 1
        ax.add_patch(Arc((x, y + 3.4), r * 2, r * 2, theta1=30, theta2=150, color=BLUE,
                                                lw=1.2, alpha=alpha * (0.35 + 0.4 * ph)))


# ----------------------------------------------------------------------------- title / outro
def scene_title(ax, k, K, gidx, outro=False):
    a = ease(k / 7)
    caps = 1 - bhattacharyya_bec(8, 0.5)
    if not outro:
        ax.text(50, 36, "Polar Codes", fontsize=34, color=FG, weight="bold", ha="center", va="center", alpha=a)
        ax.text(50, 28.5, "a 30-second visual guide", fontsize=12, color=MUTED, ha="center", va="center", alpha=a)
        t = ease((k - 6) / (K - 10))
    else:
        ax.text(50, 36, "Inside every 5G phone", fontsize=28, color=FG, weight="bold", ha="center", va="center", alpha=a)
        ax.text(50, 28.5, "This project: polar decoding in FPGA hardware — real-time and low power",
                fontsize=11, color=BLUE, ha="center", va="center", alpha=a)
        t = 1.0
    for i, v in enumerate(caps):
        lv = 0.5 + (v - 0.5) * t
        signal_icon(ax, 31 + i * 5.0, 13, lv, s=1.0, alpha=a)
    chrome(ax, None, "", "", gidx)


# ----------------------------------------------------------------------------- 1 noise
NOISE_FRAMES = 60


def scene_noise(fig, ax, k, K, gidx):
    cap = "On the way, noise flips some bits — and the receiver can't tell which ones."
    chrome(ax, 1, "Sending bits over the air", cap if k > 40 else "", gidx, ease((k - 40) / 8))
    phone(ax, 8, 27)
    tower(ax, 92, 27, k=k)
    # static
    r = np.random.default_rng(k)
    n = 110
    xs, ys = r.uniform(38, 56, n), r.normal(27, 4, n)
    ax.scatter(xs, ys, s=r.uniform(2, 9, n), color=SLATE, alpha=0.4, lw=0, zorder=1)
    ax.text(47, 18.5, "noise", fontsize=8.5, color=MUTED, ha="center")
    # bits flying along a gentle wave
    t = ease((k - 4) / 36)
    for i, b in enumerate(MSG):
        start = 12 + i * 3.5
        x = start + t * 46.0
        y = 27 + 1.6 * np.sin((x - 12) / 6.0) * (1 if 38 < x < 56 else 0.0)
        flipped = x > 47 and i in MSG_FLIPS
        bit_tile(ax, x, y, b ^ 1 if flipped else b, kind="err" if flipped else "data", w=3.2, h=3.2, fs=9, z=6)
    if k > 40:
        a = ease((k - 40) / 8)
        for i in MSG_FLIPS:
            x = 12 + i * 3.5 + 46.0
            ax.add_patch(Circle((x, 27), 2.4, fc="none", ec=ERR, lw=1.4,
                                alpha=a, zorder=7))


# ----------------------------------------------------------------------------- 2 polarization
LANE_Y = [38.5 - i * 4.15 for i in range(8)]
PIPE_X0, PIPE_X1 = 22.0, 68.0
ICON_X = 73.0
CAP8 = [np.repeat(1 - bhattacharyya_bec(2 ** l, 0.5), 8 // 2 ** l) for l in range(4)]
P_IN, P_ROUND, P_END = 14, 22, 30
POL_FRAMES = P_IN + 3 * P_ROUND + P_END


def lanes(ax, vals, alpha=1.0, icons=True, numbers=True):
    for i, v in enumerate(vals):
        y = LANE_Y[i]
        ax.add_patch(FancyBboxPatch((PIPE_X0, y - 1.15), PIPE_X1 - PIPE_X0, 2.3,
                                    boxstyle="round,pad=0,rounding_size=1.1", fc=PANEL, ec=GRID, lw=0.8,
                                    alpha=alpha, zorder=1))
        ax.add_patch(FancyBboxPatch((PIPE_X0, y - 1.15), (PIPE_X1 - PIPE_X0) * max(v, 0.02), 2.3,
                                    boxstyle="round,pad=0,rounding_size=1.1", fc=CMAP(v), ec="none",
                                    alpha=alpha * 0.85, zorder=2))
        if numbers:
            ax.text(PIPE_X0 - 2.0, y, f"lane {i + 1}", fontsize=7.5, color=MUTED, ha="right", va="center", alpha=alpha)
        if icons:
            signal_icon(ax, ICON_X, y - 1.4, v, s=0.85, alpha=alpha)


def scene_polar(fig, ax, k, K, gidx):
    if k < P_IN + 3 * P_ROUND:
        cap = "Mix copies of the same channel together with simple XORs …"
    else:
        cap = "… and they split: some lanes get perfect signal, others almost none."
    chrome(ax, 2, "One channel → strong and weak lanes", cap, gidx)
    kk = k - P_IN
    if kk < 0:
        lvl, t = 0, 0.0
    elif kk >= 3 * P_ROUND:
        lvl, t = 3, 0.0
    else:
        lvl, t = kk // P_ROUND, ease(((kk % P_ROUND) - 8) / (P_ROUND - 10))
    vals = CAP8[lvl] if t <= 0 else CAP8[lvl] + t * (CAP8[lvl + 1] - CAP8[lvl])
    lanes(ax, vals, numbers=True)
    # mixing links for the current round
    if 0 <= kk < 3 * P_ROUND:
        r = kk // P_ROUND
        h = 4 // 2 ** r
        la = ease((kk % P_ROUND) / 6) * (1 - ease(((kk % P_ROUND) - 14) / 6))
        for blk in range(0, 8, 2 * h):
            for j in range(blk, blk + h):
                y0, y1 = LANE_Y[j], LANE_Y[j + h]
                xs = PIPE_X1 + 9.5 + 3.5 * np.sin(np.linspace(0, np.pi, 30)) * (1 + 0.3 * (h > 1))
                ys = np.linspace(y0, y1, 30)
                ax.plot(xs, ys, color=AMBER, lw=1.4, alpha=la)
                xm = xs[15]
                ax.add_patch(Circle((xm, (y0 + y1) / 2), 0.9, fc="white", ec=AMBER, lw=1.2, alpha=la, zorder=5))
                ax.plot([xm - 0.55, xm + 0.55], [(y0 + y1) / 2] * 2, color=AMBER, lw=1.1, alpha=la, zorder=6)
                ax.plot([xm, xm], [(y0 + y1) / 2 - 0.55, (y0 + y1) / 2 + 0.55], color=AMBER, lw=1.1, alpha=la, zorder=6)
        ax.text(92, 41.5, f"mix {r + 1}", fontsize=9, color=AMBER, weight="bold", ha="center", alpha=max(la, 0.4))
    if kk >= 3 * P_ROUND:
        a = ease((kk - 3 * P_ROUND) / 8)
        for i, v in enumerate(CAP8[3]):
            good = v > 0.5
            ax.text(ICON_X + 5.4, LANE_Y[i], "strong" if good else "weak", fontsize=8.5, va="center",
                    color=GREEN if good else SLATE, weight="bold", alpha=a)


# ----------------------------------------------------------------------------- 3 placement
PL_IN, PL_HOP, PL_SEND, PL_HOLD = 10, 30, 18, 14
PL_FRAMES = PL_IN + PL_HOP + PL_SEND + PL_HOLD


def scene_place(fig, ax, k, K, gidx):
    if k < PL_IN + PL_HOP:
        cap = "Your data rides the strong lanes. Weak lanes carry 0s agreed on in advance."
    else:
        cap = "Out go 8 bits for 4 bits of data — that extra room is what makes repair possible."
    chrome(ax, 3, "Put the data on the strong lanes", cap, gidx)
    lanes(ax, CAP8[3], alpha=0.6)
    a = ease(k / PL_IN)
    hop = (k - PL_IN) / PL_HOP
    ax.text(4, 41.5, "data", fontsize=9, color=FG, weight="bold", va="center", alpha=a * (1 - ease(hop / 0.5)))
    send = ease((k - PL_IN - PL_HOP) / PL_SEND) if k >= PL_IN + PL_HOP else 0.0
    for j, d in enumerate(DATA8):
        lane = int(INFO8[j])
        tt = ease((hop - j * 0.12) / 0.6)
        x0, y0 = 12 + j * 4.0, 41.5
        x1, y1 = PIPE_X0 + 3, LANE_Y[lane]
        x = x0 + (x1 - x0) * tt
        y = y0 + (y1 - y0) * tt + 6 * np.sin(np.pi * tt) * (tt < 1)
        x += (PIPE_X1 - 3 - x1) * send
        bit_tile(ax, x, y, int(d), w=3.0, h=3.0, fs=8.5, z=6)
    for i in np.where(FROZEN8)[0]:
        tt = ease((hop - 0.3 - i * 0.05) / 0.4)
        if tt > 0:
            x = PIPE_X0 + 3 + (PIPE_X1 - 3 - PIPE_X0 - 3) * send
            bit_tile(ax, x, LANE_Y[i], 0, kind="frozen", w=3.0, h=3.0, fs=8.5, alpha=tt, z=6)
    if send > 0:
        # the mixer turns the 8 lane bits into the 8 transmitted bits
        for i in range(8):
            tt = ease((send - 0.6) / 0.4)
            if tt > 0:
                bit_tile(ax, 90, LANE_Y[i], int(X8[i]), w=3.0, h=3.0, fs=8.5, alpha=tt, z=6)
        ma = ease((send - 0.4) / 0.4)
        ax.add_patch(FancyBboxPatch((80.2, LANE_Y[7] - 2), 4.6, LANE_Y[0] - LANE_Y[7] + 4,
                                    boxstyle="round,pad=0,rounding_size=1", fc="white", ec=BLUE, lw=1.4, alpha=ma,
                                    zorder=5))
        ym = (LANE_Y[0] + LANE_Y[7]) / 2
        ax.add_patch(Circle((82.5, ym), 1.6, fc="white", ec=BLUE, lw=1.4, alpha=ma, zorder=6))
        ax.plot([81.5, 83.5], [ym, ym], color=BLUE, lw=1.4, alpha=ma, zorder=7)
        ax.plot([82.5, 82.5], [ym - 1.0, ym + 1.0], color=BLUE, lw=1.4, alpha=ma, zorder=7)
        ax.text(82.5, LANE_Y[7] - 3.2, "mix", ha="center", fontsize=8, color=BLUE, weight="bold", alpha=ma)
        ax.text(90, 42.0, "sent", fontsize=8.5, color=MUTED, ha="center", weight="bold", alpha=ma)


# ----------------------------------------------------------------------------- 4 decoding
LEAVES = [e for e in DEMO_EV if e[0] == "leaf"]
DC_IN, DC_BIT, DC_FIX, DC_HOLD = 14, 9, 14, 16
DEC_FRAMES = DC_IN + 8 * DC_BIT + DC_FIX + DC_HOLD
RX_X = 88.0


def scene_decode(fig, ax, k, K, gidx):
    done = k >= DC_IN + 8 * DC_BIT
    if not done:
        cap = "The receiver decides lane 1, then lane 2, … each answer helps with the next one."
    else:
        cap = "Data recovered — and the two damaged bits are repaired."
    chrome(ax, 4, "Decode one bit at a time", cap, gidx)
    lanes(ax, CAP8[3], alpha=0.35, icons=False)
    a = ease(k / DC_IN)
    ax.text(RX_X, 42.0, "received", fontsize=8.5, color=MUTED, ha="center", weight="bold", alpha=a)
    fix = ease((k - DC_IN - 8 * DC_BIT) / DC_FIX) if done else 0.0
    for i in range(8):
        rx = int(DEMO_L[i] < 0)
        if i in DEMO_FLIPS and fix > 0.5:
            bit_tile(ax, RX_X, LANE_Y[i], int(X8[i]), w=3.0, h=3.0, fs=8.5)
            ax.add_patch(Circle((RX_X, LANE_Y[i]), 2.3 + 3 * (fix - 0.5), fc="none", ec=GREEN, lw=1.6,
                                alpha=max(0, 1 - 2 * (fix - 0.5)), zorder=7))
        else:
            bit_tile(ax, RX_X, LANE_Y[i], rx, kind="err" if i in DEMO_FLIPS else "data", w=3.0, h=3.0, fs=8.5,
                     alpha=a)
    nb = (k - DC_IN) / DC_BIT
    cur = int(np.floor(nb)) if nb >= 0 else -1
    for n in range(min(cur + 1, 8)):
        u, idx = LEAVES[n][3], LEAVES[n][4]
        pop = ease((nb - n) / 0.45)
        fz = bool(FROZEN8[idx])
        bit_tile(ax, PIPE_X0 + 3, LANE_Y[idx], u, kind="frozen" if fz else "data", w=3.0, h=3.0, fs=8.5, alpha=pop)
        if pop >= 1:
            ax.text(PIPE_X0 + 7, LANE_Y[idx], "known 0" if fz else "✓", fontsize=8 if fz else 11, va="center",
                    color=SLATE if fz else GREEN, weight="bold")
    if 0 <= cur < 8:
        idx = LEAVES[cur][4]
        y = LANE_Y[idx]
        ax.add_patch(FancyBboxPatch((PIPE_X0 - 1, y - 1.9), RX_X - PIPE_X0 + 4.5, 3.8,
                                    boxstyle="round,pad=0,rounding_size=1.2", fc="none", ec=AMBER, lw=1.8, zorder=8))
        if not FROZEN8[idx]:
            raw = ((k - DC_IN) % DC_BIT) / (DC_BIT - 1)
            for i in range(8):
                p = ease((raw - i * 0.05) / 0.65)
                ys = LANE_Y[i] + (y - LANE_Y[i]) * p
                xs = RX_X - 2 - (RX_X - 2 - (PIPE_X0 + 6)) * p
                ax.add_patch(Circle((xs, ys), 0.45, color=AMBER, alpha=0.8, zorder=9))


# ----------------------------------------------------------------------------- 5 result
GR_C, GR_R = 46, 28
R_IN, R_FILL, R_HOLD = 8, 30, 32
RES_FRAMES = R_IN + R_FILL + R_HOLD


def scene_result(fig, ax, k, K, gidx):
    r = RES
    snr = r["ebn0"][-1]
    pu = 0.5 * erfc(sqrt(2 * 10 ** (snr / 10)) / sqrt(2))
    pc = r["ber"][-1]
    ratio = float(f"{pu / pc:.2g}")
    nbits = GR_C * GR_R
    rng = np.random.default_rng(11)
    n_err_u = int(round(nbits * pu))
    err_u = set(rng.choice(nbits, n_err_u, replace=False))
    err_c = set()                                   # expected nbits*pc << 1
    fill = ease((k - R_IN) / R_FILL) if k >= R_IN else 0.0
    shown = int(nbits * fill)
    cap = (f"Same signal power, {nbits:,} bits each — about {ratio:,.0f}× fewer errors with the polar code."
           if k >= R_IN + R_FILL else "")
    chrome(ax, 5, "Result", cap, gidx, ease((k - R_IN - R_FILL) / 8))
    for side, (x0, title, errs, col) in enumerate([(6.5, "without coding", err_u, SLATE),
                                                   (54.0, "with a polar code", err_c, BLUE)]):
        ax.text(x0 + 19.5, 42.5, title, fontsize=12, color=FG, weight="bold", ha="center")
        idx = np.arange(shown)
        cx = x0 + (idx % GR_C) * 0.86
        cy = 38.0 - (idx // GR_C) * 0.92
        ok = np.array([i not in errs for i in idx], bool) if shown else np.zeros(0, bool)
        ax.scatter(cx[ok], cy[ok], s=3.2, color=col if side else "#c5d0dc", lw=0)
        if (~ok).any():
            ax.scatter(cx[~ok], cy[~ok], s=26, color=ERR, lw=0, zorder=4)
            ax.scatter(cx[~ok], cy[~ok], s=110, color=ERR, alpha=0.15, lw=0, zorder=3)
        nerr = int((~ok).sum())
        ax.text(x0 + 19.5, 9.0, f"{nerr} wrong", fontsize=15, ha="center", weight="bold",
                color=ERR if nerr else GREEN, alpha=1 if shown else 0)


# ----------------------------------------------------------------------------- render
TL = (
    [("title", i, 22) for i in range(22)]
    + [("noise", i, NOISE_FRAMES) for i in range(NOISE_FRAMES)]
    + [("polar", i, POL_FRAMES) for i in range(POL_FRAMES)]
    + [("place", i, PL_FRAMES) for i in range(PL_FRAMES)]
    + [("dec", i, DEC_FRAMES) for i in range(DEC_FRAMES)]
    + [("res", i, RES_FRAMES) for i in range(RES_FRAMES)]
    + [("outro", i, 24) for i in range(24)]
)
TOTAL = len(TL)
FN = {"noise": scene_noise, "polar": scene_polar, "place": scene_place, "dec": scene_decode, "res": scene_result}


def render(args):
    idx, (name, k, K), outdir = args
    fig, ax = new_canvas()
    if name in ("title", "outro"):
        scene_title(ax, k, K, idx, outro=name == "outro")
    else:
        FN[name](fig, ax, k, K, idx)
    fig.savefig(os.path.join(outdir, f"f{idx:04d}.png"), facecolor=BG)
    plt.close(fig)


def init(res):
    global RES
    RES = res


def main():
    res = json.load(open(sys.argv[1])); out = sys.argv[2]
    outdir = tempfile.mkdtemp(prefix="polar_s2_")
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
