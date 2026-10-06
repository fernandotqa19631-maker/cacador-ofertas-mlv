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

AUTH_URL = "https://auth.mercadolivre.com.br/authorization"
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
API_URL = "https://api.mercadolibre.com"

PAGE = r"""
<!doctype html><html lang="pt-BR"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Caçador de Ofertas MLV</title>
<style>
body{font-family:Arial,sans-serif;max-width:950px;margin:auto;padding:18px;background:#f5f5f5;color:#222}
.card{background:white;border-radius:16px;padding:20px;margin:14px 0;box-shadow:0 2px 10px #0001}
h1{margin-bottom:6px}.btn{display:inline-block;background:#ffe600;color:#222;padding:12px 16px;border-radius:10px;text-decoration:none;font-weight:bold;border:0;cursor:pointer}
.ok{color:#08783e;font-weight:bold}.muted{color:#666}input{width:100%;box-sizing:border-box;padding:12px;margin:7px 0;border:1px solid #ccc;border-radius:9px}
.deal{white-space:pre-wrap;background:#f7f7f7;padding:14px;border-radius:10px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media(max-width:650px){.grid{grid-template-columns:1fr}}
</style></head><body>
<div class="card"><h1>🔎 Caçador de Ofertas MLV</h1>
<p class="muted">Consulte produtos e prepare ofertas para compartilhar.</p>
{% if connected %}<p class="ok">✓ Mercado Livre conectado</p>
<a class="btn" href="/me">Testar conexão</a>
{% else %}<a class="btn" href="/login">Conectar Mercado Livre</a>{% endif %}
</div>

{% if connected %}
<div class="card">
<h2>🔥 Caçar ofertas automaticamente</h2>
<p class="muted">Busca produtos populares em várias categorias e prioriza os que estão com desconto.</p>
<form action="/ofertas" method="get">
<label>Desconto mínimo</label>
<select name="min" style="width:100%;padding:12px;margin:7px 0;border:1px solid #ccc;border-radius:9px">
<option value="10">10% ou mais</option>
<option value="20" selected>20% ou mais</option>
<option value="30">30% ou mais</option>
</select>
<button class="btn">🔎 Caçar ofertas</button>
</form>
</div>
{% endif %}

<div class="card"><h2>Preparar oferta de afiliado</h2>
<p class="muted">Use exatamente os dados que aparecem para você no Mercado Livre.</p>
<div class="grid">
<input id="codigoAfiliado" placeholder="Código: ex. JJZBV9-TRU1">
<input id="linkAfiliado" placeholder="Link: ex. https://meli.la/1fjFTNU">
</div>
<button type="button" class="btn" onclick="usarAfiliado()">Usar esta oferta</button>
<p id="statusAfiliado" class="muted"></p>
</div>

{% if connected %}
<div class="card"><h2>Consulta técnica por MLB</h2>
<p class="muted">Opcional: se você tiver o ID tradicional MLB do anúncio, consulte os dados pela API.</p>
<form action="/produto" method="get">
<input name="id" placeholder="Ex.: MLB1234567890" required>
<button class="btn">Consultar pela API</button>
</form></div>
{% endif %}

<div class="card"><h2>Gerador de mensagem</h2>
<div class="grid">
<input id="nome" placeholder="Nome do produto">
<input id="antes" placeholder="Preço anterior (ex.: 104,82)">
<input id="agora" placeholder="Preço atual (ex.: 81,75)">
<input id="desconto" placeholder="Desconto (ex.: 22)">
</div>
<input id="codigo" placeholder="Código de afiliado (ex.: JJZBV9-TRU1)">
<input id="link" placeholder="Seu link de afiliado meli.la">
<label><input id="frete" type="checkbox" style="width:auto"> Frete grátis</label><br><br>
<button type="button" class="btn" onclick="gerar()">Gerar mensagem</button>
<button type="button" class="btn" onclick="whatsapp()">Compartilhar no WhatsApp</button>
<div id="saida" class="deal" style="margin-top:15px"></div>
</div>
<script>
function montar(){
 let n=document.getElementById('nome').value,a=document.getElementById('antes').value,
 p=document.getElementById('agora').value,d=document.getElementById('desconto').value,
 l=document.getElementById('link').value,c=document.getElementById('codigo').value,f=document.getElementById('frete').checked;
 let t=`🔥 OFERTA!\n\n${n}\n`;
 if(a)t+=`De R$ ${a} `;
 if(p)t+=`por R$ ${p}\n`;
 if(d)t+=`🔻 ${d}% OFF\n`;
 if(f)t+=`🚚 Frete grátis\n`;
 if(c)t+=`\n🔍 Código no Mercado Livre: ${c}\n`;
 if(l)t+=`\n🛒 PEGAR OFERTA:\n${l}\n`;
 t+=`\n⚠️ Preço e estoque podem mudar.`;
 return t;
}
function usarAfiliado(){
 const c=document.getElementById('codigoAfiliado').value.trim();
 const l=document.getElementById('linkAfiliado').value.trim();
 if(!c && !l){document.getElementById('statusAfiliado').textContent='Informe o código ou o link.';return;}
 if(l && !/^https:\/\/meli\.la\//i.test(l)){
   document.getElementById('statusAfiliado').textContent='Confira o link: ele deve começar com https://meli.la/';
   return;
 }
 document.getElementById('codigo').value=c;
 document.getElementById('link').value=l;
 document.getElementById('statusAfiliado').textContent='✓ Oferta carregada no gerador abaixo.';
 document.getElementById('nome').scrollIntoView({behavior:'smooth'});
}
function gerar(){document.getElementById('saida').textContent=montar();}
function whatsapp(){window.open('https://wa.me/?text='+encodeURIComponent(montar()),'_blank');}
</script></body></html>
"""

