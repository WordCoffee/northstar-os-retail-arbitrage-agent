import re, json, urllib.request, time, os
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
Q={
 "organic ceylon cinnamon sticks":"https://www.amazon.com/s?k=organic+ceylon+cinnamon+sticks",
 "organic whole nutmeg":"https://www.amazon.com/s?k=organic+whole+nutmeg",
}
out={}
for q,u in Q.items():
    try:
        r=urllib.request.Request(u,headers={"User-Agent":UA,"Accept-Language":"en-US,en;q=0.9"})
        html=urllib.request.urlopen(r,timeout=30).read().decode("utf-8","replace")
    except Exception as e:
        print("ERR",q,e); continue
    if re.search(r'captcha|Robot Check|automated access',html): print("BLOCKED",q); continue
    items=[]
    blocks=re.split(r'data-asin="([A-Z0-9]{10})"',html)
    for i in range(1,len(blocks)-1,2):
        asin=blocks[i]; b=blocks[i+1]
        mt=re.search(r'<h2[^>]*>.*?<span[^>]*>(.*?)</span>',b,re.S) or re.search(r'aria-label="([^"]{15,180})"',b)
        title=re.sub(r'<[^>]+>','',mt.group(1)).strip() if mt else ""
        mp=re.search(r'a-price-whole">([0-9,]+)',b); mf=re.search(r'a-price-fraction">([0-9]{2})',b)
        price=(mp.group(1).replace(",","")+"."+(mf.group(1) if mf else "00")) if mp else ""
        mr=re.search(r'([0-9.]+) out of 5 stars',b)
        mc=re.search(r'aria-label="([0-9,]+) ratings?"',b) or re.search(r's-underline-text">([0-9,]+)<',b)
        if title and len(title)>12:
            items.append({"asin":asin,"title":title[:170],"price_usd":price,
                          "rating":mr.group(1) if mr else "","ratings":mc.group(1).replace(",","") if mc else ""})
    out[q]=items[:18]; print(q,len(items)); time.sleep(2)
json.dump(out,open("docs/mogra-organics-research-2026-10-02/_raw/amazon_search_obs2.json","w",encoding="utf-8"),indent=1)
for q,items in out.items():
    print("===",q,"===")
    for o in items:
        if o["price_usd"]:
            t=o["title"][:66]
            print(f"  {o['asin']:<12} ${o['price_usd']:<8} {o['rating']:<4} {o['ratings']:<7} {t}")
