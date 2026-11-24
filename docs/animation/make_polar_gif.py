"""Generate docs/images/polar-codes.gif — a short README animation of polar codes.

Scenes: title -> 1 channel polarization -> 2 encoding (N=8) -> 3 SC decoding (N=8)
        -> 4 BER/FER (N=1024, K=512, Monte-Carlo) -> outro.
Usage (from docs/animation):
        python ber_sim.py 2.0                                   # -> ber_design2.0.json (~4 min)
        python make_polar_gif.py ber_design2.0.json ../images/polar-codes.gif
Needs:  numpy, matplotlib, ffmpeg on PATH.
"""
import json, os, shutil, subprocess, sys, tempfile
from multiprocessing import Pool

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle
from matplotlib.colors import LinearSegmentedColormap

from polar_core import bhattacharyya_bec, get_frozen_mask, encode

FPS = 12
W, H = 100.0, 56.25                      # drawing coordinates (16:9)
FIG = (8.8, 4.95); DPI = 100             # -> 880 x 495 px

# light "white / blue" theme.  Semantic names: GREEN = information / good, RED = frozen / bad (slate),
# AMBER = active highlight, PURPLE = partial sums, ERR = bit flipped by noise.
BG, PANEL, FG, MUTED, GRID = "#ffffff", "#f3f7fc", "#0b1f3a", "#5f7189", "#d3deeb"
GREEN, RED, BLUE, AMBER, PURPLE = "#0b63ce", "#8597ad", "#1f6feb", "#0ea5e9", "#123a7a"
NAVY, MID, ERR = "#123a7a", "#6ea8f7", "#e5534b"
CMAP = LinearSegmentedColormap.from_list("pol", ["#c5d0dc", MID, GREEN])
STEPS = ["1  Polarization", "2  Encoding", "3  SC decoding", "4  BER / FER"]


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


# ----------------------------------------------------------------------------- canvas helpers
def new_canvas():
    fig = plt.figure(figsize=FIG, dpi=DPI, facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W); ax.set_ylim(0, H); ax.set_aspect("equal"); ax.axis("off")
    ax.set_facecolor(BG)
    return fig, ax


def header(ax, step, title, subtitle, steps=None):
    steps = steps or STEPS
    gap = 1.6
    x0, pw = 3.0, (94.0 - gap * (len(steps) - 1)) / len(steps)
    for i, s in enumerate(steps):
        active = i == step
        done = i < step
        fc = BLUE if active else (PANEL)
        ec = BLUE if active else (GRID)
        ax.add_patch(FancyBboxPatch((x0 + i * (pw + gap), 51.2), pw, 3.4,
                                    boxstyle="round,pad=0,rounding_size=1.7", fc=fc, ec=ec, lw=1))
        ax.text(x0 + i * (pw + gap) + pw / 2, 52.9, s + ("  ✓" if done else ""), ha="center", va="center",
                fontsize=8.5, color=BG if active else (FG if done else MUTED), weight="bold")
    ax.text(3, 47.0, title, fontsize=15, color=FG, weight="bold", va="center")
    ax.text(3, 43.6, subtitle, fontsize=9.2, color=MUTED, va="center")


def footer(ax):
    ax.text(97, 1.4, "FPGA-Polar-Codes · TAU EE", fontsize=7, color=GRID, ha="right", va="center")


def style_axes(a):
    a.set_facecolor(PANEL)
    for s in a.spines.values():
        s.set_color(GRID)
    a.tick_params(colors=MUTED, labelsize=7.5)
    a.xaxis.label.set_color(MUTED); a.yaxis.label.set_color(MUTED)