OFFERS_PAGE = r"""
<!doctype html><html lang="pt-BR"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ofertas encontradas</title>
<style>
body{font-family:Arial;max-width:1000px;margin:auto;padding:16px;background:#f5f5f5;color:#222}
.card{background:#fff;border-radius:16px;padding:16px;margin:14px 0;box-shadow:0 2px 10px #0001}
img{width:150px;height:150px;object-fit:contain;float:left;margin-right:16px}.price{font-size:24px;font-weight:bold}
.old{text-decoration:line-through;color:#777}.off{font-weight:bold;color:#08783e}.btn{display:inline-block;background:#ffe600;color:#222;padding:11px 14px;border-radius:9px;text-decoration:none;font-weight:bold;border:0;margin:4px}
.clear{clear:both}.muted{color:#666}textarea{width:100%;box-sizing:border-box;min-height:150px;margin-top:10px;padding:10px}
</style></head><body>
<a href="/">← Voltar</a><h1>🔥 Ofertas encontradas</h1>
<p class="muted">Combina tendências semanais e mais vendidos. Preços podem mudar a qualquer momento.</p>
<div class="card"><b>Diagnóstico da busca</b><br>
{{ diagnostics.candidatos }} candidatos encontrados • {{ diagnostics.analisados }} produtos analisados •
{{ diagnostics.com_promocao }} com desconto identificado • {{ diagnostics.com_frete }} com frete grátis.
{% if fallback %}<p><b>Nenhum chegou a {{ minimum }}% nesta rodada.</b> Para não deixar a tela vazia, abaixo estão os melhores produtos analisados, inclusive sem desconto identificado.</p>{% endif %}
</div>
{% if not deals %}<div class="card">A API não devolveu produtos utilizáveis nesta rodada. Use o diagnóstico acima para identificar onde a busca parou.</div>{% endif %}
{% for d in deals %}
<div class="card">
{% if d.image %}<img src="{{ d.image }}">{% endif %}
<h3>{{ d.title }}</h3>
{% if d.old %}<div class="old">De R$ {{ "%.2f"|format(d.old) }}</div>{% endif %}
<div class="price">R$ {{ "%.2f"|format(d.price) }}</div>
{% if d.discount %}<div class="off">🔻 {{ d.discount }}% OFF</div>{% endif %}
{% if d.free_shipping %}<div>🚚 Frete grátis</div>{% endif %}
<p>🏆 Popular na categoria: posição {{ d.position }}</p>
<a class="btn" target="_blank" href="{{ d.permalink }}">Abrir produto</a>
<button class="btn" type="button" onclick='msg({{ d|tojson }}, {{ loop.index }})'>Preparar mensagem</button>
<div class="clear"></div>
<textarea id="m{{ loop.index }}" style="display:none"></textarea>
<button id="w{{ loop.index }}" class="btn" style="display:none" type="button" onclick="zap({{ loop.index }})">WhatsApp</button>
</div>
{% endfor %}
<script>
function br(v){return Number(v).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2})}
function msg(d,i){
 let t='🔥 OFERTA!\\n\\n'+d.title+'\\n';
 if(d.old)t+='De R$ '+br(d.old)+' por R$ '+br(d.price)+'\\n';
 else t+='Por R$ '+br(d.price)+'\\n';
 if(d.discount)t+='🔻 '+d.discount+'% OFF\\n';
 if(d.free_shipping)t+='🚚 Frete grátis\\n';
 t+='\\n⚠️ Agora gere/cole seu link de afiliado do Mercado Livre antes de divulgar.\\n';
 let a=document.getElementById('m'+i);a.value=t;a.style.display='block';
 document.getElementById('w'+i).style.display='inline-block';
}
function zap(i){
 let a=document.getElementById('m'+i);
 window.open('https://wa.me/?text='+encodeURIComponent(a.value),'_blank');
}
</script></body></html>
"""

