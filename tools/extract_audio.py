"""Unwrap every AudioClip to WAV (or raw .fsb where FMOD used Vorbis).

    NFH_DATA=/path/to/extraction python3 tools/extract_audio.py out/audio

Standard library only.
"""
import os, sys, re, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
from unityser import SerializedFile
from audio import (read_audioclip, clip_bytes, parse_fsb5, write_wav,
                   FSB_PCM8, FSB_PCM16, FSB_PCM32, FSB_FORMAT_NAMES)
from extract_textures import serialized_files

AUDIOCLIP_CLASS_ID = 83
PCM_BITS = {FSB_PCM8: 8, FSB_PCM16: 16, FSB_PCM32: 32}


def main(outdir):
    paths.check()
    os.makedirs(outdir, exist_ok=True)
    modes = collections.Counter()
    used = collections.Counter()
    wav = fsb = 0
    seconds = 0.0
    problems = []
    for p in serialized_files():
        try:
            sf = SerializedFile(p)
        except Exception:
            continue
        rdirs = (os.path.dirname(p), paths.APK, paths.OBB)
        for o in sf.objects:
            if o['class_id'] != AUDIOCLIP_CLASS_ID:
                continue
            clip = read_audioclip(sf, o)
            name = re.sub(r'[^A-Za-z0-9_.-]', '_', clip.name) or 'unnamed'
            used[name] += 1
            if used[name] > 1:
                name = '%s~%d' % (name, used[name])
            buf = clip_bytes(clip, rdirs)
            if not buf:
                problems.append((clip.name, 'resource %r missing' % clip.source))
                continue
            try:
                mode, samples = parse_fsb5(buf)
            except Exception as e:
                problems.append((clip.name, '%s: %s' % (type(e).__name__, e)))
                continue
            modes[FSB_FORMAT_NAMES.get(mode, 'mode%d' % mode)] += 1
            seconds += clip.length
            if mode in PCM_BITS:
                for i, s in enumerate(samples):
                    suffix = '' if len(samples) == 1 else '~%d' % (i + 1)
                    write_wav(os.path.join(outdir, name + suffix + '.wav'),
                              s.channels or clip.channels,
                              s.frequency or clip.frequency,
                              PCM_BITS[mode], s.data)
                    wav += 1
            else:
                # FMOD strips the Vorbis setup headers; keep the container so it
                # can be handled with a real FSB5 decoder later.
                with open(os.path.join(outdir, name + '.fsb'), 'wb') as f:
                    f.write(buf)
                fsb += 1
    print('wrote %d WAV + %d raw .fsb (%.1f min of audio) -> %s'
          % (wav, fsb, seconds / 60, outdir))
    print('fsb formats:', ', '.join('%s=%d' % kv for kv in modes.most_common()))
    if problems:
        print('\nproblems: %d' % len(problems))
        for a, b in problems[:10]:
            print('   %-28s %s' % (a, b))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else 'audio'))
