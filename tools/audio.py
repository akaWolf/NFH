"""AudioClip reading, and just enough FSB5 to get the samples out.

Unity 5 wraps every clip in an FMOD FSB5 container inside a sibling .resource
file. The game is almost entirely PCM16, which unwraps straight to WAV; the
handful of Vorbis clips are written out as raw .fsb, since FMOD stores those
with its setup headers stripped and rebuilding them is a separate problem.
"""
import os, struct

# FSB5 sample formats
FSB_PCM8, FSB_PCM16, FSB_PCM24, FSB_PCM32, FSB_PCMFLOAT = 1, 2, 3, 4, 5
FSB_GCADPCM, FSB_IMAADPCM, FSB_VAG, FSB_HEVAG, FSB_XMA = 6, 7, 8, 9, 10
FSB_MPEG, FSB_CELT, FSB_AT9, FSB_XWMA, FSB_VORBIS = 11, 12, 13, 14, 15

FSB_FORMAT_NAMES = {
    FSB_PCM8: 'PCM8', FSB_PCM16: 'PCM16', FSB_PCM24: 'PCM24', FSB_PCM32: 'PCM32',
    FSB_PCMFLOAT: 'PCMFLOAT', FSB_GCADPCM: 'GCADPCM', FSB_IMAADPCM: 'IMAADPCM',
    FSB_VAG: 'VAG', FSB_HEVAG: 'HEVAG', FSB_XMA: 'XMA', FSB_MPEG: 'MPEG',
    FSB_CELT: 'CELT', FSB_AT9: 'AT9', FSB_XWMA: 'XWMA', FSB_VORBIS: 'VORBIS',
}

FSB_FREQUENCIES = [0, 8000, 11000, 11025, 16000, 22050, 24000, 32000,
                   44100, 48000, 96000]

# UnityEngine.AudioCompressionFormat
COMPRESSION_NAMES = {0: 'PCM', 1: 'Vorbis', 2: 'ADPCM', 3: 'MP3', 4: 'VAG',
                     5: 'HEVAG', 6: 'XMA', 7: 'AAC', 8: 'GCADPCM', 9: 'ATRAC9'}


class AudioClip:
    __slots__ = ('name', 'load_type', 'channels', 'frequency', 'bits',
                 'length', 'source', 'offset', 'size', 'compression')

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    @property
    def compression_name(self):
        return COMPRESSION_NAMES.get(self.compression, 'fmt%d' % self.compression)

    def __repr__(self):
        return '<AudioClip %s %dch %dHz %.2fs %s>' % (
            self.name, self.channels, self.frequency, self.length,
            self.compression_name)


def read_audioclip(sf, obj):
    from unityser import Reader
    r = Reader(sf.body(obj), 0)
    name = r.astr()
    load_type = r.i32(); channels = r.i32(); frequency = r.i32(); bits = r.i32()
    length = r.u('f', 4)
    r.u8(); r.align(4)                       # m_IsTrackerFormat
    r.i32()                                  # m_SubsoundIndex
    r.u8(); r.u8(); r.u8(); r.align(4)       # preload, background, legacy3D
    source = r.astr()
    offset = r.u('Q', 8); size = r.u('Q', 8)
    compression = r.i32()
    return AudioClip(name=name, load_type=load_type, channels=channels,
                     frequency=frequency, bits=bits, length=length,
                     source=source, offset=offset, size=size,
                     compression=compression)


def find_resource(name, dirs):
    """A .resource can sit beside its serialized file or in the sibling tree —
    the APK and OBB halves of assets/bin/Data reference each other."""
    if not name:
        return None
    base = os.path.basename(name)
    for d in ([dirs] if isinstance(dirs, str) else dirs):
        p = os.path.join(d, base)
        if os.path.exists(p):
            return p
    return None


def clip_bytes(clip, resource_dirs):
    """the raw FSB5 container for this clip, or b'' if the resource is missing"""
    p = find_resource(clip.source, resource_dirs)
    if not p:
        return b''
    with open(p, 'rb') as f:
        f.seek(clip.offset)
        return f.read(clip.size)


class FsbSample:
    __slots__ = ('name', 'frequency', 'channels', 'samples', 'data')

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def parse_fsb5(buf):
    """-> (mode, [FsbSample]). Only the header walk; samples keep their payload
    exactly as stored."""
    if buf[:4] != b'FSB5':
        raise ValueError('not an FSB5 container')
    (version, num_samples, hdr_size, name_size,
     data_size, mode) = struct.unpack_from('<IIIIII', buf, 4)
    pos = 60 if version == 1 else 64
    headers = []
    for _ in range(num_samples):
        raw, = struct.unpack_from('<Q', buf, pos); pos += 8
        more = raw & 1
        freq_idx = (raw >> 1) & 0xf
        channels = ((raw >> 5) & 1) + 1
        offset = ((raw >> 6) & 0x0fffffff) * 16
        nsamples = (raw >> 34) & 0x3fffffff
        frequency = FSB_FREQUENCIES[freq_idx] if freq_idx < len(FSB_FREQUENCIES) else 0
        while more:
            chunk, = struct.unpack_from('<I', buf, pos); pos += 4
            more = chunk & 1
            size = (chunk >> 1) & 0xffffff
            ctype = (chunk >> 25) & 0x7f
            if ctype == 1 and size >= 1:                 # CHANNELS
                channels = buf[pos]
            elif ctype == 2 and size >= 4:               # FREQUENCY
                frequency, = struct.unpack_from('<I', buf, pos)
            pos += size
        headers.append((offset, nsamples, frequency, channels))

    names = [None] * num_samples
    if name_size:
        base = 60 + hdr_size if version == 1 else 64 + hdr_size
        for i in range(num_samples):
            off, = struct.unpack_from('<I', buf, base + 4 * i)
            p = base + off
            n = buf[p]
            names[i] = buf[p + 1:p + 1 + n].decode('utf-8', 'replace')

    data_start = (60 if version == 1 else 64) + hdr_size + name_size
    out = []
    for i, (off, ns, fq, ch) in enumerate(headers):
        end = headers[i + 1][0] if i + 1 < len(headers) else data_size
        out.append(FsbSample(name=names[i], frequency=fq, channels=ch,
                             samples=ns,
                             data=buf[data_start + off:data_start + end]))
    return mode, out


def write_wav(path, channels, frequency, bits, pcm):
    """RIFF/WAVE, integer PCM."""
    block = channels * bits // 8
    hdr = b'RIFF' + struct.pack('<I', 36 + len(pcm)) + b'WAVE'
    hdr += b'fmt ' + struct.pack('<IHHIIHH', 16, 1, channels, frequency,
                                 frequency * block, block, bits)
    hdr += b'data' + struct.pack('<I', len(pcm))
    with open(path, 'wb') as f:
        f.write(hdr); f.write(pcm)