PRODUCT_PAGE = """
<!doctype html><html lang="pt-BR"><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Produto</title><style>
body{font-family:Arial;max-width:800px;margin:auto;padding:18px;background:#f5f5f5}.card{background:#fff;padding:20px;border-radius:16px}
img{max-width:240px;border-radius:12px}.price{font-size:28px;font-weight:bold}.old{text-decoration:line-through;color:#777}
.btn{display:inline-block;background:#ffe600;padding:12px 16px;border-radius:10px;text-decoration:none;color:#222;font-weight:bold}
</style></head><body><div class="card">
<a href="/">← Voltar</a><h2>{{ p.title }}</h2>
{% if p.thumbnail %}<img src="{{ p.thumbnail }}">{% endif %}
{% if p.regular and p.current and p.regular > p.current %}<p class="old">R$ {{ "%.2f"|format(p.regular) }}</p>{% endif %}
{% if p.current %}<p class="price">R$ {{ "%.2f"|format(p.current) }}</p>{% endif %}
{% if p.discount %}<p>🔻 {{ p.discount }}% OFF</p>{% endif %}
<p>ID: {{ p.id }}</p>
{% if p.permalink %}<a class="btn" href="{{ p.permalink }}" target="_blank">Abrir produto</a>{% endif %}
<p><b>Para receber comissão:</b> use seu link de afiliado meli.la no gerador de mensagem.</p>
</div></body></html>
"""

def api_get(path, **kwargs):
    token = session.get("access_token")
    if not token:
        return None
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {token}"
    return requests.get(API_URL + path, headers=headers, timeout=20, **kwargs)

@app.get("/")
def home():
    return render_template_string(PAGE, connected=bool(session.get("access_token")))

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/login")
def login():
    if not ML_CLIENT_ID or not REDIRECT_URI:
        return "Configure ML_CLIENT_ID e BASE_URL no Render.", 500
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state
    params = {"response_type":"code","client_id":ML_CLIENT_ID,"redirect_uri":REDIRECT_URI,"state":state}
    return redirect(AUTH_URL + "?" + urlencode(params))