# ----------------------------------------------------------------------------- scene 0: title
def scene_title(ax, k, K, outro=False):
    a = ease(k / max(1, K * 0.35))
    if not outro:
        ax.text(50, 33, "Polar Codes", fontsize=34, color=FG, weight="bold", ha="center", va="center", alpha=a)
        ax.text(50, 25.5, "channel polarization  ·  encoding  ·  SC decoding  ·  BER / FER",
                fontsize=11, color=MUTED, ha="center", va="center", alpha=a)
        ax.text(50, 18.5, "Arıkan (2009) — the first provably capacity-achieving codes, used in 5G NR control channels",
                fontsize=8.5, color=BLUE, ha="center", va="center", alpha=a)
    else:
        ax.text(50, 33, "Next: SC decoder on FPGA", fontsize=26, color=FG, weight="bold", ha="center", va="center", alpha=a)
        ax.text(50, 25.5, "N = 1024 · K = 512 · AMD Zynq UltraScale+ (iWave RainboW-G30)",
                fontsize=11, color=MUTED, ha="center", va="center", alpha=a)
        ax.text(50, 18.5, "hardware vs. software: throughput · latency · power",
                fontsize=9, color=BLUE, ha="center", va="center", alpha=a)
    # small polarization motif
    for i in range(16):
        x = 26 + i * 3.2
        v = 1 - bhattacharyya_bec(16, 0.5)[i]
        ax.add_patch(Circle((x, 9), 0.9, color=CMAP(v), alpha=a * 0.9))
    footer(ax)


# ----------------------------------------------------------------------------- scene 1: polarization
POL_NMAX = 10
POL_SPLIT, POL_HOLD = 5, 1
POL_START, POL_END = 6, 26
POL_FRAMES = POL_START + POL_NMAX * (POL_SPLIT + POL_HOLD) + POL_END
CAPS = [1 - bhattacharyya_bec(2 ** n, 0.5) for n in range(POL_NMAX + 1)]


def scene_polar(fig, ax, k, K):
    header(ax, 0, "Channel polarization",
           "Combine N copies of a channel W (here BEC, ε = 0.5): the N synthetic bit-channels drift to "
           "I ≈ 1 (perfect) or I ≈ 0 (useless).")
    # determine state
    if k < POL_START:
        n, t = 0, 0.0
    else:
        kk = k - POL_START
        step = kk // (POL_SPLIT + POL_HOLD)
        if step >= POL_NMAX:
            n, t = POL_NMAX, 1.0
        else:
            n, t = step, ease((kk % (POL_SPLIT + POL_HOLD)) / POL_SPLIT)
    final = k >= POL_START + POL_NMAX * (POL_SPLIT + POL_HOLD)

    if n < POL_NMAX and t > 0:
        P, C = CAPS[n], CAPS[n + 1]
        Nc = len(C)
        xp = np.repeat((np.arange(len(P)) + 0.5) / len(P), 2)
        xc = (np.arange(Nc) + 0.5) / Nc
        xs, ys = xp + t * (xc - xp), np.repeat(P, 2) + t * (C - np.repeat(P, 2))
        Nshow = Nc if t > 0.5 else len(P)
    else:
        nn = n if not (n < POL_NMAX and t > 0) else n
        C = CAPS[nn]
        xs, ys = (np.arange(len(C)) + 0.5) / len(C), C
        Nshow = len(C)

    a1 = fig.add_axes([0.065, 0.11, 0.57, 0.575]); style_axes(a1)
    a1.set_xlim(0, 1); a1.set_ylim(-0.04, 1.04)
    a1.set_xlabel("bit-channel index  i / N", fontsize=8)
    a1.set_ylabel("capacity  I(W$_N^{(i)}$)", fontsize=8)
    a1.grid(color=GRID, lw=0.5, alpha=0.6)
    size = max(3, 70 / np.sqrt(len(xs)))
    if final:
        Kinfo = Nshow // 2
        order = np.argsort(-ys, kind="stable")
        info = np.zeros(len(ys), bool); info[order[:Kinfo]] = True
        ft = ease((k - (POL_START + POL_NMAX * (POL_SPLIT + POL_HOLD))) / 10)
        cols = [CMAP(v) for v in ys]
        tgt = [matplotlib.colors.to_rgba(GREEN if f else RED) for f in info]
        cols = [tuple(np.array(c) * (1 - ft) + np.array(g) * ft) for c, g in zip(cols, tgt)]
        a1.scatter(xs, ys, s=size, c=cols, lw=0)
    else:
        a1.scatter(xs, ys, s=size, c=ys, cmap=CMAP, vmin=0, vmax=1, lw=0)

    # right panel
    ax.text(68, 37.5, f"N = 2$^{{{int(np.log2(Nshow))}}}$ = {Nshow}", fontsize=17, color=FG, weight="bold")
    good = np.mean(ys > 0.9) * 100; bad = np.mean(ys < 0.1) * 100
    ax.text(68, 32.5, f"I > 0.9 :  {good:4.1f} %", fontsize=10, color=GREEN, family="monospace")
    ax.text(68, 29.3, f"I < 0.1 :  {bad:4.1f} %", fontsize=10, color=RED, family="monospace")
    ax.text(68, 26.1, f"in between: {100 - good - bad:4.1f} %", fontsize=10, color=MID, family="monospace")
    a2 = fig.add_axes([0.685, 0.13, 0.27, 0.27]); style_axes(a2)
    hist, edges = np.histogram(ys, bins=10, range=(0, 1))
    a2.bar((edges[:-1] + edges[1:]) / 2, hist / len(ys), width=0.09,
           color=[CMAP(v) for v in (edges[:-1] + 0.05)])
    a2.set_ylim(0, 1); a2.set_xlim(0, 1)
    a2.set_xticks([0, 0.5, 1]); a2.set_yticks([0, 0.5, 1])
    a2.set_title("distribution of I", fontsize=7.5, color=MUTED, pad=2)
    if final:
        ft = ease((k - (POL_START + POL_NMAX * (POL_SPLIT + POL_HOLD))) / 10)
        ax.text(3, 40.4, "→ put the K data bits on the best channels; freeze the rest to 0 (known to the decoder)",
                fontsize=8.8, color=FG, alpha=ft, weight="bold")
        ax.add_patch(Circle((70, 3.3), 0.8, color=GREEN, alpha=ft))
        ax.text(71.5, 3.3, "information", fontsize=8, color=FG, va="center", alpha=ft)
        ax.add_patch(Circle((82, 3.3), 0.8, color=RED, alpha=ft))
        ax.text(83.5, 3.3, "frozen", fontsize=8, color=FG, va="center", alpha=ft)


