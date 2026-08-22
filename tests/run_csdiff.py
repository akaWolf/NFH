"""Track C of the bug hunt: the differential test at function
granularity — the ORIGINAL bytecode against the port, same inputs.

tools/csdiff/runner loads the user's own Assembly-CSharp.dll (never in
the repo), resolves its UnityEngine reference onto our deterministic
stub, fabricates the objects a method needs, executes the original
method and dumps the state; this driver replicates every case through
the port and diffs the observable outcomes.

    python3 tests/run_csdiff.py [--managed=<dir>]

The Managed dir defaults to the unpacked s1 data
(/tmp/nfh-data/apk/assets/bin/Data/Managed); NFH_DATA overrides.

Covered so far:
    CalculateScore + CalculateRating + SaveScore
        (GameInfo.cs:392-465, Level.cs:467-473)
      vs GameState.calculate_score (runtime/world.py) — numeric outcome,
        the rating tier, and the trick-ratio line.
"""
import itertools, json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSDIFF = os.path.join(ROOT, 'tools', 'csdiff')
sys.path.insert(0, os.path.join(ROOT, 'runtime'))


def managed_dir(argv):
    for a in argv:
        if a.startswith('--managed='):
            return a.split('=', 1)[1]
    env = os.environ.get('NFH_DATA')
    if env:
        return os.path.join(env, 'apk', 'assets', 'bin', 'Data', 'Managed')
    return '/tmp/nfh-data/apk/assets/bin/Data/Managed'


def build_runner():
    """dotnet build once; the SDK's incremental build makes re-runs cheap"""
    r = subprocess.run(['dotnet', 'build', '-c', 'Release', '--nologo', '-v', 'q',
                        os.path.join(CSDIFF, 'runner', 'csdiff.csproj')],
                       capture_output=True, text=True,
                       env=dict(os.environ, DOTNET_CLI_TELEMETRY_OPTOUT='1',
                                DOTNET_ROOT=os.path.expanduser('~/.dotnet'),
                                PATH=os.path.expanduser('~/.dotnet') + ':'
                                + os.environ['PATH']))
    if r.returncode:
        sys.exit('dotnet build failed:\n' + r.stdout + r.stderr)
    out = os.path.join(CSDIFF, 'runner', 'bin', 'Release', 'net10.0', 'csdiff.dll')
    assert os.path.exists(out), out
    return out


def run_cases(dll, managed, cases):
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
        json.dump(cases, f)
        path = f.name
    try:
        r = subprocess.run(['dotnet', dll, managed, path],
                           capture_output=True, text=True,
                           env=dict(os.environ,
                                    DOTNET_ROOT=os.path.expanduser('~/.dotnet'),
                                    PATH=os.path.expanduser('~/.dotnet') + ':'
                                    + os.environ['PATH']))
        if r.returncode:
            sys.exit('runner failed:\n' + r.stdout + r.stderr)
        return json.loads(r.stdout)
    finally:
        os.unlink(path)


# -- the case grid ---------------------------------------------------------