@app.get("/callback")
def callback():
    if request.args.get("state") != session.pop("oauth_state", None):
        return "State OAuth inválido. Tente conectar novamente.", 400
    code = request.args.get("code")
    if not code:
        return "Código de autorização não recebido.", 400
    data = {"grant_type":"authorization_code","client_id":ML_CLIENT_ID,"client_secret":ML_CLIENT_SECRET,
            "code":code,"redirect_uri":REDIRECT_URI}
    r = requests.post(TOKEN_URL, data=data, timeout=20)
    if not r.ok:
        return f"Falha ao obter token: {r.status_code} {r.text}", 400
    session["access_token"] = r.json()["access_token"]
    return redirect("/")

@app.get("/me")
def me():
    r = api_get("/users/me")
    if r is None: return redirect("/login")
    if not r.ok: return jsonify({"erro":"Não foi possível consultar a conta","status":r.status_code}), r.status_code
    data = r.json()
    return jsonify({k:data.get(k) for k in ("id","nickname","site_id")})


HUNT_TERMS = ["celular", "notebook", "smart tv", "cafeteira", "ferramentas", "games", "beleza", "autopeças"]

def auth_headers():
    return {"Authorization": f"Bearer {session.get('access_token','')}"}

def get_json(url, params=None):
    try:
        r = requests.get(url, headers=auth_headers(), params=params, timeout=15)
        return r.json() if r.ok else None
    except requests.RequestException:
        return None

def category_for(term):
    data = get_json(API_URL + "/sites/MLB/domain_discovery/search", {"q": term, "limit": 1})
    if isinstance(data, list) and data:
        return data[0].get("category_id")
    return None

def product_to_deal(entry):
    eid = entry.get("id")
    pos = entry.get("position")
    typ = entry.get("type")
    if not eid:
        return None

    if typ == "PRODUCT" or (eid.startswith("MLB") and not eid[3:].isdigit()):
        d = get_json(API_URL + f"/products/{eid}")
        if not d:
            return None
        winner = d.get("buy_box_winner") or {}
        price = winner.get("price")
        old = winner.get("original_price")
        if not price:
            return None
        pics = d.get("pictures") or []
        image = pics[0].get("url") if pics else None
        return {
            "id": winner.get("item_id") or eid,
            "title": d.get("name") or d.get("family_name") or eid,
            "price": price, "old": old,
            "free_shipping": (winner.get("shipping") or {}).get("free_shipping", False),
            "permalink": d.get("permalink") or "",
            "image": image, "position": pos
        }

    d = get_json(API_URL + f"/items/{eid}")
    if not d:
        return None
    price = d.get("price")
    old = d.get("original_price")
    # Official current sale price for marketplace context.
    sp = get_json(API_URL + f"/items/{eid}/sale_price", {"context": "channel_marketplace"})
    if sp:
        price = sp.get("amount") or price
        old = sp.get("regular_amount") or old
    # Also inspect all valid prices as a fallback.
    pd = get_json(API_URL + f"/items/{eid}/prices")
    if pd and pd.get("prices"):
        prices = pd["prices"]
        promo = next((x for x in prices if x.get("type") == "promotion" and not (x.get("conditions") or {}).get("context_restrictions")), None)
        standard = next((x for x in prices if x.get("type") == "standard" and not (x.get("conditions") or {}).get("context_restrictions")), None)
        if promo:
            price = promo.get("amount") or price
            old = promo.get("regular_amount") or (standard or {}).get("amount") or old
        elif standard:
            price = standard.get("amount") or price
    if not price:
        return None
    return {
        "id": eid, "title": d.get("title") or eid, "price": price, "old": old,
        "free_shipping": (d.get("shipping") or {}).get("free_shipping", False),
        "permalink": d.get("permalink") or "",
        "image": d.get("thumbnail"), "position": pos
    }

