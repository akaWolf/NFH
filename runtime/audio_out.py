"""Frame-keyed sound effects through SDL2_mixer.

The game fires AnimationSound entries as their frame index comes up
(AnimationControllerBase.PlaySound); clips were extracted to WAV by
tools/extract_audio.py. Point NFH_AUDIO at those directories.
"""
import os


def audio_dirs():
    env = os.environ.get('NFH_AUDIO')
    dirs = env.split(':') if env else []
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for s in ('s1', 's2'):
        dirs.append(os.path.join(root, 'audio', s))
    dirs.append(os.path.join(root, 'audio'))
    return [d for d in dirs if os.path.isdir(d)]


class SoundBank:
    def __init__(self, mixer, dirs):
        self._mixer = mixer
        self._dirs = dirs
        self._cache = {}

    @classmethod
    def try_open(cls):
        dirs = audio_dirs()
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

    def play(self, name):
        chunk = self._cache.get(name)
        if chunk is None and name not in self._cache:
            path = None
            for d in self._dirs:
                p = os.path.join(d, name + '.wav')
                if os.path.exists(p):
                    path = p
                    break
            chunk = self._mixer.Mix_LoadWAV(path.encode()) if path else None
            self._cache[name] = chunk
        if chunk:
            self._mixer.Mix_PlayChannel(-1, chunk, 0)