def score_cases():
    cases = []
    # season 1 path (NFH2Path false): compound math + the rating tiers
    for tut, ticks, cts, done, fts, won, timeup in itertools.product(
            (False, True), (0, 1, 2, 7), (0, 5, 10), (0, 3, 8),
            (0, 45, 90), (False, True), (False,)):
        cases.append({
            'name': 's1 tut=%d ticks=%d cts=%d done=%d fts=%d won=%d'
                    % (tut, ticks, cts, done, fts, won),
            'gameinfo': {'IsTutorial': tut, 'CompoundTrickScore': cts,
                         'CompletedTricksCount': done, 'FinalTrickScore': fts,
                         'TotalTricksCount': 8, 'MaximumRating': 100,
                         'Won': won, 'TimeUp': timeup, 'IgnoreScore': False},
            'woody': {'NFH2Path': False},
            'rott': {'AngryCountTicks': ticks},
        })
    # the lost-run tiers
    for timeup in (False, True):
        cases.append({
            'name': 's1 lost timeup=%d' % timeup,
            'gameinfo': {'IsTutorial': False, 'CompoundTrickScore': 5,
                         'CompletedTricksCount': 2, 'FinalTrickScore': 20,
                         'TotalTricksCount': 8, 'MaximumRating': 100,
                         'Won': False, 'TimeUp': timeup, 'IgnoreScore': False},
            'woody': {'NFH2Path': False},
            'rott': {'AngryCountTicks': 3},
        })
    # season 2 path: the 90/Total formula, the tick bonus, IgnoreScore
    for ticks, done, total, ignore in itertools.product(
            (0, 1, 2), (0, 5, 9), (9,), (False, True)):
        cases.append({
            'name': 's2 ticks=%d done=%d ignore=%d' % (ticks, done, ignore),
            'gameinfo': {'IsTutorial': False, 'CompoundTrickScore': 0,
                         'CompletedTricksCount': done, 'FinalTrickScore': 0,
                         'TotalTricksCount': total, 'MaximumRating': 100,
                         'Won': True, 'TimeUp': False, 'IgnoreScore': ignore},
            'woody': {'NFH2Path': True},
            'rott': {'AngryCountTicks': ticks},
        })
    return cases


# -- the port side ---------------------------------------------------------

def port_score(case):
    from world import GameState
    gi = case['gameinfo']
    gs = GameState({'total': gi['TotalTricksCount'],
                    'is_tutorial': gi['IsTutorial'],
                    'compound_trick_score': gi['CompoundTrickScore'],
                    'ignore_score': gi['IgnoreScore']})
    gs.completed = gi['CompletedTricksCount']
    gs.final_trick_score = gi['FinalTrickScore']
    gs.won = gi['Won']
    gs.time_up = gi['TimeUp']
    gs.calculate_score(case['rott']['AngryCountTicks'],
                       nfh2=case['woody']['NFH2Path'])
    return gs


TIER = {'TIME UP': 'timeup', 'FAILED': 'failed', 'EXCELLENT': 'excellent',
        'GOOD': 'good', 'PASSED': 'passed'}


def diff_scores(cases, results):
    bad = 0
    for case, res in zip(cases, results):
        if res.get('error'):
            print('ERR  %-40s %s' % (case['name'],
                                     res['error'].splitlines()[0]))
            bad += 1
            continue
        gs = port_score(case)
        mism = []
        if gs.final_viewer_rating != res['FinalViewerRating']:
            mism.append('rating %d != C# %d' % (gs.final_viewer_rating,
                                                res['FinalViewerRating']))
        # the original Rating strings are localized statics; an
        # uninitialized GameInfo leaves them null — classify via the
        # numeric outcome instead: both sides must pick the same tier
        want_tier = ('timeup' if not case['gameinfo']['Won']
                     and case['gameinfo']['TimeUp']
                     else 'failed' if not case['gameinfo']['Won']
                     else 'excellent' if res['FinalViewerRating'] >= 100
                     else 'good' if res['FinalViewerRating'] >= 60
                     else 'passed')
        if TIER.get(gs.rating) != want_tier:
            mism.append('tier %s != C# %s' % (gs.rating, want_tier))
        if bool(res['Perfect']) != (want_tier == 'excellent'):
            mism.append('Perfect %s vs tier %s' % (res['Perfect'], want_tier))
        ratio = '%d / %d' % (case['gameinfo']['CompletedTricksCount'],
                             case['gameinfo']['TotalTricksCount'])
        if gs.trick_ratio != ratio:
            mism.append('ratio %r' % gs.trick_ratio)
        if mism:
            print('DIFF %-40s %s' % (case['name'], '; '.join(mism)))
            bad += 1
    return bad


def main(argv):
    managed = managed_dir(argv)
    if not os.path.isdir(managed):
        print('no Managed dir at %s — unpack the game data first '
              '(tools/unpack.py)' % managed)
        return 2
    dll = build_runner()
    cases = score_cases()
    results = run_cases(dll, managed, cases)
    bad = diff_scores(cases, results)
    print('---')
    print('csdiff CalculateScore: %d cases, %d mismatches'
          % (len(cases), bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
