#!/usr/bin/env python3
"""Generate an allRGB image -- or an animation of it growing.

A Python port and extension of fejesjoco's allRGB program (allcolors.cs
in this repo) -- the C# from his post "All RGB colors in one image"
(March 2, 2014), his answer to Code Golf Stack Exchange #22144. Every
color is used exactly once. Colors are placed one at a time at the empty
pixel where each best matches its already-placed neighbors, so the image
grows outward from its seed(s) as an organic bloom of color.

fejesjoco released the original under the GPL. As a translation of it,
this file is a derivative work and is likewise GPL-licensed; see the
README for the repository's mixed-license layout.

The palette is width*height colors, taken as a near-cubic grid of the
RGB cube (e.g. 1080x1080 -> a 100x108x108 grid), so any image size
works -- it need not be a perfect cube.

Output:
  -o name.png   a still image
  -o name.mp4   an animation of the growth (also .gif, .mov, .webm)

Structure knobs:
  --order M   color traversal: shuffle (speckly), walk (smooth gradient
              fields), hue (rainbow flow)
  --seeds N   number of bloom centers
  --average   match the average of the neighbors, not the single best
  --seed S    fix the random stream for reproducible output
"""

import argparse

import numpy as np
from PIL import Image

# 8-connected neighbor offsets
_OFFSETS = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
            if (dy, dx) != (0, 0)]
_VIDEO_EXT = (".mp4", ".gif", ".mov", ".webm", ".avi")


