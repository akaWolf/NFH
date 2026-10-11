"""compare an oracle event trace (trace_*.jsonl) with the port's idle recording (state.jsonl): the neighbour's
key moments — PC: DoAction enter/use/leave on his station objects and icon changes; port: the routine's
anim/item/think transitions — printed side by side in seconds"""
import json, sys, os
tr = [json.loads(l) for l in open(os.path.expanduser(sys.argv[1]))]
st = [json.loads(l) for l in open(os.path.expanduser(sys.argv[2]))]
TPS = 12.0
print('== PC (oracle) neighbour events')
last = None
for r in tr:
    if r['ev'] == 'action' and r['args'][1] not in ('woody', 'kid', 'olga') and r['args'][2] not in ('-',):
        print('%7.2f action %s %s' % (r['tick'] / TPS, r['args'][1], r['args'][2]))
    if r['ev'] == 'icon' and r['args'][0] == 'neighbor':
        ic = r['args'][1]
        if ic != last:
            print('%7.2f icon   %r' % (r['tick'] / TPS, ic)); last = ic
    if r['ev'] in ('shout', 'post'):
        print('%7.2f %s %s' % (r['tick'] / TPS, r['ev'], r['args'][:3]))
print('== port (PC profile) neighbour transitions')
last = None
for s in st:
    r = next(x for x in s['routines'] if x['role'] == 'Rottweiler')
    k = (s['hud'].get('think') if s['hud'] else None, r['item'], r['state'], r['anim'])
    if k != last:
        print('%7.2f think=%-10r %-14s %-7s %s' % (s['t'], k[0], r['item'], r['state'], r['anim'])); last = k
