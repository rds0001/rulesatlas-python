"""Pure current-hand poker comparisons; no odds or future-card exploration."""
from collections import Counter

def five(cards):
    ranks=sorted((int(c)%13+2 for c in cards),reverse=True);counts=Counter(ranks);groups=sorted(((n,r) for r,n in counts.items()),reverse=True);flush=len({int(c)//13 for c in cards})==1
    straight=5 if ranks==[14,5,4,3,2] else ranks[0] if len(counts)==5 and ranks[0]-ranks[-1]==4 else 0
    if straight and flush:return (8,straight)
    if groups[0][0]==4:return (7,groups[0][1],groups[1][1])
    if [g[0] for g in groups]==[3,2]:return (6,groups[0][1],groups[1][1])
    if flush:return (5,*ranks)
    if straight:return (4,straight)
    if groups[0][0]==3:return (3,groups[0][1],*sorted((r for n,r in groups[1:]),reverse=True))
    if [g[0] for g in groups[:2]]==[2,2]:return (2,*sorted((groups[0][1],groups[1][1]),reverse=True),groups[2][1])
    if groups[0][0]==2:return (1,groups[0][1],*sorted((r for n,r in groups[1:]),reverse=True))
    return (0,*ranks)

def pai_five(cards):
    if 52 not in cards:return five(cards)
    rest=[c for c in cards if c!=52]
    if all(int(c)%13==12 for c in rest):return (9,14)
    choices=[]
    for c in range(52):
        if c in rest:continue
        result=five(rest+[c])
        if c%13==12 or result[0] in (4,5,8):choices.append(result)
    return max(choices)

def pai_two(cards):
    ranks=sorted((14 if c==52 else int(c)%13+2 for c in cards),reverse=True)
    return (1,ranks[0]) if ranks[0]==ranks[1] else (0,*ranks)
