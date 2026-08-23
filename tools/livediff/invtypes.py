"""InventoryType's names to their enum values, from the decompiled
src/Assembly-CSharp/InventoryType.cs (ordinal, no explicit values)"""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))


def load():
    p = os.path.join(ROOT, 'src', 'Assembly-CSharp', 'InventoryType.cs')
    names = [l.strip().rstrip(',') for l in open(p)
             if re.match(r'^\s*IT2?_[A-Za-z0-9_]+,?\s*$', l)]
    return {n: i for i, n in enumerate(names)}
