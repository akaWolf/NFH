"""PlayerPrefs — the original's settings and progress store (Unity's
key/value registry), kept as one JSON file.

Keys are the SettingKey enum names (SettingKey.cs: AudioEnabled, AudioLevel,
MusicEnabled, MusicLevel, TimedGame, TrickCamera, LastLoadedLevel, Language,
LastLoadedLevel2, Sensibility), Level.cs's progress keys ("LevelsInitialized",
"Duration"+i, "TricksTotal"+i, "MinRating"+i, "TricksPlayed"+i,
"RatingAchieved"+i, "LevelCompleted"+i, "LevelPerfect"+i — Level.cs:265-420)
and LocalizationManager's custom-language flag. Defaults are the call
sites' (PlayerPrefs.GetInt(key, default)). PlayerPrefs.Save() writes the
file; the store also writes on exit, as Unity does.

The file lives in the XDG data dir (NFH_PREFS overrides the path) — a viewer
decision; the original's registry/plist location has no counterpart here.
"""
import json, os


class Prefs:
    def __init__(self, path=None):
        self.path = path or os.environ.get('NFH_PREFS') or os.path.join(
            os.environ.get('XDG_DATA_HOME')
            or os.path.join(os.path.expanduser('~'), '.local', 'share'),
            'nfh', 'prefs.json')
        self.data = {}
        self.dirty = False
        try:
            with open(self.path, encoding='utf-8') as f:
                self.data = json.load(f)
        except (OSError, ValueError):
            self.data = {}

    # PlayerPrefs.GetInt/GetFloat/GetString (missing key -> the default)
    def get_int(self, key, default=0):
        v = self.data.get(key, default)
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    def get_float(self, key, default=0.0):
        v = self.data.get(key, default)
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    def get_string(self, key, default=''):
        v = self.data.get(key, default)
        return v if isinstance(v, str) else default

    def has_key(self, key):
        return key in self.data

    def set_int(self, key, value):
        self.data[key] = int(value)
        self.dirty = True

    def set_float(self, key, value):
        self.data[key] = float(value)
        self.dirty = True

    def set_string(self, key, value):
        self.data[key] = str(value)
        self.dirty = True

    def delete_all(self):
        self.data = {}
        self.dirty = True

    def save(self):
        """PlayerPrefs.Save"""
        if not self.dirty:
            return
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=1, sort_keys=True)
            os.replace(tmp, self.path)
            self.dirty = False
        except OSError:
            pass


class MemoryPrefs(Prefs):
    """a store that never touches the disk — the tests' PlayerPrefs"""

    def __init__(self, data=None):
        self.path = None
        self.data = dict(data or {})
        self.dirty = False

    def save(self):
        self.dirty = False
