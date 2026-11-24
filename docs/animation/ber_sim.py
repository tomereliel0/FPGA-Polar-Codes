import json, sys, time
import numpy as np
from polar_core import get_frozen_mask, encode, sc_decode

N, K = 1024, 512
R = K / N
design = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0
snrs = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
frozen = get_frozen_mask(N, K, design)
info = ~frozen
rng = np.random.default_rng(2026)
B = 2000
res = {"N": N, "K": K, "design_snr_db": design, "ebn0": [], "ber": [], "fer": [], "frames": []}
t0 = time.time()
for ebn0 in snrs:
    sigma = np.sqrt(1 / (2 * R * 10 ** (ebn0 / 10)))
    be = fe = frames = 0
    while fe < (300 if ebn0 < 3.6 else 150) and frames < 2_400_000:
        u = np.zeros((B, N), np.uint8)
        u[:, info] = rng.integers(0, 2, (B, K), dtype=np.uint8)
        y = 1 - 2.0 * encode(u) + sigma * rng.standard_normal((B, N))
        uh, _ = sc_decode(2 * y / sigma ** 2, frozen)
        err = (uh[:, info] != u[:, info])
        be += err.sum(); fe += err.any(1).sum(); frames += B
    res["ebn0"].append(ebn0); res["ber"].append(be / (frames * K)); res["fer"].append(fe / frames); res["frames"].append(frames)
    print(f"{ebn0:.1f} dB  BER={be/(frames*K):.3e}  FER={fe/frames:.3e}  frames={frames}  t={time.time()-t0:.0f}s", flush=True)
json.dump(res, open(f"ber_design{design}.json", "w"), indent=1)
