"""Pass-1 helper: inventory every state field of the target classes.

For each class: parse field declarations; keep bool / enum / int / float /
object-reference fields.  Then grep ALL .cs files for every occurrence of
each field name, classifying write (=, ++, --, op=) vs read.  Emits a
markdown-ish dump with File.cs:line for each site.

Config-vs-state judgment is left to the reader: the dump marks fields whose
only writes sit in initializers (declaration line) so they can be skipped
fast.
"""
import os, re, sys, json, collections

SRC = 'src/Assembly-CSharp'
TARGETS = ['Pawn', 'Woody', 'Rottweiler', 'Mother', 'Olga', 'Kid',
           'GameInfo', 'HUD', 'Item', 'TrickItem', 'SearchItem', 'Door',
           'ActionManager', 'AnimationControllerBase', 'Alerter',
           'HideItem', 'AnimationInstance', 'ItemAnimationInstance']

FIELD_RE = re.compile(
    r'^\s*(?:public|private|protected|internal)\s+'
    r'(?:static\s+)?(?:readonly\s+)?'
    r'(?P<type>[A-Za-z_][A-Za-z0-9_.<>\[\],\s]*?)\s+'
    r'(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?:=\s*(?P<init>[^;]+))?;')

SKIP_TYPES = {'string', 'String', 'Rect', 'Rect[]', 'GUIStyle', 'Texture2D',
              'Texture2D[]', 'AudioClip', 'AudioClip[]', 'Vector2', 'const'}

def parse_fields(path):
    fields = []
    depth = 0
    in_class = False
    for i, line in enumerate(open(path, encoding='utf-8', errors='replace'),
                             1):
        s = line.strip()
        if s.startswith('public class') or s.startswith('internal class'):
            in_class = True
        depth += line.count('{') - line.count('}')
        # fields live at depth 1 inside the class body
        if not in_class or depth != 1:
            continue
        if '(' in s.split('=')[0]:      # method or property with args
            continue
        m = FIELD_RE.match(line)
        if not m:
            continue
        t = m.group('type').strip()
        if t in ('const',) or ' const ' in line:
            continue
        fields.append({'name': m.group('name'), 'type': t,
                       'init': (m.group('init') or '').strip(),
                       'line': i})
    return fields

WRITE_RE = None

def classify(line, name):
    """write / read / decl for one source line containing name"""
    # strip strings and comments roughly
    l = re.sub(r'"[^"]*"', '""', line)
    l = l.split('//')[0]
    out = []
    for m in re.finditer(r'\b%s\b' % re.escape(name), l):
        rest = l[m.end():]
        before = l[:m.start()]
        if re.match(r'\s*(\+\+|--)', rest) or re.search(r'(\+\+|--)\s*$',
                                                        before):
            out.append('write')
        elif re.match(r'\s*(=[^=]|[-+*/|&^]=)', rest):
            out.append('write')
        elif re.match(r'\s*(==|!=|\)|\]|;|,|\.|&&|\|\||\?|:)', rest):
            out.append('read')
        else:
            out.append('read')
    return out

def main():
    files = []
    for root, _dirs, names in os.walk(SRC):
        for n in names:
            if n.endswith('.cs'):
                files.append(os.path.join(root, n))
    files.sort()
    all_lines = {}
    for f in files:
        all_lines[f] = open(f, encoding='utf-8',
                            errors='replace').readlines()

    for cls in TARGETS:
        path = os.path.join(SRC, cls + '.cs')
        if not os.path.exists(path):
            print('## %s: NOT FOUND' % cls)
            continue
        fields = parse_fields(path)
        print('\n' + '=' * 72)
        print('## class %s (%d fields)' % (cls, len(fields)))
        for fd in fields:
            t = fd['type']
            name = fd['name']
            writes, reads = [], []
            for f in files:
                base = os.path.basename(f)
                for i, line in enumerate(all_lines[f], 1):
                    if name not in line:
                        continue
                    for kind in classify(line, name):
                        site = '%s:%d' % (base, i)
                        (writes if kind == 'write' else reads).append(site)
            # drop the declaration itself from writes
            decl = '%s.cs:%d' % (cls, fd['line'])
            wr = [w for w in writes if w != decl]
            print('\n### %s.%s : %s%s  (decl %s)' % (
                cls, name, t, (' = ' + fd['init']) if fd['init'] else '',
                decl))
            print('  writes(%d): %s' % (len(wr), ' '.join(wr) or '-'))
            print('  reads(%d): %s' % (len(reads),
                                       ' '.join(reads[:120]) or '-'))
            if len(reads) > 120:
                print('  ...reads truncated (%d total)' % len(reads))

main()
