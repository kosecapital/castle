import json, re, collections
def num(s):
    s=s.strip()
    if s in ("A/D","","-"): return None
    return float(s.replace(".","").replace(",","."))
oz={}
for f in ["ozet_1","ozet_2","ozet_3"]:
    for ln in open(f"data/raw/{f}.txt",encoding="utf-8"):
        ln=ln.strip()
        if not ln: continue
        p=ln.split(";")
        assert len(p)==7,(ln,len(p))
        code,name,sector,close,mcap,mcapusd,ff=p
        assert code not in oz, code
        oz[code]=dict(code=code,name=name,sector=sector.replace("Perakande","Perakende"),close=num(close),mcap=num(mcap),mcap_usd=num(mcapusd),float=num(ff))
ra={}
for f in ["ratios_1","ratios_2"]:
    for ln in open(f"data/raw/{f}.txt",encoding="utf-8"):
        ln=ln.strip()
        if not ln: continue
        p=ln.split(";")
        assert len(p)==7,(ln,len(p))
        code,close,pe,evebitda,evsales,pb,per=p
        assert code not in ra, code
        ra[code]=dict(close=num(close),pe=num(pe),ev_ebitda=num(evebitda),ev_sales=num(evsales),pb=num(pb),period=per)
print("ozet",len(oz),"ratios",len(ra))
print("only ozet",sorted(set(oz)-set(ra)))
print("only ratios",sorted(set(ra)-set(oz)))
bad=[c for c in oz if c in ra and oz[c]["close"]!=ra[c]["close"]]
print("close mismatch",[(c,oz[c]["close"],ra[c]["close"]) for c in bad])
# alphabetical order check
codes=list(oz)
print("sorted?",codes==sorted(codes))
# implied usdtry check
import statistics
fx=[oz[c]["mcap"]/oz[c]["mcap_usd"] for c in oz if oz[c]["mcap_usd"] and oz[c]["mcap_usd"]>50]
print("implied USDTRY median",round(statistics.median(fx),3),"min",round(min(fx),2),"max",round(max(fx),2))
out=[c for c in oz if oz[c]["mcap_usd"] and oz[c]["mcap_usd"]>50 and abs(oz[c]["mcap"]/oz[c]["mcap_usd"]/statistics.median(fx)-1)>0.01]
print("fx outliers",[(c,oz[c]["mcap"],oz[c]["mcap_usd"]) for c in out])
U=[]
for c in oz:
    d=dict(oz[c]); d.update({k:v for k,v in ra[c].items() if k!="close"})
    U.append(d)
json.dump(U,open("data/universe.json","w",encoding="utf-8"),ensure_ascii=False,indent=0)
print("sectors:")
for s,n in collections.Counter(d["sector"] for d in U).most_common(): print("  ",n,s)
print("periods",collections.Counter(d["period"] for d in U))
print("total mcap bn TL",round(sum(d["mcap"] for d in U)/1000,1))
