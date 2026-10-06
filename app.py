import os, secrets
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

PAGE = """
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
<div class="card"><h2>Consultar produto</h2>
<p class="muted">Cole o ID do anúncio começando com MLB.</p>
<form action="/produto" method="get">
<input name="id" placeholder="Ex.: MLB1234567890" required>
<button class="btn">Consultar</button>
</form></div>
{% endif %}

<div class="card"><h2>Gerador de mensagem</h2>
<div class="grid">
<input id="nome" placeholder="Nome do produto">
<input id="antes" placeholder="Preço anterior (ex.: 104,82)">
<input id="agora" placeholder="Preço atual (ex.: 81,75)">
<input id="desconto" placeholder="Desconto (ex.: 22)">
</div>
<input id="link" placeholder="Seu link de afiliado meli.la">
<label><input id="frete" type="checkbox" style="width:auto"> Frete grátis</label><br><br>
<button class="btn" onclick="gerar()">Gerar mensagem</button>
<button class="btn" onclick="whatsapp()">Compartilhar no WhatsApp</button>
<div id="saida" class="deal" style="margin-top:15px"></div>
</div>
<script>
function montar(){
 let n=document.getElementById('nome').value,a=document.getElementById('antes').value,
 p=document.getElementById('agora').value,d=document.getElementById('desconto').value,
 l=document.getElementById('link').value,f=document.getElementById('frete').checked;
 let t=`🔥 OFERTA!\n\n${n}\n`;
 if(a)t+=`De R$ ${a} `;
 if(p)t+=`por R$ ${p}\n`;
 if(d)t+=`🔻 ${d}% OFF\n`;
 if(f)t+=`🚚 Frete grátis\n`;
 t+=`\n🛒 PEGAR OFERTA:\n${l}\n\n⚠️ Preço e estoque podem mudar.`;
 return t;
}
function gerar(){document.getElementById('saida').textContent=montar();}
function whatsapp(){window.open('https://wa.me/?text='+encodeURIComponent(montar()),'_blank');}
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