@app.get("/ofertas")
def ofertas():
    if not session.get("access_token"):
        return redirect("/login")
    try:
        minimum = max(0, min(90, int(request.args.get("min", "20"))))
    except ValueError:
        minimum = 20

    entries, seen = [], set()
    diagnostics = {"categorias":0, "candidatos":0, "analisados":0, "com_promocao":0, "com_frete":0}

    # 1) Best sellers from broad themes.
    for term in HUNT_TERMS:
        cat = category_for(term)
        if not cat:
            continue
        diagnostics["categorias"] += 1
        h = get_json(API_URL + f"/highlights/MLB/category/{cat}")
        if not h:
            continue
        for e in (h.get("content") or [])[:6]:
            eid=e.get("id")
            if eid and eid not in seen:
                seen.add(eid); entries.append(e)

    # 2) Weekly trends: discover categories from popular searches and add their best sellers.
    trends = get_json(API_URL + "/trends/MLB")
    if isinstance(trends, list):
        for t in trends[:12]:
            kw=t.get("keyword")
            if not kw: continue
            cat=category_for(kw)
            if not cat: continue
            h=get_json(API_URL + f"/highlights/MLB/category/{cat}")
            if not h: continue
            for e in (h.get("content") or [])[:3]:
                eid=e.get("id")
                if eid and eid not in seen:
                    seen.add(eid); entries.append(e)

    diagnostics["candidatos"]=len(entries)
    raw=[]
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures=[ex.submit(product_to_deal,e) for e in entries[:80]]
        for f in as_completed(futures):
            try:
                d=f.result()
                if not d: continue
                diagnostics["analisados"] += 1
                old,price=d.get("old"),d.get("price")
                d["discount"]=round((old-price)/old*100) if old and price and old>price else 0
                if d["discount"]>0: diagnostics["com_promocao"] += 1
                if d.get("free_shipping"): diagnostics["com_frete"] += 1
                raw.append(d)
            except Exception:
                pass

    filtered=[d for d in raw if d["discount"]>=minimum]
    filtered.sort(key=lambda x:(x["discount"],x.get("free_shipping",False),-(x.get("position") or 999)),reverse=True)

    # If the requested discount yields nothing, show the analyzed products instead of a blank screen.
    fallback=False
    deals=filtered
    if not deals:
        fallback=True
        deals=sorted(raw,key=lambda x:(x["discount"],x.get("free_shipping",False),-(x.get("position") or 999)),reverse=True)[:20]
    else:
        deals=deals[:30]

    return render_template_string(OFFERS_PAGE,deals=deals,minimum=minimum,
                                  diagnostics=diagnostics,fallback=fallback)

@app.get("/produto")
def produto():
    item_id = request.args.get("id","").strip().upper()
    if not item_id.startswith("MLB"):
        return "Use o ID do anúncio começando com MLB.", 400
    item = api_get(f"/items/{item_id}")
    if item is None: return redirect("/login")
    if not item.ok: return f"Produto não encontrado ({item.status_code}).", item.status_code
    d = item.json()
    current = d.get("price")
    regular = d.get("original_price")
    prices = api_get(f"/items/{item_id}/prices")
    if prices is not None and prices.ok:
        pdata = prices.json()
        plist = pdata.get("prices", [])
        promos = [x for x in plist if x.get("type") == "promotion"]
        standards = [x for x in plist if x.get("type") == "standard"]
        if promos:
            current = promos[0].get("amount") or current
            regular = promos[0].get("regular_amount") or regular
        elif standards:
            current = standards[0].get("amount") or current
    discount = None
    if current and regular and regular > current:
        discount = round((regular-current)/regular*100)
    p = {"id":item_id,"title":d.get("title"),"thumbnail":d.get("thumbnail"),
         "permalink":d.get("permalink"),"current":current,"regular":regular,"discount":discount}
    return render_template_string(PRODUCT_PAGE, p=p)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT","10000")))
