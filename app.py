import os, secrets
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode
import requests
from flask import Flask, redirect, request, session, render_template_string, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

ML_CLIENT_ID = os.environ.get("ML_CLIENT_ID", "")
ML_CLIENT_SECRET = os.environ.get("ML_CLIENT_SECRET", "")
BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/")
REDIRECT_URI = f"{BASE_URL}/callback" if BASE_URL else ""
API = "https://api.mercadolibre.com"
AUTH = "https://auth.mercadolivre.com.br/authorization"
TOKEN = API + "/oauth/token"

TERMS = ["celular smartphone","notebook","smart tv","cafeteira","ferramentas",
         "games console","beleza","autopeças","eletrodomésticos","casa cozinha"]

CSS = """body{font-family:Arial,sans-serif;max-width:1050px;margin:auto;padding:16px;background:#f5f5f5;color:#222}
.card{background:#fff;border-radius:16px;padding:18px;margin:14px 0;box-shadow:0 2px 10px #0001}
.btn{display:inline-block;background:#ffe600;color:#222;padding:12px 15px;border:0;border-radius:10px;text-decoration:none;font-weight:bold;cursor:pointer;margin:4px}
.ok{color:#08783e;font-weight:bold}.muted{color:#666}.bad{color:#a40000}.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
input,select,textarea{width:100%;box-sizing:border-box;padding:11px;margin:6px 0;border:1px solid #ccc;border-radius:9px}
img.prod{width:150px;height:150px;object-fit:contain;float:left;margin-right:16px}.old{text-decoration:line-through;color:#777}
.price{font-size:25px;font-weight:bold}.off{color:#08783e;font-weight:bold;font-size:18px}.clear{clear:both}
textarea{min-height:170px}@media(max-width:650px){.grid{grid-template-columns:1fr}img.prod{float:none;width:100%;height:210px}}"""

HOME = r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Caçador de Ofertas MLV</title><style>{{css}}</style></head><body>
<div class="card"><h1>🔎 Caçador de Ofertas MLV</h1>
{% if connected %}<p class="ok">✓ Mercado Livre conectado</p>
<form action="/ofertas"><label>Desconto mínimo</label><select name="min"><option>0</option><option>10</option><option selected>20</option><option>30</option><option>40</option></select>
<button class="btn">🔥 Caçar ofertas agora</button></form><p style="margin-top:12px"><a href="/diagnostico-api" target="_blank">🩺 Ver diagnóstico da API</a></p>
{% else %}<a class="btn" href="/login">Conectar Mercado Livre</a>{% endif %}</div>
<div class="card"><h2>Oferta de afiliado</h2><p class="muted">Quando escolher um produto, gere seu link no Mercado Livre e cole no card da oferta. O restante é preenchido automaticamente.</p></div>
</body></html>"""

OFFERS = r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ofertas</title><style>{{css}}</style></head><body><a href="/">← Voltar</a><h1>🔥 Caçador</h1>
<div class="card"><b>Diagnóstico real da busca</b><br>
Categorias principais: {{diag.categories}} • Categorias finais: {{diag.leaves}} • Rankings lidos: {{diag.rankings}} • Candidatos: {{diag.candidates}} •
Resolvidos em anúncios: {{diag.resolved}} • Com preço: {{diag.priced}} • Com desconto identificado: {{diag.promos}} • Frete grátis: {{diag.free}}.
{% if diag.errors %}<p class="bad">Falhas de API: {{diag.errors}} {% if diag.statuses %}• Status: {{diag.statuses}}{% endif %}</p>{% endif %}
{% if fallback %}<p><b>Nenhum chegou a {{minimum}}% nesta rodada.</b> Estou mostrando os melhores produtos encontrados para você não ficar com tela vazia.</p>{% endif %}
</div>
{% for d in deals %}
<div class="card">
{% if d.image %}<img class="prod" src="{{d.image}}">{% endif %}
<h3>{{d.title}}</h3>
{% if d.old %}<div class="old">De R$ {{ "%.2f"|format(d.old) }}</div>{% endif %}
<div class="price">R$ {{ "%.2f"|format(d.price) }}</div>
{% if d.discount %}<div class="off">🔻 {{d.discount}}% OFF</div>{% endif %}
{% if d.free_shipping %}<div>🚚 Frete grátis</div>{% endif %}
<div>🏆 Ranking: #{{d.position}} • Fonte: {{d.source}}</div>
<p class="muted">Anúncio: {{d.item_id}}</p>
<a class="btn" href="{{d.permalink}}" target="_blank">Abrir no Mercado Livre</a>
<div class="clear"></div><hr>
<label>Seu link de afiliado deste produto</label>
<input id="link{{loop.index}}" placeholder="https://meli.la/...">
<label>Código de afiliado (opcional)</label><input id="cod{{loop.index}}" placeholder="JJZBV9-...">
<button class="btn" type="button" onclick='prepare({{d|tojson}},{{loop.index}})'>📋 Preparar para compartilhar</button>
<textarea id="msg{{loop.index}}" style="display:none"></textarea>
<button class="btn" id="wa{{loop.index}}" style="display:none" type="button" onclick="zap({{loop.index}})">WhatsApp</button>
</div>
{% else %}<div class="card bad">Nenhum produto pôde ser carregado. Veja o diagnóstico acima.</div>{% endfor %}
<script>
function money(v){return Number(v).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2})}
function prepare(d,i){
 const link=document.getElementById('link'+i).value.trim(),cod=document.getElementById('cod'+i).value.trim();
 let t='🔥 OFERTA!\\n\\n'+d.title+'\\n';
 if(d.old)t+='De R$ '+money(d.old)+' por R$ '+money(d.price)+'\\n'; else t+='Por R$ '+money(d.price)+'\\n';
 if(d.discount)t+='🔻 '+d.discount+'% OFF\\n'; if(d.free_shipping)t+='🚚 Frete grátis\\n';
 if(cod)t+='\\n🔍 Código no Mercado Livre: '+cod+'\\n';
 if(link)t+='\\n🛒 PEGAR OFERTA:\\n'+link+'\\n'; else t+='\\n⚠️ COLE SEU LINK DE AFILIADO ANTES DE ENVIAR\\n';
 t+='\\n⚠️ Preço e estoque podem mudar.';
 const a=document.getElementById('msg'+i);a.value=t;a.style.display='block';document.getElementById('wa'+i).style.display='inline-block';
}
function zap(i){const t=document.getElementById('msg'+i).value;if(t.includes('COLE SEU LINK')){alert('Cole seu link de afiliado antes de compartilhar.');return}window.open('https://wa.me/?text='+encodeURIComponent(t),'_blank')}
</script></body></html>"""

