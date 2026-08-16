"""Rebuild the FMOD-Vorbis clips (.fsb) that extract_audio.py left
undecoded into plain .ogg files SDL2_mixer can play — the level music and
the outcome jingles ship in this format.

    python3 tools/fsb_to_ogg.py audio/s1 audio/s2

Needs python-fsb5 (https://github.com/HearthSim/python-fsb5) on the
PYTHONPATH and libvorbis; everything it rebuilds decodes with stock ffmpeg.
Already-converted files are skipped.
"""
import os, sys, glob, struct


def _write_float_wav(path, sample):
    """a minimal WAVE_FORMAT_IEEE_FLOAT container around raw f32 frames"""
    data = sample.data
    ch = sample.channels
    rate = sample.frequency
    with open(path, 'wb') as f:
        f.write(b'RIFF' + struct.pack('<I', 36 + len(data)) + b'WAVE')
        f.write(b'fmt ' + struct.pack('<IHHIIHH', 16, 3, ch, rate,
                                      rate * ch * 4, ch * 4, 32))
        f.write(b'data' + struct.pack('<I', len(data)) + data)


def main(dirs):
    try:
        import fsb5
    except ImportError:
        print('python-fsb5 not importable — clone HearthSim/python-fsb5 '
              'and add it to PYTHONPATH')
        return 1
    done = skipped = failed = 0
    for d in dirs:
        for p in sorted(glob.glob(os.path.join(d, '*.fsb'))):
            out = p[:-4] + '.ogg'
            if os.path.exists(out):
                skipped += 1
                continue
            try:
                f = fsb5.FSB5(open(p, 'rb').read())
                # every shipped bank holds exactly one sample
                sample = f.samples[0]
                if f.header.mode == 5:
                    # PCMFLOAT (na2_shout3pool): raw float32 -> a WAVE_FLOAT
                    _write_float_wav(p[:-4] + '.wav', sample)
                else:
                    open(out, 'wb').write(f.rebuild_sample(sample))
                done += 1
            except Exception as e:
                failed += 1
                print('%-40s %s: %s' % (os.path.basename(p),
                                        type(e).__name__, e))
    print('rebuilt %d, skipped %d, failed %d' % (done, skipped, failed))
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:] or ['audio/s1', 'audio/s2']))
