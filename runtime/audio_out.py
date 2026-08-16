"""Frame-keyed sound effects through SDL2_mixer.

The game fires AnimationSound entries as their frame index comes up
(AnimationControllerBase.PlaySound); clips were extracted to WAV by
tools/extract_audio.py. Point NFH_AUDIO at those directories.
"""
import os


def audio_dirs(level_paths=()):
    """the clip search path (viewer decision, mirroring viewer.texture_dirs):
    NFH_AUDIO first, then the season directories with the season of the
    opened levels first — a build's Resources.Load only ever sees its own
    season's clips, and two names differ between the extractions
    (give_take1, wod_ha1: S2 levels reference both), then audio/"""
    env = os.environ.get('NFH_AUDIO')
    dirs = env.split(':') if env else []
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    seasons = ['s1', 's2']
    if any('/s2/' in p.replace('\\', '/') for p in level_paths):
        seasons.reverse()
    for s in seasons:
        dirs.append(os.path.join(root, 'audio', s))
    dirs.append(os.path.join(root, 'audio'))
    return [d for d in dirs if os.path.isdir(d)]


class SoundBank:
    """SDL_mixer scaffolding (no game rule here): the clip cache and the
    channels behind Helpers.PlaySound / the MusicPlayer sources"""

    def __init__(self, mixer, dirs):
        self._mixer = mixer
        self._dirs = dirs
        self._cache = {}

    @classmethod
    def try_open(cls, level_paths=()):
        """open the mixer if SDL audio is available, else None (silent run)"""
        dirs = audio_dirs(level_paths)
        if not dirs:
            return None
        try:
            import sdl2
            from sdl2 import sdlmixer
            if sdl2.SDL_InitSubSystem(sdl2.SDL_INIT_AUDIO) != 0:
                return None
            if sdlmixer.Mix_OpenAudio(44100, sdl2.AUDIO_S16SYS, 2, 1024) != 0:
                return None
            sdlmixer.Mix_AllocateChannels(16)
            return cls(sdlmixer, dirs)
        except Exception:
            return None

    MUSIC_CHANNEL = 15                    # reserved for the MusicPlayer port
    ENTRANCE_CHANNEL = 14                 # MusicPlayer.EntranceSoundSource: its
                                          # own AudioSource, the level track
                                          # starts under it (MusicPlayer.cs:122-135)

    def _load(self, name):
        """the clip named by an AnimationSound.FileName / MusicPlayer clip:
        first <dir>/<name>.wav|.ogg along the season-ordered search path
        (Resources.Load in AnimationSound.LoadClip resolves the same bare
        name under Sound/sfx_hi/ or Sound/NFH2/sfx/ — the two colliding
        names, but_hover1 and na_slip_up1, extract to byte-identical twins,
        so the flat lookup is exact); None is cached for a missing clip"""
        chunk = self._cache.get(name)
        if chunk is None and name not in self._cache:
            path = None
            for d in self._dirs:
                for ext in ('.wav', '.ogg'):
                    p = os.path.join(d, name + ext)
                    if os.path.exists(p):
                        path = p
                        break
                if path:
                    break
            chunk = self._mixer.Mix_LoadWAV(path.encode()) if path else None
            self._cache[name] = chunk
        return chunk

    def play(self, name):
        """one frame-keyed effect on a free channel (Helpers.PlaySound,
        Helpers.cs:452-470 — a null clip is skipped there too — behind
        AnimationControllerBase.PlaySound, cs:191-201)"""
        chunk = self._load(name)
        if chunk:
            self._mixer.Mix_PlayChannel(-1, chunk, 0)

    def play_music(self, name, loop=True, offset=0.0):
        """the MusicPlayer sources: one reserved channel — starting a jingle
        stops the level track first (LevelMusicSource.Stop before every
        PlayEffectsMusic, MusicPlayer.cs:143-166). `offset` starts the clip
        that many seconds in: the port's clock begins at StartGame while
        the original's clap started at scene load, before the title cards
        (viewer decision over the decoded PCM — SDL_mixer has no seek)"""
        chunk = self._load(name)
        if not chunk:
            return
        if offset > 0.0:
            chunk = self._sub_chunk(name, chunk, offset)
            if chunk is None:
                return
        self._mixer.Mix_HaltChannel(self.MUSIC_CHANNEL)
        self._mixer.Mix_PlayChannel(self.MUSIC_CHANNEL, chunk,
                                    -1 if loop else 0)

    def _sub_chunk(self, name, chunk, offset):
        """a Mix_Chunk over the decoded buffer from `offset` seconds on
        (Mix_QuickLoad_RAW aliases the memory, so the parent chunk stays
        cached and alive)"""
        import ctypes
        key = (name, round(offset, 3))
        if key in self._cache:
            return self._cache[key]
        freq = ctypes.c_int(0); fmt = ctypes.c_ushort(0); ch = ctypes.c_int(0)
        if self._mixer.Mix_QuerySpec(ctypes.byref(freq), ctypes.byref(fmt),
                                     ctypes.byref(ch)) == 0:
            return None
        bps = freq.value * ch.value * ((fmt.value & 0xff) // 8)
        skip = int(offset * bps)
        skip -= skip % max(1, ch.value * ((fmt.value & 0xff) // 8))
        total = chunk.contents.alen
        if skip >= total:
            sub = None
        else:
            addr = ctypes.addressof(chunk.contents.abuf.contents) + skip
            sub = self._mixer.Mix_QuickLoad_RAW(
                ctypes.cast(addr, ctypes.POINTER(ctypes.c_ubyte)),
                total - skip)
        self._cache[key] = sub
        return sub

    def play_entrance(self, name):
        """PlayEntranceMusic (MusicPlayer.cs:122-130): the EntranceSound on
        its own source, once, unless it is already playing"""
        chunk = self._load(name)
        if not chunk:
            return
        if self._mixer.Mix_Playing(self.ENTRANCE_CHANNEL):
            return
        self._mixer.Mix_PlayChannel(self.ENTRANCE_CHANNEL, chunk, 0)

    def stop_entrance(self):
        """StopEntranceMusic (MusicPlayer.cs:132-135)"""
        self._mixer.Mix_HaltChannel(self.ENTRANCE_CHANNEL)

    def stop_music(self):
        """LevelMusicSource.Stop (MusicPlayer.cs:143-166) on the reserved
        channel"""
        self._mixer.Mix_HaltChannel(self.MUSIC_CHANNEL)