def headers():
    return {"Authorization": "Bearer " + session.get("access_token","")}

def api_get(path, params=None):
    try:
        r=requests.get(API+path,headers=headers(),params=params,timeout=15)
        if not r.ok: return None, r.status_code
        return r.json(), 200
    except requests.RequestException:
        return None, 599

def category(term):
    d,st=api_get("/sites/MLB/domain_discovery/search",{"q":term,"limit":1})
    return (d[0].get("category_id") if st==200 and isinstance(d,list) and d else None)

def money_value(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None

def discount_pct(current, regular):
    current, regular = money_value(current), money_value(regular)
    if not current or not regular or regular <= current:
        return 0
    return round((regular-current)*100/regular)

def item_details(item_id, position, source):
    d,st=api_get("/items/"+item_id)
    if st!=200 or not d: return None
    sp,_=api_get("/items/"+item_id+"/sale_price",{"context":"channel_marketplace"})
    price=(sp or {}).get("amount") or d.get("price")
    old=(sp or {}).get("regular_amount") or d.get("original_price")
    if not price: return None
    discount=round((old-price)/old*100) if old and old>price else 0
    pics=d.get("pictures") or []
    image=(pics[0].get("secure_url") or pics[0].get("url")) if pics else d.get("thumbnail")
    return {"item_id":item_id,"title":d.get("title") or d.get("family_name") or item_id,
      "price":float(price),"old":float(old) if old else None,"discount":discount,
      "free_shipping":bool((d.get("shipping") or {}).get("free_shipping")),
      "permalink":d.get("permalink") or "https://www.mercadolivre.com.br/",
      "image":image,"position":position or 999,"source":source}

def resolve(entry):
    """Turn a highlight result into a shareable Mercado Livre product/deal."""
    eid=entry.get("id","")
    typ=entry.get("type","")
    pos=entry.get("position",999)

    if typ=="PRODUCT":
        pd,st=api_get("/products/"+eid)
        if st!=200 or not pd:
            return None

        winner=pd.get("buy_box_winner") or {}
        current=winner.get("price")
        regular=winner.get("original_price")
        disc=discount_pct(current,regular)
        shipping=winner.get("shipping") or {}
        pics=pd.get("pictures") or []
        picture=""
        if pics:
            picture=pics[0].get("secure_url") or pics[0].get("url") or pics[0].get("id","")
            if picture and not str(picture).startswith("http"):
                picture=f"https://http2.mlstatic.com/D_{picture}-O.jpg"

        # A PRODUCT page is itself a valid Mercado Livre product link.
        # This is useful even when the current buy-box winner is unavailable.
        permalink=pd.get("permalink")
        iid=winner.get("item_id") or eid
        if not permalink:
            return None

        return {
            "item_id":iid,
            "title":pd.get("name") or pd.get("family_name") or eid,
            "price":money_value(current) or 0,
            "regular_price":money_value(regular),
            "discount":disc,
            "free_shipping":bool(shipping.get("free_shipping")),
            "thumbnail":picture,
            "permalink":permalink,
            "position":pos,
            "source":"PRODUCT",
            "seller_id":winner.get("seller_id"),
        }

    if eid.startswith("MLBU") or typ=="USER_PRODUCT":
        up,st=api_get("/user-products/"+eid)
        if st!=200 or not up:
            return None
        # Some UP responses expose item ids directly.
        ids=up.get("item_ids") or up.get("items") or []
        for x in ids:
            iid=x.get("id") if isinstance(x,dict) else x
            if iid:
                got=item_details(iid,pos,"USER_PRODUCT")
                if got:
                    return got
        return None

    return item_details(eid,pos,"ITEM")

@app.get("/")
def home(): return render_template_string(HOME,css=CSS,connected=bool(session.get("access_token")))

@app.get("/health")
def health(): return {"ok":True}

@app.get("/login")
def login():
    if not ML_CLIENT_ID or not REDIRECT_URI: return "Configure ML_CLIENT_ID e BASE_URL.",500
    state=secrets.token_urlsafe(32);session["oauth_state"]=state
    return redirect(AUTH+"?"+urlencode({"response_type":"code","client_id":ML_CLIENT_ID,"redirect_uri":REDIRECT_URI,"state":state}))

@app.get("/callback")
def callback():
    if request.args.get("state")!=session.pop("oauth_state",None): return "State OAuth inválido.",400
    code=request.args.get("code")
    r=requests.post(TOKEN,data={"grant_type":"authorization_code","client_id":ML_CLIENT_ID,"client_secret":ML_CLIENT_SECRET,"code":code,"redirect_uri":REDIRECT_URI},timeout=20)
    if not r.ok:return f"Falha ao obter token: {r.status_code}",400
    session["access_token"]=r.json()["access_token"];return redirect("/")

@app.get("/me")
def me():
    d,st=api_get("/users/me")
    if st!=200:return redirect("/login")
    return jsonify({k:d.get(k) for k in ("id","nickname","site_id")})

def api_debug(path):
    token=session.get("access_token")
    try:
        r=requests.get(API+path,headers={"Authorization":"Bearer "+token},timeout=15)
        try:
            body=r.json()
        except Exception:
            body={"raw":(r.text or "")[:500]}
        # Keep only useful API error fields; never return request headers/token.
        if isinstance(body,dict):
            safe={k:body.get(k) for k in ("message","error","status","cause","code") if k in body}
            if not safe: safe={"response":str(body)[:500]}
        else:
            safe={"response":str(body)[:500]}
        return r.status_code,safe
    except Exception as e:
        return 0,{"error":type(e).__name__}

@app.get("/diagnostico-api")
def diagnostico_api():
    if not session.get("access_token"): return redirect("/login")
    tests={}
    # Read-only probes only. No data is created/changed.
    paths=(
        "/users/me",
        "/sites/MLB/categories",
        "/sites/MLB/domain_discovery/search?limit=1&q=celular",
        "/sites/MLB/search?q=celular&limit=1",
        "/highlights/MLB/category/MLB1051",
        "/categories/MLB1051",
        "/items/MLB3733067613",
        "/items/MLB3733067613/sale_price?context=channel_marketplace",
        "/products/search?site_id=MLB&q=celular&limit=1",
    )
    for path in paths:
        st,body=api_debug(path)
        tests[path]={"http":st,"mercado_livre":body}
    return jsonify(tests)

def leaf_categories(root_id, max_leaves=3):
    """Find a few active leaf categories below a top-level category."""
    leaves=[]
    queue=[root_id]
    visited=set()
    while queue and len(leaves)<max_leaves:
        cid=queue.pop(0)
        if cid in visited: continue
        visited.add(cid)
        d,st=api_get("/categories/"+cid)
        if st!=200 or not d: continue
        children=d.get("children_categories") or []
        if not children:
            leaves.append(cid)
        else:
            # Prefer branches with more listings.
            children=sorted(children,key=lambda x:x.get("total_items_in_this_category",0),reverse=True)
            queue.extend([x["id"] for x in children[:5] if x.get("id")])
    return leaves

@app.get("/teste-produto-real")
def teste_produto_real():
    if not session.get("access_token"):
        return redirect("/login")

    h,st=api_get("/highlights/MLB/category/MLB1051")
    if st!=200 or not isinstance(h,dict):
        return jsonify({"etapa":"highlights","http":st,"resposta":h}), st or 500

    product=next((x for x in (h.get("content") or []) if x.get("type")=="PRODUCT" and x.get("id")),None)
    if not product:
        return jsonify({"etapa":"highlights","erro":"Nenhum PRODUCT encontrado"}),404

    pid=product["id"]
    pd,pst=api_get("/products/"+pid)

    out={
        "product_id":pid,
        "product_http":pst,
        "product_type":type(pd).__name__,
    }
    if isinstance(pd,dict):
        out["product_keys"]=sorted(pd.keys())
        out["name"]=pd.get("name")
        out["permalink"]=pd.get("permalink")
        winner=pd.get("buy_box_winner")
        out["buy_box_winner_type"]=type(winner).__name__
        if isinstance(winner,dict):
            out["buy_box_winner_keys"]=sorted(winner.keys())
            out["item_id"]=winner.get("item_id")
            out["price"]=winner.get("price")
            out["original_price"]=winner.get("original_price")
    else:
        out["response_preview"]=str(pd)[:1000]
    return jsonify(out)

@app.get("/ofertas")
def ofertas():
    if not session.get("access_token"): return redirect("/login")
    try: minimum=max(0,min(90,int(request.args.get("min","20"))))
    except: minimum=20

    diag={"categories":0,"leaves":0,"rankings":0,"candidates":0,"resolved":0,
          "priced":0,"promos":0,"free":0,"errors":0,"statuses":{}}

    # Official Brazil category tree. No category predictor dependency.
    roots,st=api_get("/sites/MLB/categories")
    if st!=200 or not isinstance(roots,list):
        diag["errors"]+=1
        diag["statuses"]["/sites/MLB/categories"]=st
        return render_template_string(OFFERS,css=CSS,deals=[],diag=diag,minimum=minimum,fallback=False)

    # Focus on shopping categories suitable for affiliate deals.
    wanted={"MLB5672","MLB1246","MLB1574","MLB1051","MLB5726","MLB1000",
            "MLB1276","MLB263532","MLB1144","MLB1648","MLB1132","MLB264586"}
    roots=[r for r in roots if r.get("id") in wanted]
    diag["categories"]=len(roots)

    # Rankings work directly on the top-level categories for this application.
    # Using them directly avoids the child-category calls that caused 12/12 failures.
    leafs=[r["id"] for r in roots if r.get("id")]
    diag["leaves"]=len(leafs)

    entries=[];seen=set()
    for cid in leafs:
        h,hst=api_get(f"/highlights/MLB/category/{cid}")
        if hst!=200 or not h:
            diag["errors"]+=1
            diag["statuses"][str(hst)]=diag["statuses"].get(str(hst),0)+1
            continue
        diag["rankings"]+=1
        for e in (h.get("content") or [])[:8]:
            key=e.get("id")
            if key and key not in seen:
                seen.add(key);entries.append(e)
    diag["candidates"]=len(entries)

    raw=[]
    with ThreadPoolExecutor(max_workers=8) as pool:
        fs=[pool.submit(resolve,e) for e in entries[:100]]
        for f in as_completed(fs):
            try:
                d=f.result()
                if d:
                    diag["resolved"]+=1;diag["priced"]+=1
                    if d["discount"]>0:diag["promos"]+=1
                    if d["free_shipping"]:diag["free"]+=1
                    raw.append(d)
            except Exception: diag["errors"]+=1

    uniq={d["item_id"]:d for d in raw}
    raw=list(uniq.values())
    chosen=[d for d in raw if d["discount"]>=minimum]
    fallback=not bool(chosen)
    if fallback: chosen=raw
    chosen.sort(key=lambda d:(d["discount"],d["free_shipping"],-d["position"]),reverse=True)
    return render_template_string(OFFERS,css=CSS,deals=chosen[:30],diag=diag,minimum=minimum,fallback=fallback)

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT","10000")))
