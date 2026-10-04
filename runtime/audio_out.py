"""Frame-keyed sound effects through SDL2_mixer.

The game fires AnimationSound entries as their frame index comes up
(AnimationControllerBase.PlaySound); clips were extracted to WAV by
tools/extract_audio.py. Point NFH_AUDIO at those directories.
"""
import os
import time

import pcprofile
from base import asset_root


def audio_dirs(level_paths=()):
    """the clip search path (viewer decision, mirroring viewer.texture_dirs):
    NFH_AUDIO first, then the season directories with the season of the
    opened levels first — a build's Resources.Load only ever sees its own
    season's clips, and two names differ between the extractions
    (give_take1, wod_ha1: S2 levels reference both), then audio/"""
    env = os.environ.get('NFH_AUDIO')
    dirs = env.split(':') if env else []
    root = asset_root()
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
        # Level.AudioEnabled / AudioLevel / MusicLevel as the settings leave
        # them: Helpers.PlaySound is silent without AudioEnabled and scales
        # by AudioLevel (Helpers.cs:457-463); the music sources take
        # MusicLevel * AudioLevel (MusicPlayer.StartMusic, cs:98-105)
        self.audio_enabled = True
        self.sound_volume = 1.0
        self.music_volume = 1.0
        # the PC's Season 1 level track (pc_track): its clip, channel, the
        # clock of its position and whether the whole clip loops yet; the
        # track an intermezzo closed with its place, and the one asked for
        # under it
        self._pc = None
        self._pc_held = None
        self._pc_pending = None
        self._intermezzo = False

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
            # the two music sources own the first channels, and under the
            # PC profile the intermezzo and the crossfade's second track the
            # next two; Mix_PlayChannel(-1) never lands an effect on a
            # reserved one
            sdlmixer.Mix_ReserveChannels(4 if pcprofile.is_pc() else 2)
            return cls(sdlmixer, dirs)
        except Exception:
            return None

    MUSIC_CHANNEL = 0                     # reserved for the MusicPlayer port
    ENTRANCE_CHANNEL = 1                  # MusicPlayer.EntranceSoundSource: its
                                          # own AudioSource, the level track
                                          # starts under it (MusicPlayer.cs:122-135)
    INTERMEZZO_CHANNEL = 2                # the PC's jingle slot (play_intermezzo)
    MUSIC2_CHANNEL = 3                    # the PC crossfade's other track (pc_track)

    @property
    def EFFECT_CHANNELS(self):            # Mix_PlayChannel(-1)'s pool
        return range(4 if pcprofile.is_pc() else 2, 16)

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

    def set_sound_volume(self, volume, enabled=True):
        """Level.AudioEnabled / AudioLevel for the effects (Helpers.PlaySound
        gates on AudioEnabled and scales by AudioLevel, Helpers.cs:457-463)"""
        self.audio_enabled = bool(enabled)
        self.sound_volume = max(0.0, min(1.0, float(volume)))
        for ch in self.EFFECT_CHANNELS:
            self._mixer.Mix_Volume(ch, int(round(self.sound_volume * 128)))

    def set_music_volume(self, volume):
        """MusicLevel * AudioLevel on the music and entrance sources
        (MusicPlayer.StartMusic cs:101, PlayEntranceMusic cs:125,
        PlayEffectsMusic cs:172)"""
        self.music_volume = max(0.0, min(1.0, float(volume)))
        for ch in (self.MUSIC_CHANNEL, self.ENTRANCE_CHANNEL) + \
                ((self.INTERMEZZO_CHANNEL, self.MUSIC2_CHANNEL) if pcprofile.is_pc() else ()):
            self._mixer.Mix_Volume(ch, int(round(self.music_volume * 128)))

    def play(self, name):
        """one frame-keyed effect on a free channel (Helpers.PlaySound,
        Helpers.cs:452-470 — a null clip is skipped there too — behind
        AnimationControllerBase.PlaySound, cs:191-201)"""
        if not self.audio_enabled:
            return
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
        self._pc_drop()
        self._mixer.Mix_HaltChannel(self.MUSIC_CHANNEL)
        self._mixer.Mix_PlayChannel(self.MUSIC_CHANNEL, chunk,
                                    -1 if loop else 0)
        # (a track started while an intermezzo holds the channel plays)
        self._mixer.Mix_Resume(self.MUSIC_CHANNEL)

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

    def play_intermezzo(self, name, offset=0.0):
        """SFXEngine's intermezzo, the PC's jingles (its IntermezzoStart and
        the end callback's restoreVolumes, SFXEngine.dll 0x10002f89-0x10003040,
        0x10002e10): the music streams close with their places kept
        (0x100043b0 -> 0x10003d70(0)) and reopen there as the jingle ends
        (0x10004400 -> 0x10003d70(1)) — the level track paused under it (the
        PC's Season 1 track: closed with its place, pc_track); a second one
        while it plays is refused ('intermezzo Rejected Slot Playing',
        0x10002fa4). The jingle has its own reserved channel at the music's
        volume; `offset` starts it that many seconds in (the clap's load
        clock, World.play_clap)"""
        if self._mixer.Mix_Playing(self.INTERMEZZO_CHANNEL):
            return False
        chunk = self._load(name)
        if not chunk:
            return False
        if offset > 0.0:
            chunk = self._sub_chunk(name, chunk, offset)
            if chunk is None:
                return False
        if self._mixer.Mix_PlayChannel(self.INTERMEZZO_CHANNEL, chunk, 0) < 0:
            return False
        if self._pc is not None:
            self._pc_held = (self._pc['name'], self.pc_position())
            self._pc_drop(keep=True)
        else:
            self._mixer.Mix_Pause(self.MUSIC_CHANNEL)
        self._intermezzo = True
        return True

    def tick_intermezzo(self):
        """the intermezzo's end: the level track goes on where it stood —
        the PC's Season 1 track reopened at its place, or the one asked for
        under the intermezzo there (its slot's new file, pc_track), from the
        start where none played"""
        if not self._intermezzo \
                or self._mixer.Mix_Playing(self.INTERMEZZO_CHANNEL):
            return
        self._intermezzo = False
        held, self._pc_held = self._pc_held, None
        pending, self._pc_pending = self._pc_pending, None
        if held is not None or pending is not None:
            self._pc_start(pending or held[0], self.MUSIC_CHANNEL,
                           held[1] if held is not None else 0.0)
        else:
            self._mixer.Mix_Resume(self.MUSIC_CHANNEL)

    # -- the PC's Season 1 level track (World._pc_music_tick) ---------------
    def _bps(self):
        """bytes a second of the mixer's decoded buffers"""
        import ctypes
        freq = ctypes.c_int(0); fmt = ctypes.c_ushort(0); ch = ctypes.c_int(0)
        if self._mixer.Mix_QuerySpec(ctypes.byref(freq), ctypes.byref(fmt),
                                     ctypes.byref(ch)) == 0:
            return 0
        return freq.value * ch.value * ((fmt.value & 0xff) // 8)

    def _pc_len(self, name):
        chunk = self._load(name)
        bps = self._bps()
        return chunk.contents.alen / float(bps) if chunk and bps else 0.0

    def pc_position(self):
        """the current track's place, seconds (its clock; the clip loops)"""
        p = self._pc
        if p is None:
            return 0.0
        length = self._pc_len(p['name'])
        t = time.monotonic() - p['t0']
        return t % length if length > 0.0 else t

    def _pc_start(self, name, ch, pos, fade_ms=0):
        """the track on `ch` from `pos` seconds: the rest of the clip, then
        the whole clip looping (pc_tick); faded in over `fade_ms`"""
        chunk = self._load(name)
        if not chunk:
            return False
        sub, loops = chunk, -1
        if pos > 0.0:
            sub = self._sub_chunk(name, chunk, pos)
            loops = 0
            if sub is None:
                sub, loops, pos = chunk, -1, 0.0
        self._mixer.Mix_HaltChannel(ch)
        self._mixer.Mix_Volume(ch, int(round(self.music_volume * 128)))
        if fade_ms > 0:
            self._mixer.Mix_FadeInChannelTimed(ch, sub, loops, int(fade_ms), -1)
        else:
            self._mixer.Mix_PlayChannel(ch, sub, loops)
        self._pc = {'name': name, 'ch': ch, 't0': time.monotonic() - pos,
                    'whole': loops == -1}
        return True

    def _pc_drop(self, keep=False):
        """the PC track off both its channels (`keep`: the held place stays)"""
        if self._pc is None and self._pc_pending is None and self._pc_held is None:
            return
        for ch in (self.MUSIC_CHANNEL, self.MUSIC2_CHANNEL):
            self._mixer.Mix_HaltChannel(ch)
        self._pc = None
        if not keep:
            self._pc_held = self._pc_pending = None

    def pc_track(self, name, fade_ms=500):
        """the level's music post under the PC profile (game.exe fcn.00438280
        -> SFXEngine's crossFade, fcn.10002e90): the same clip plays on
        ('playMusic already playing'); another crossfades in on the free
        slot at the playing one's place (fcn.100041d0 -> fcn.100041a0: the
        three moods of a set are one piece at three tempos) while the old
        fades out, `fade_ms` each; with none playing it starts from the top
        without a fade (0x1000344f -> playMusic); under an intermezzo the
        slot takes the new clip closed and it opens as the intermezzo ends
        ('crossFade rejected. InterMezzo playMusic on current playing',
        0x10003129)"""
        if not name:
            return
        if self._intermezzo:
            self._pc_pending = name
            return
        p = self._pc
        if p is not None and p['name'] == name:
            return
        if p is None:
            self._pc_start(name, self.MUSIC_CHANNEL, 0.0)
            return
        pos = self.pc_position()
        other = self.MUSIC2_CHANNEL if p['ch'] == self.MUSIC_CHANNEL else self.MUSIC_CHANNEL
        self._mixer.Mix_FadeOutChannel(p['ch'], int(fade_ms))
        self._pc_start(name, other, pos, fade_ms)

    def pc_tick(self):
        """the rest of a track started mid-clip has played: the whole clip
        from its top, looping (Miles loops the stream, loopCount 0)"""
        p = self._pc
        if p is None or p['whole'] or self._intermezzo:
            return
        if not self._mixer.Mix_Playing(p['ch']):
            chunk = self._load(p['name'])
            if chunk:
                self._mixer.Mix_PlayChannel(p['ch'], chunk, -1)
            p['whole'] = True
            p['t0'] = time.monotonic()

    def stop_music(self):
        """LevelMusicSource.Stop (MusicPlayer.cs:143-166) on the reserved
        channel"""
        self._pc_drop()
        self._mixer.Mix_HaltChannel(self.MUSIC_CHANNEL)