def factor3(total):
    """Factor `total` into three near-equal integers (per-channel counts)."""
    small = [d for d in range(1, int(total ** 0.5) + 1) if total % d == 0]
    divisors = sorted(set(small) | {total // d for d in small})
    best = None
    for nr in divisors:
        if nr ** 3 > total:
            break
        rem = total // nr
        for ng in divisors:
            if ng < nr:
                continue
            if ng * ng > rem:
                break
            if rem % ng == 0:
                nb = rem // ng                 # nr <= ng <= nb
                if best is None or nb - nr < best[0]:
                    best = (nb - nr, (nr, ng, nb))
    return best[1]


def make_colors(counts):
    """Build every color of a near-cubic RGB grid with the given counts."""
    chans = [np.array([0], dtype=np.int16) if n == 1
             else (np.arange(n) * 255 // (n - 1)).astype(np.int16)
             for n in counts]
    grid = np.meshgrid(chans[0], chans[1], chans[2], indexing="ij")
    return np.stack(grid, axis=-1).reshape(-1, 3)


def order_colors(colors, counts, mode, rng):
    """Reorder the color list, which controls how the image flows.

    shuffle: random -- high-contrast, speckly.
    walk:    3D boustrophedon through the color grid; consecutive colors
             differ by one step in one channel -- smooth gradient fields.
    hue:     sorted around the hue wheel, then by brightness -- rainbow flow.
    """
    if mode == "shuffle":
        rng.shuffle(colors)
        return colors
    if mode == "walk":
        nr, ng, nb = counts
        b = np.arange(nb)
        rows = []
        for r in range(nr):
            for g in (range(ng) if r % 2 == 0 else range(ng - 1, -1, -1)):
                seq = b if (r + g) % 2 == 0 else b[::-1]
                rows.append((r * ng + g) * nb + seq)
        return colors[np.concatenate(rows)]
    if mode == "hue":
        c = colors.astype(np.float64) / 255.0
        r, g, b = c[:, 0], c[:, 1], c[:, 2]
        mx, d = c.max(axis=1), c.max(axis=1) - c.min(axis=1)
        h = np.zeros(len(c))
        mr = (d > 0) & (mx == r)
        mg = (d > 0) & (mx == g) & ~mr
        mb = (d > 0) & (mx == b) & ~mr & ~mg
        h[mr] = ((g[mr] - b[mr]) / d[mr]) % 6
        h[mg] = (b[mg] - r[mg]) / d[mg] + 2
        h[mb] = (r[mb] - g[mb]) / d[mb] + 4
        return colors[np.lexsort((mx, h))]
    raise ValueError(f"unknown order: {mode}")


def generate(width, height, average=False, nseeds=1, order="shuffle",
             seed=None, progress=None, nframes=0, on_frame=None):
    """Grow an allRGB image; return the final (height, width, 3) uint8 array.

    If nframes>0 and on_frame is given, on_frame(img_copy) is called at
    nframes evenly-spaced points during the growth, plus once at the end.
    """
    total = width * height
    counts = factor3(total)
    rng = np.random.default_rng(seed)

    colors = order_colors(make_colors(counts), counts, order, rng)

    img = np.zeros((height, width, 3), dtype=np.uint8)
    filled = np.zeros((height, width), dtype=bool)
    slot = np.full((height, width), -1, dtype=np.int64)   # frontier index, or -1

    # The frontier: empty pixels next to filled ones, held as parallel arrays
    # with a logical length n. Each slot caches the colors of that pixel's
    # already-placed neighbors, updated incrementally, so scoring a color
    # never has to re-read the image.
    ay = np.empty(total, dtype=np.int64)
    ax = np.empty(total, dtype=np.int64)
    nbr = np.zeros((total, 8, 3), dtype=np.int32)         # neighbor colors
    ncnt = np.zeros(total, dtype=np.int64)                # neighbors per slot
    n = 0
    lane = np.arange(8)
    int_max = np.iinfo(np.int32).max

    # distinct random seed positions
    seed_pos = set()
    while len(seed_pos) < min(nseeds, total):
        seed_pos.add((int(rng.integers(height)), int(rng.integers(width))))
    seed_pos = list(seed_pos)

    frame_step = max(1, total // nframes) if (nframes and on_frame) else 0

    def remove(idx):
        """Swap-remove frontier entry idx with the last live entry."""
        nonlocal n
        n -= 1
        slot[ay[idx], ax[idx]] = -1
        if idx != n:
            ay[idx], ax[idx] = ay[n], ax[n]
            nbr[idx] = nbr[n]
            ncnt[idx] = ncnt[n]
            slot[ay[idx], ax[idx]] = idx

    def place(by, bx, color):
        """Mark (by,bx) filled and fold its color into each empty neighbor."""
        nonlocal n
        img[by, bx] = color
        filled[by, bx] = True
        for oy, ox in _OFFSETS:
            ty, tx = by + oy, bx + ox
            if not (0 <= ty < height and 0 <= tx < width) or filled[ty, tx]:
                continue
            s = slot[ty, tx]
            if s < 0:                          # a new frontier pixel
                s = n
                ay[s], ax[s], ncnt[s] = ty, tx, 0
                slot[ty, tx] = s
                n += 1
            nbr[s, ncnt[s]] = color            # cache the neighbor's color
            ncnt[s] += 1

    if progress:
        print(f"palette {counts[0]}x{counts[1]}x{counts[2]} = "
              f"{total} colors", flush=True)

    for i in range(colors.shape[0]):
        color = colors[i]

        if i < len(seed_pos):
            by, bx = seed_pos[i]
            s = slot[by, bx]
            if s >= 0:                         # seed landed on the frontier
                remove(s)
        else:
            cache = nbr[:n]                            # (n, 8, 3) int32 view
            diff = cache - color                       # (n, 8, 3)
            dist = (diff * diff).sum(axis=2)           # (n, 8)
            valid = lane[None, :] < ncnt[:n, None]     # (n, 8)
            if average:
                score = np.where(valid, dist, 0).sum(axis=1) / ncnt[:n]
            else:
                score = np.where(valid, dist, int_max).min(axis=1)
            # random tie-break among the equally-best pixels
            ties = np.flatnonzero(score == score.min())
            best = int(ties[rng.integers(ties.size)])
            by, bx = int(ay[best]), int(ax[best])
            remove(best)

        place(by, bx, color)

        if frame_step and i % frame_step == 0:
            on_frame(img.copy())
        if progress and i % progress == 0:
            print(f"{i / total:6.1%}  frontier {n}", flush=True)

    if frame_step:
        on_frame(img.copy())
    return img


def main():
    p = argparse.ArgumentParser(
        description="Generate an allRGB image, or an animation of it growing.")
    p.add_argument("-o", "--output", default="allcolors.png",
                   help="output file; a video extension (.mp4/.gif/...) "
                        "produces a growth animation")
    p.add_argument("--width", type=int, default=1000)
    p.add_argument("--height", type=int, default=1000)
    p.add_argument("--seeds", type=int, default=1,
                   help="number of bloom centers")
    p.add_argument("--order", choices=["shuffle", "walk", "hue"],
                   default="shuffle",
                   help="color traversal: shuffle (speckly), "
                        "walk (smooth gradient fields), hue (rainbow flow)")
    p.add_argument("--average", action="store_true",
                   help="match the average of the neighbors, not the best one")
    p.add_argument("--frames", type=int, default=300,
                   help="number of animation frames (video output only)")
    p.add_argument("--fps", type=int, default=30,
                   help="animation frame rate (video output only)")
    p.add_argument("--seed", type=int, default=None,
                   help="seed for reproducible output")
    args = p.parse_args()

    common = dict(average=args.average, nseeds=args.seeds, order=args.order,
                  seed=args.seed, progress=50000)

    if args.output.lower().endswith(_VIDEO_EXT):
        import imageio
        # macro_block_size=1 keeps the exact requested dimensions; the
        # default (16) pads them up to a macroblock multiple
        writer = imageio.get_writer(args.output, fps=args.fps,
                                    macro_block_size=1)
        try:
            img = generate(args.width, args.height, nframes=args.frames,
                           on_frame=writer.append_data, **common)
        finally:
            writer.close()
        unique = np.unique(img.reshape(-1, 3), axis=0).shape[0]
        print(f"wrote {args.output}: {args.width}x{args.height} animation, "
              f"{args.frames} frames; final image has {unique} unique colors")
    else:
        img = generate(args.width, args.height, **common)
        Image.fromarray(img, "RGB").save(args.output)
        unique = np.unique(img.reshape(-1, 3), axis=0).shape[0]
        print(f"wrote {args.output}: {args.width}x{args.height}, "
              f"{unique} unique colors")


if __name__ == "__main__":
    main()
