#!/usr/bin/env python3
"""Which level track the PC video plays: per window of the video's audio the
remaster's clip (ingame1/ingame2 x normal/slow/fast, audio/s1/*.ogg) with the
highest normalized cross-correlation and its place in the clip — a run of
windows whose place advances with the video's clock is that clip playing.

    nix-shell -p ffmpeg python3Packages.numpy --run \
      "python3 tools/pcref/music_tracks.py ~/nfh-bench/pcref/pc_s1_all_720.mp4 369.6 540.3 [win hop]"

Read on 2026-10-04 over the fourteen Season 1 episodes (tools/pcref/
episodes_s1.json): each plays one set, ingame1 (E01, E04, E06, E07, E08,
E13) or ingame2 (E02, E03, E05, E09-E12, E14); the slow clip takes over at
the normal clip's place during E08-E14's sneaking walks and the fast one in
E11 and E13's pet alarms; each trick's jingle holds the track (E02: its
place 2.4-2.6 s behind after each of five jingles). The level start: the
clap (jingle_levelstart) at the level's load and the track from its top as
the clap's 15.0 s end (E09 15.04, E10 15.02, E11 14.87, E13 15.03 s after
the clap's start); E02 opened 5.6 s into its clip there."""
import os
import subprocess
import sys
import numpy as np

SR = 4000
AUD = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'audio', 's1')


def decode(path, start=None, dur=None):
    cmd = ['ffmpeg', '-v', 'quiet']
    if start is not None:
        cmd += ['-ss', str(start)]
    if dur is not None:
        cmd += ['-t', str(dur)]
    cmd += ['-i', path, '-ac', '1', '-ar', str(SR), '-f', 's16le', '-']
    raw = subprocess.run(cmd, capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    return x - x.mean() if len(x) else x


def best_place(w, clip):
    """(max normalized cross-correlation, the clip's second there); the clip
    looped once so a window over its end matches"""
    tr = np.concatenate([clip, clip[:len(w)]])
    n = len(tr) + len(w)
    nfft = 1 << (n - 1).bit_length()
    c = np.fft.irfft(np.fft.rfft(tr, nfft) * np.conj(np.fft.rfft(w, nfft)), nfft)[:len(tr) - len(w) + 1]
    cs = np.concatenate([[0], np.cumsum(tr ** 2)])
    e = np.sqrt(np.maximum(cs[len(w):len(tr) + 1] - cs[:len(tr) - len(w) + 1], 1e-9)) \
        * np.sqrt((w ** 2).sum() + 1e-9)
    r = c / e
    i = int(np.argmax(r))
    return float(r[i]), i / SR


def main(argv):
    video, t0, t1 = argv[0], float(argv[1]), float(argv[2])
    win = float(argv[3]) if len(argv) > 3 else 6.0
    hop = float(argv[4]) if len(argv) > 4 else 3.0
    clips = {'%d_%s' % (k, m): decode('%s/ingame%d_%s.ogg' % (AUD, k, m))
             for k in (1, 2) for m in ('normal', 'slow', 'fast')}
    seg = decode(video, t0, t1 - t0)
    W = int(win * SR)
    pos = 0
    while pos + W <= len(seg):
        w = seg[pos:pos + W]
        w = w - w.mean()
        res = sorted(((nm,) + best_place(w, c) for nm, c in clips.items()), key=lambda x: -x[1])
        print('%7.1f  %s  %.2f @%.1f | %s' % (t0 + pos / SR, res[0][0], res[0][1], res[0][2],
                                            ' '.join('%s=%.2f' % (nm, r) for nm, r, _p in res[1:3])))
        pos += int(hop * SR)


if __name__ == '__main__':
    main(sys.argv[1:])