# ----------------------------------------------------------------------------- scene 2: encoding
N8, K8 = 8, 4
FROZEN8 = get_frozen_mask(N8, K8, 0.0)
INFO8 = np.where(~FROZEN8)[0]
DATA8 = np.array([1, 0, 1, 1], np.uint8)
U8 = np.zeros(N8, np.uint8); U8[INFO8] = DATA8
STAGES = [U8.copy()]
for h in (1, 2, 4):
    v = STAGES[-1].copy()
    for j in range(N8):
        if (j // h) % 2 == 0:
            v[j] ^= v[j + h]
    STAGES.append(v)
X8 = STAGES[-1]
assert (X8 == encode(U8[None])[0]).all()

ENC_COLS = [18, 34, 50, 66]
ROW_Y = [37.0 - i * 4.45 for i in range(N8)]
ENC_INTRO, ENC_STAGE, ENC_MAP, ENC_HOLD = 8, 14, 10, 16
ENC_FRAMES = ENC_INTRO + 3 * ENC_STAGE + ENC_MAP + ENC_HOLD


def bit_node(ax, x, y, b, alpha=1.0, frozen=False, hl=False):
    if frozen:
        ax.add_patch(Circle((x, y), 1.45, fc=PANEL, ec=MUTED, lw=1, alpha=alpha, ls="--"))
        ax.text(x, y, str(b), ha="center", va="center", fontsize=8.5, color=MUTED, alpha=alpha)
        return
    fc = BLUE if b else PANEL
    ax.add_patch(Circle((x, y), 1.45, fc=fc, ec=AMBER if hl else (BLUE), lw=1.6 if hl else 1, alpha=alpha))
    ax.text(x, y, str(b), ha="center", va="center", fontsize=8.5, color=BG if b else FG, weight="bold", alpha=alpha)


def scene_encode(fig, ax, k, K):
    header(ax, 1, "Encoding   x = u · F$^{\\otimes n}$,   F = [[1,0],[1,1]]",
           f"N = 8, K = 4: data {''.join(map(str, DATA8))} on the 4 best rows "
           f"({', '.join(str(int(i)) for i in INFO8)}), frozen rows = 0.  log₂N XOR stages → (N/2)·log₂N XORs.")
    a_in = ease(k / ENC_INTRO)
    # input labels
    for i in range(N8):
        lab = f"u{i}"
        ax.text(ENC_COLS[0] - 5.2, ROW_Y[i], lab, ha="right", va="center", fontsize=8.5,
                color=MUTED if FROZEN8[i] else GREEN, alpha=a_in, family="monospace")
        ax.text(ENC_COLS[0] - 3.2, ROW_Y[i], "F" if FROZEN8[i] else "D", ha="center", va="center", fontsize=7,
                color=RED if FROZEN8[i] else GREEN, alpha=a_in, weight="bold")
    # stages
    kk = k - ENC_INTRO
    for s, h in enumerate((1, 2, 4)):
        st = (kk - s * ENC_STAGE) / ENC_STAGE        # progress of this stage
        if st <= 0:
            continue
        line_a = ease(st / 0.55)
        active = st < 1.0
        c0, c1 = ENC_COLS[s], ENC_COLS[s + 1]
        col = AMBER if active else GRID
        for j in range(N8):
            ax.plot([c0 + 1.45, c0 + 1.45 + (c1 - c0 - 2.9) * line_a], [ROW_Y[j]] * 2, color=col, lw=1.2, zorder=1)
            if (j // h) % 2 == 0:
                xo = c0 + 0.62 * (c1 - c0)
                xe = c0 + 1.2 + (xo - c0 - 1.2) * line_a
                ye = ROW_Y[j + h] + (ROW_Y[j] - ROW_Y[j + h]) * line_a
                ax.plot([c0 + 1.2, xe], [ROW_Y[j + h], ye], color=col, lw=1.2, zorder=1)
                if line_a > 0.95:
                    ax.text(xo, ROW_Y[j] + 0.05, "⊕", ha="center", va="center", fontsize=12,
                            color=AMBER if active else MUTED, zorder=3,
                            bbox=dict(boxstyle="circle,pad=0.0", fc=BG, ec="none"))
        if active:
            ax.text((c0 + c1) / 2, 2.6, f"stage {s + 1}:  x[j] ^= x[j+{h}]", ha="center", fontsize=8, color=AMBER)
    # nodes
    for i in range(N8):
        bit_node(ax, ENC_COLS[0], ROW_Y[i], U8[i], a_in, frozen=FROZEN8[i])
    for s in range(3):
        st = (kk - s * ENC_STAGE) / ENC_STAGE
        if st > 0.6:
            na = ease((st - 0.6) / 0.3)
            for i in range(N8):
                bit_node(ax, ENC_COLS[s + 1], ROW_Y[i], STAGES[s + 1][i], na, hl=(st < 1.0))
    # output + BPSK
    mt = (kk - 3 * ENC_STAGE) / ENC_MAP
    if mt > 0:
        ma = ease(mt)
        for i in range(N8):
            ax.text(ENC_COLS[3] + 3.6, ROW_Y[i], f"x{i}", ha="left", va="center", fontsize=8.5, color=BLUE,
                    family="monospace", alpha=ma)
            ax.annotate("", xy=(80.5, ROW_Y[i]), xytext=(74.5, ROW_Y[i]),
                        arrowprops=dict(arrowstyle="->", color=MUTED, lw=0.9, alpha=ma))
            s_val = 1 - 2 * int(X8[i])
            ax.text(84, ROW_Y[i], f"{s_val:+d}", ha="center", va="center", fontsize=9.5,
                    color=FG, weight="bold", alpha=ma, family="monospace")
        ax.text(84, 41.0, "BPSK", ha="center", fontsize=8.5, color=MUTED, alpha=ma)
        ax.text(84, 39.2, "s = 1 − 2x", ha="center", fontsize=7.5, color=MUTED, alpha=ma)
        ax.text(93, ROW_Y[3] - 2.2, "→ AWGN\nchannel", ha="center", va="center", fontsize=8.5, color=AMBER, alpha=ma)
    footer(ax)


# ----------------------------------------------------------------------------- scene 3: SC decoding
EBN0_DEMO = 1.0
SIG2 = 1 / (2 * (K8 / N8) * 10 ** (EBN0_DEMO / 10))


def rnd(v):
    r = round(float(v), 1)
    return 0.0 if r == 0 else r


def sc_trace(L, frozen):
    ev = []

    def rec(d, kidx, Lv, off, op):
        ev.append(("show", d, kidx, list(Lv), op))
        n = len(Lv)
        if n == 1:
            u = 0 if frozen[off] else int(Lv[0] < 0)
            ev.append(("leaf", d, kidx, u, off))
            return [u], [u]
        h = n // 2
        La, Lb = Lv[:h], Lv[h:]
        Lf = [rnd(np.sign(a) * np.sign(b) * min(abs(a), abs(b))) for a, b in zip(La, Lb)]
        ua, va = rec(d + 1, 2 * kidx, Lf, off, "f")
        Lg = [rnd(b + (1 - 2 * v) * a) for a, b, v in zip(La, Lb, va)]
        ub, vb = rec(d + 1, 2 * kidx + 1, Lg, off + h, "g")
        beta = [x ^ y for x, y in zip(va, vb)] + vb
        ev.append(("beta", d, kidx, beta))
        return ua + ub, beta

    u, x = rec(0, 0, list(L), 0, None)
    return ev, u


def pick_demo_noise():
    s = 1 - 2.0 * X8
    for seed in range(5000):
        r = np.random.default_rng(seed)
        y = s + np.sqrt(SIG2) * r.standard_normal(N8)
        L = [rnd(2 * v / SIG2) for v in y]
        flips = [i for i in range(N8) if (L[i] < 0) != bool(X8[i])]
        if len(flips) != 2 or max(abs(v) for v in L) > 9.4 or min(abs(v) for v in L) < 0.3:
            continue
        ev, u = sc_trace(L, FROZEN8)
        if u == list(U8):
            return L, flips, ev
    raise RuntimeError("no demo noise found")


DEMO_L, DEMO_FLIPS, DEMO_EV = pick_demo_noise()
DEMO_EV = DEMO_EV[1:]                         # root "show" handled by the intro
DEC_INTRO, DEC_EV, DEC_END = 10, 4, 24
DEC_FRAMES = DEC_INTRO + DEC_EV * len(DEMO_EV) + DEC_END
TREE_X0, TREE_W = 2.0, 67.0
LEVEL_Y = [35.0, 26.0, 17.0, 8.0]
BOX_H = 3.6


def node_xy(d, kidx):
    w = TREE_W / 2 ** d
    return TREE_X0 + (kidx + 0.5) * w, LEVEL_Y[d], w - 1.2


def scene_decode(fig, ax, k, K):
    header(ax, 2, "Successive-cancellation (SC) decoding",
           f"Same codeword over AWGN (Eb/N0 = {EBN0_DEMO:.0f} dB). Depth-first walk of the tree: "
           "f to the left child, g to the right, decide bits at the leaves.")
    a_in = ease(k / DEC_INTRO)
    nev = max(0, (k - DEC_INTRO) // DEC_EV + (1 if k >= DEC_INTRO else 0))
    nev = min(nev, len(DEMO_EV))
    done = k >= DEC_INTRO + DEC_EV * len(DEMO_EV)
    shown = {(0, 0): (DEMO_L, None)}
    betas, leaves = {}, {}
    active = (0, 0) if nev == 0 else None
    for e in DEMO_EV[:nev]:
        if e[0] == "show":
            shown[(e[1], e[2])] = (e[3], e[4]); active = (e[1], e[2])
        elif e[0] == "leaf":
            leaves[(e[1], e[2])] = (e[3], e[4]); active = (e[1], e[2])
        else:
            betas[(e[1], e[2])] = e[3]; active = (e[1], e[2])
    if done:
        active = None
    last_kind = DEMO_EV[nev - 1][0] if nev > 0 else "show"

    ax.text(TREE_X0 + 0.5, 39.6, "channel LLRs  L = 2y/σ²", fontsize=8, color=MUTED, alpha=a_in)
    ax.text(TREE_X0 + TREE_W - 0.5, 39.6, "red = bit flipped by the noise", fontsize=8, color=ERR, alpha=a_in, ha="right")
    # edges
    for (d, kidx), (Lv, op) in shown.items():
        if d == 0:
            continue
        px, py, _ = node_xy(d - 1, kidx // 2)
        cx, cy, _ = node_xy(d, kidx)
        is_act = active == (d, kidx) and last_kind == "show"
        col = AMBER if is_act else GRID
        ax.plot([px, cx], [py - BOX_H / 2, cy + BOX_H / 2], color=col, lw=1.6 if is_act else 1.0, zorder=1)
        mx = px + 0.7 * (cx - px); my = (py - BOX_H / 2) + 0.7 * ((cy + BOX_H / 2) - (py - BOX_H / 2))
        ax.text(mx, my, op, ha="center", va="center", fontsize=7.5, color=AMBER if is_act else MUTED,
                weight="bold", zorder=3, bbox=dict(boxstyle="circle,pad=0.15", fc=BG, ec=col, lw=0.8))
        if (d - 1, kidx // 2) in betas or (active == (d, kidx) and last_kind == "beta"):
            pass
    # beta edges flash
    if active is not None and last_kind == "beta" and active[0] > 0:
        d, kidx = active
        px, py, _ = node_xy(d - 1, kidx // 2)
        cx, cy, _ = node_xy(d, kidx)
        ax.plot([px, cx], [py - BOX_H / 2, cy + BOX_H / 2], color=PURPLE, lw=2.0, zorder=2)
    # boxes
    for (d, kidx), (Lv, op) in shown.items():
        cx, cy, w = node_xy(d, kidx)
        is_act = active == (d, kidx)
        ec = AMBER if is_act else GRID
        if is_act and last_kind == "beta":
            ec = PURPLE
        alpha = a_in if d == 0 else 1.0
        ax.add_patch(FancyBboxPatch((cx - w / 2, cy - BOX_H / 2), w, BOX_H, boxstyle="round,pad=0,rounding_size=0.8",
                                    fc=PANEL, ec=ec, lw=1.6 if is_act else 1.0, alpha=alpha, zorder=2))
        n = len(Lv)
        for i, v in enumerate(Lv):
            xx = cx - w / 2 + (i + 0.5) * w / n
            c = FG
            if d == 0 and i in DEMO_FLIPS:
                c = ERR
            ax.text(xx, cy, f"{v:+.1f}", ha="center", va="center", fontsize=8 if n > 1 else 7.5, color=c,
                    family="monospace", alpha=alpha, zorder=3, weight="bold" if (d == 0 and i in DEMO_FLIPS) else None)
        if (d, kidx) in betas:
            b = betas[(d, kidx)]
            ax.text(cx, cy - BOX_H / 2 - 1.3, "β = " + " ".join(map(str, b)), ha="center", va="center",
                    fontsize=7.5, color=PURPLE, family="monospace", zorder=4, weight="bold",
                    bbox=dict(boxstyle="round,pad=0.1", fc=BG, ec="none"))
    # leaves
    for (d, kidx), (u, idx) in leaves.items():
        cx, cy, w = node_xy(d, kidx)
        fz = FROZEN8[idx]
        txt = f"û{idx}={u}"
        ax.text(cx, cy - BOX_H / 2 - 1.6, txt, ha="center", va="center", fontsize=7.5,
                color=MUTED if fz else GREEN, weight="bold", family="monospace")
        ax.text(cx, cy - BOX_H / 2 - 3.6, "frozen" if fz else "info", ha="center", va="center", fontsize=6.5,
                color=RED if fz else GREEN)
    # right panel: rules
    rx = 72.5
    ax.add_patch(FancyBboxPatch((rx - 0.8, 14.2), 26.0, 26.6, boxstyle="round,pad=0,rounding_size=1.2",
                                fc=PANEL, ec=GRID, lw=1, alpha=a_in))
    hi = DEMO_EV[nev - 1] if (nev > 0 and not done) else None
    f_on = hi is not None and hi[0] == "show" and hi[4] == "f"
    g_on = hi is not None and hi[0] == "show" and hi[4] == "g"
    l_on = hi is not None and hi[0] == "leaf"
    b_on = hi is not None and hi[0] == "beta"
    rules = [
        ("f  → left child", r"sign(a)·sign(b)·min(|a|,|b|)", f_on, AMBER),
        ("g  → right child", r"b + (1 − 2β)·a", g_on, AMBER),
        ("leaf", "frozen → 0,  info → sign(L)", l_on, GREEN),
        ("β  partial sums ↑", "[β_L ⊕ β_R ,  β_R]", b_on, PURPLE),
    ]
    for i, (t1, t2, on, c) in enumerate(rules):
        y = 38.0 - i * 6.0
        ax.text(rx, y, t1, fontsize=8.5, color=c if on else FG, weight="bold", alpha=a_in)
        ax.text(rx, y - 2.4, t2, fontsize=7.5, color=c if on else MUTED, alpha=a_in, family="monospace")
    ax.text(rx, 12.0, "(a, b = left / right halves of L)", fontsize=6.5, color=MUTED, alpha=a_in)
    # result row
    ax.text(rx, 7.8, "û", fontsize=9, color=FG, weight="bold", family="monospace")
    ax.text(rx, 4.6, "u", fontsize=9, color=MUTED, weight="bold", family="monospace")
    uhat = {idx: u for (u, idx) in leaves.values()}
    for i in range(N8):
        xx = rx + 3.2 + i * 2.75
        ax.text(xx, 7.8, str(uhat[i]) if i in uhat else "·", fontsize=9, ha="center",
                color=(MUTED if FROZEN8[i] else GREEN) if i in uhat else MUTED, family="monospace", weight="bold")
        ax.text(xx, 4.6, str(U8[i]), fontsize=9, ha="center", color=MUTED, family="monospace")
    if done:
        ft = ease((k - (DEC_INTRO + DEC_EV * len(DEMO_EV))) / 8)
        ax.text(rx, 1.6, f"✓ decoded — {len(DEMO_FLIPS)} channel errors corrected", fontsize=7.8,
                color=GREEN, weight="bold", alpha=ft)


# ----------------------------------------------------------------------------- scene 4: BER / FER
BER_DRAW, BER_HOLD = 36, 32
BER_FRAMES = BER_DRAW + BER_HOLD
RES = None


def qfunc(x):
    from math import erfc, sqrt
    return 0.5 * erfc(x / sqrt(2))


def interp_curve(xs, ys, xmax):
    xs, ys = np.asarray(xs), np.asarray(ys)
    m = ys > 0
    xs, ys = xs[m], ys[m]
    if xmax <= xs[0]:
        return xs[:1], ys[:1]
    keep = xs <= xmax
    xo, yo = list(xs[keep]), list(ys[keep])
    if xmax < xs[-1]:
        j = np.searchsorted(xs, xmax)
        t = (xmax - xs[j - 1]) / (xs[j] - xs[j - 1])
        xo.append(xmax); yo.append(10 ** (np.log10(ys[j - 1]) + t * (np.log10(ys[j]) - np.log10(ys[j - 1]))))
    return np.array(xo), np.array(yo)


def gain_at(target, xs, ys):
    xs, ys = np.asarray(xs), np.asarray(ys)
    for j in range(1, len(xs)):
        if ys[j - 1] >= target > ys[j] > 0:
            t = (np.log10(target) - np.log10(ys[j - 1])) / (np.log10(ys[j]) - np.log10(ys[j - 1]))
            return xs[j - 1] + t * (xs[j] - xs[j - 1])
    return None


def scene_ber(fig, ax, k, K):
    r = RES
    header(ax, 3, "Performance: BER / FER",
           f"Monte-Carlo, N = {r['N']}, K = {r['K']} (R = ½), BPSK over AWGN, SC decoder (min-sum f). "
           "This is the curve the FPGA must reproduce.")
    xs = np.array(r["ebn0"])
    xmax = xs[0] + (xs[-1] - xs[0]) * ease(k / BER_DRAW)
    a1 = fig.add_axes([0.075, 0.12, 0.56, 0.6]); style_axes(a1)
    a1.set_yscale("log"); a1.set_xlim(-0.2, 9.2); a1.set_ylim(1e-6, 1)
    a1.set_xlabel("Eb/N0 [dB]", fontsize=8); a1.set_ylabel("error rate", fontsize=8)
    a1.grid(color=GRID, lw=0.5, alpha=0.6, which="major")
    ex = np.linspace(0, 9.2, 200)
    a1.plot(ex, [qfunc(np.sqrt(2 * 10 ** (e / 10))) for e in ex], ls="--", color=MUTED, lw=1.2,
            label="uncoded BPSK (BER)")
    a1.axvline(0.187, color=MUTED, ls=":", lw=1.2)
    a1.text(0.3, 2.2e-6, "Shannon limit\nR=½ (0.19 dB)", color=MUTED, fontsize=6.5)
    bx, by = interp_curve(xs, r["ber"], xmax)
    fx, fy = interp_curve(xs, r["fer"], xmax)
    a1.plot(fx, fy, "-", color=NAVY, lw=2, label="polar SC — FER")
    a1.plot(bx, by, "-", color=BLUE, lw=2, label="polar SC — BER")
    mk = xs <= xmax + 1e-9
    a1.plot(xs[mk][np.array(r["fer"])[mk] > 0], np.array(r["fer"])[mk][np.array(r["fer"])[mk] > 0], "o", color=NAVY, ms=3.5)
    a1.plot(xs[mk][np.array(r["ber"])[mk] > 0], np.array(r["ber"])[mk][np.array(r["ber"])[mk] > 0], "o", color=BLUE, ms=3.5)
    leg = a1.legend(fontsize=7, loc="upper right", facecolor=PANEL, edgecolor=GRID, labelcolor=FG)
    # right panel
    frames_sim = int(np.sum(np.array(r["frames"])[mk]))
    rx = 67.5
    ax.text(rx, 37.5, "Monte-Carlo", fontsize=9, color=MUTED)
    ax.text(rx, 33.8, f"{frames_sim:,} frames", fontsize=14, color=FG, weight="bold")
    ax.text(rx, 30.6, f"{frames_sim * r['N'] / 1e6:,.0f} M coded bits", fontsize=8.5, color=MUTED)
    ax.text(rx, 28.0, f"frozen set: Bhattacharyya @ {r['design_snr_db']:.0f} dB design SNR", fontsize=7, color=MUTED)
    g_coded = gain_at(1e-4, xs, r["ber"])
    ex_u = gain_at(1e-4, ex, [qfunc(np.sqrt(2 * 10 ** (e / 10))) for e in ex])
    if k >= BER_DRAW and g_coded is not None and ex_u is not None:
        ft = ease((k - BER_DRAW) / 10)
        ax.text(rx, 24.6, "coding gain @ BER 10⁻⁴", fontsize=9, color=MUTED, alpha=ft)
        ax.text(rx, 20.4, f"≈ {ex_u - g_coded:.1f} dB", fontsize=18, color=GREEN, weight="bold", alpha=ft)
        ax.text(rx, 16.6, f"({ex_u:.1f} dB uncoded → {g_coded:.1f} dB coded)", fontsize=7.5, color=MUTED, alpha=ft)
        ax.text(rx, 10.5, "next: same curve from the FPGA,\nbit-exact vs. this reference", fontsize=8,
                color=BLUE, alpha=ft)
    footer(ax)


# ----------------------------------------------------------------------------- timeline + render
TITLE_FRAMES, OUTRO_FRAMES = 18, 20
TIMELINE = (
    [("title", i, TITLE_FRAMES) for i in range(TITLE_FRAMES)]
    + [("polar", i, POL_FRAMES) for i in range(POL_FRAMES)]
    + [("enc", i, ENC_FRAMES) for i in range(ENC_FRAMES)]
    + [("dec", i, DEC_FRAMES) for i in range(DEC_FRAMES)]
    + [("ber", i, BER_FRAMES) for i in range(BER_FRAMES)]
    + [("outro", i, OUTRO_FRAMES) for i in range(OUTRO_FRAMES)]
)


def render(args):
    idx, (name, k, K), outdir = args
    fig, ax = new_canvas()
    if name == "title":
        scene_title(ax, k, K)
    elif name == "outro":
        scene_title(ax, k, K, outro=True)
    elif name == "polar":
        scene_polar(fig, ax, k, K)
    elif name == "enc":
        scene_encode(fig, ax, k, K)
    elif name == "dec":
        scene_decode(fig, ax, k, K)
    elif name == "ber":
        scene_ber(fig, ax, k, K)
    fig.savefig(os.path.join(outdir, f"f{idx:04d}.png"), facecolor=BG)
    plt.close(fig)


def init(res):
    global RES
    RES = res


def main():
    res_path, out = sys.argv[1], sys.argv[2]
    only = sys.argv[3] if len(sys.argv) > 3 else None
    res = json.load(open(res_path))
    outdir = tempfile.mkdtemp(prefix="polar_frames_")
    items = [(i, t, outdir) for i, t in enumerate(TIMELINE) if only is None or t[0] == only]
    with Pool(os.cpu_count(), initializer=init, initargs=(res,)) as p:
        p.map(render, items, chunksize=8)
    print(f"{len(items)} frames ({len(items) / FPS:.1f} s) -> {outdir}")
    if only:
        return
    pal = os.path.join(outdir, "palette.png")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(outdir, "f%04d.png"),
                    "-vf", "palettegen=max_colors=96:stats_mode=full", pal], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(outdir, "f%04d.png"),
                    "-i", pal, "-lavfi", "paletteuse=dither=none:diff_mode=rectangle", "-loop", "0", out], check=True)
    print(out, os.path.getsize(out) / 1e6, "MB")


if __name__ == "__main__":
    main()
