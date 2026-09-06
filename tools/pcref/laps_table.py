import json, re, statistics, collections
S = '/tmp/claude-1000/-home-akawolf-projects-own-NFH/ac3a80a3-83a6-48a6-96d4-81dc371f54eb/scratchpad'
labels = {
 's1_E01': {2:'Sofa/TV',3:'Binoculars'}, 's1_E02': {2:'Sofa/TV',3:'Beer',4:'Toilet'},
 's1_E03': {2:'LetterBox',3:'Cake+Candle'}, 's1_E04': {2:'Sink(shave)',3:'ApplePie',4:'Microwave',5:'Deodorant'},
 's1_E05': {3:'Piano',4:'Football',5:'Plant',7:'Phone',8:'Toilet'},
 's1_E06': {2:'PhotoAlbum',3:'Candy',4:'Pudding',5:'BathTub',6:'Towel',8:'Toilet'},
 's1_E07': {2:'Drawing',3:'Camera',4:'MagnesiumBottle',5:'Pottery(Diesel)',6:'MumStatue'},
 's1_E08': {2:'Coffee',3:'ToothBrush',6:'DeckChair',7:'WateringCan',8:'Plant'},
 's1_E09': {2:'PigMilk',3:'Teeth',4:'Bed',5:'AlarmClock',6:'PigKeys',7:'Pig',8:'CornChips',9:'Chili'},
 's1_E10': {2:'SteakMeat',3:'Beer',4:'BBQ',5:'SteakChair',6:'Wine'},
 's1_E11': {2:'Detergent',3:'WashingMachine',4:'Drier',5:'Iron',8:'Airer',9:'FishTank',11:'Vacuum'},
 's1_E12': {3:'YogaBook',4:'FishTank',5:'Yoga',6:'Trampoline',7:'Bicycle',8:'Mixer',9:'ChestExpander',10:'Weights',11:'Rope'},
 's1_E13': {1:'Sink',2:'ChairAssembly',3:'AngleGrinder',4:'ValveMain',5:'Radiator',6:'FuseBox',7:'Ladder',11:'ValveHot'},
 's1_E14': {3:'Polish',4:'GoldCup',5:'Pipe',6:'Gramaphone',7:'CDs',8:'Shotgun',9:'Hat',10:'Horn'},
 'n2_E01': {1:'CaptainHat',2:'Buffet',3:'Puddle/Rail'}, 'n2_E02': {0:'BeerMat',6:'Rake',7:'Swimming',9:'BridgeRail'},
 'n2_E03': {0:'Microphone',1:'Toilet',2:'Watermelon',3:'Bicycle'},
 'n2_E04': {0:'PullKart',1:'Karate',2:'Gong',3:'HotDog',4:'JadeNecklace'},
 'n2_E05': {0:'TableTennis',1:'WaterSkis',2:'Chef',3:'Rockets',4:'SandSculpture'},
 'n2_E06': {1:'DeckChair(mum)',2:'Pillows',3:'Pillows',7:'DogFifi',8:'LaunchPad',9:'Harpoon',10:'Weights',11:'DynamiteBox'},
 'n2_E07': {0:'PoolBoard',1:'Bartender',2:'Elephant',3:'Shell',4:'SandCastle',5:'BeachTowel',9:'Elephant'},
 'n2_E08': {0:'IndianPlatform',5:'ShoeMachine',6:'AngryElephant',7:'ArmsBowl',11:'Mother',12:'Fifi'},
 'n2_E09': {0:'FireFakir',1:'TadjMahal',5:'HotShoe',6:'Coal',7:'IceCream',8:'Cow'},
 'n2_E10': {0:'DeckChair',5:'CallRTMother',6:'DogBasket',7:'TurbanShop',8:'Elephant'},
 'n2_E11': {0:'Sweets',1:'FishingRod',2:'LifeBoat',3:'LifeJacket',4:'DivingGear',8:'ToiletMen'},
 'n2_E12': {0:'AztecThrone',1:'Whip',2:'CigarBox',5:'MechanicalBull',6:'ParrotLedge',7:'SleepBench'},
 'n2_E13': {0:'LiveBull',1:'PlantCarnivore',2:'Tortilla',3:'BoatPicnic',4:'Pinata',5:'MechanicalBull',6:'CementBath'},
 'n2_E14': {0:'Shower',1:'Bouquet',2:'CaptainWheel',3:'Pistol',4:'Hatch'},
}
mobile_of = {'s1_E%02d' % i: 'Level1%02d' % i for i in range(1, 15)}
mobile_of.update({'n2_E%02d' % i: 'Level2%02d' % i for i in range(1, 15)})
mob = {}
for line in open(S + '/mobile_laps2.txt'):
    parts = [p.strip() for p in line.strip().split('|')]
    mob[parts[0]] = parts
names = {}
for pre, f in (('s1', 'pc/ep_s1.json'), ('n2', 'pc/ep_n2.json')):
    for e in json.load(open(S + '/' + f)): names[pre + '_' + e['name'][:3]] = e['name'][4:]
out = []; table = []
for key in sorted(labels):
    d = json.load(open(S + '/bub/%s.json' % key)); lab = labels[key]
    seq = []
    for t, k in d['rows']:
        l = lab.get(k)
        if l is None: continue
        tt = round(t - d['start'])
        if seq and seq[-1][0] == l: seq[-1][2] = tt
        else: seq.append([l, tt, tt])
    seq = [s for s in seq if s[2] - s[1] >= 2 or True]
    # lap: intervals between starts of the most frequent activity (by total time)
    tot = collections.Counter()
    for l, a, b in seq: tot[l] += b - a + 1
    order = [l for l, _ in tot.most_common()]
    first = seq[0][0] if seq else None
    def periods(l):
        st = [a for ll, a, b in seq if ll == l]
        return [y - x for x, y in zip(st, st[1:])]
    cand = [(l, periods(l)) for l in order if len(periods(l)) >= 1]
    # prefer the routine's first activity when it repeats
    per = None; by = None
    for l, p in cand:
        if l == first and p: per, by = p, l; break
    if per is None and cand: by, per = cand[0]
    med = statistics.median(per) if per else None
    m = mob.get(mobile_of[key], [])
    mroutine = m[1].replace('routine ', '') if len(m) > 1 else ''
    mlap = (m[3] + '; ' + m[4]) if len(m) > 4 else ''
    muses = m[5].replace('uses: ', '') if len(m) > 5 else ''
    pc_seq = ' > '.join('%s %d-%d' % (l, a, b) for l, a, b in seq[:14])
    out.append('### %s — %s (mobile %s)\n\nPC (bubble, s from the level start): %s\n\nPC lap by %s: %s → median %s s\n\nmobile routine: %s\n\nmobile uses: %s\n\nmobile lap: %s\n' % (key, names[key], mobile_of[key], pc_seq, by, per[:5] if per else None, med, mroutine, muses, mlap))
    table.append((key, names[key], mobile_of[key], by, med, per[:4] if per else [], mlap))
open(S + '/laps_detail.md', 'w').write('\n'.join(out))
for t in table: print('%s | %-24s | %s | PC lap by %-16s med %s %s | mobile %s' % t)
