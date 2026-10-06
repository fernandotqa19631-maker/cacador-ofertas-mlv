import os, secrets
from urllib.parse import urlencode
import requests
from flask import Flask, redirect, request, session, render_template_string, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))

ML_CLIENT_ID = os.environ.get("ML_CLIENT_ID", "")
ML_CLIENT_SECRET = os.environ.get("ML_CLIENT_SECRET", "")
BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")
REDIRECT_URI = f"{BASE_URL}/callback" if BASE_URL else ""

AUTH_URL = "https://auth.mercadolivre.com.br/authorization"
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
API_URL = "https://api.mercadolibre.com"

PAGE = """
<!doctype html><html lang="pt-BR"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Caçador de Ofertas MLV</title>
<style>
body{font-family:Arial,sans-serif;max-width:850px;margin:auto;padding:22px;background:#f5f5f5;color:#222}
.card{background:white;border-radius:16px;padding:22px;margin:16px 0;box-shadow:0 2px 10px #0001}
h1{margin-bottom:6px}.btn{display:inline-block;background:#ffe600;color:#222;padding:13px 18px;border-radius:10px;text-decoration:none;font-weight:bold;border:0}
.ok{color:#08783e;font-weight:bold}.muted{color:#666}input,textarea{width:100%;box-sizing:border-box;padding:12px;margin:7px 0;border:1px solid #ccc;border-radius:9px}
button{cursor:pointer}.deal{white-space:pre-wrap;background:#f7f7f7;padding:14px;border-radius:10px}
</style></head><body>
<div class="card"><h1>🔎 Caçador de Ofertas MLV</h1>
<p class="muted">Primeira versão segura para conectar sua conta do Mercado Livre e preparar ofertas para compartilhamento.</p>
{% if connected %}<p class="ok">✓ Mercado Livre conectado</p>
<a class="btn" href="/me">Testar conexão</a>
{% else %}<a class="btn" href="/login">Conectar Mercado Livre</a>{% endif %}
</div>
<div class="card"><h2>Gerador de mensagem</h2>
<input id="nome" placeholder="Nome do produto">
<input id="antes" placeholder="Preço anterior (ex.: 104,82)">
<input id="agora" placeholder="Preço atual (ex.: 81,75)">
<input id="desconto" placeholder="Desconto (ex.: 22)">
<input id="link" placeholder="Seu link de afiliado meli.la">
<label><input id="frete" type="checkbox" style="width:auto"> Frete grátis</label><br><br>
<button class="btn" onclick="gerar()">Gerar mensagem</button>
<div id="saida" class="deal" style="margin-top:15px"></div>
</div>
<script>
function gerar(){
 let n=document.getElementById('nome').value, a=document.getElementById('antes').value,
 p=document.getElementById('agora').value,d=document.getElementById('desconto').value,
 l=document.getElementById('link').value,f=document.getElementById('frete').checked;
 let t=`🔥 OFERTA!\\n\\n${n}\\n`;
 if(a)t+=`De R$ ${a} `;
 if(p)t+=`por R$ ${p}\\n`;
 if(d)t+=`🔻 ${d}% OFF\\n`;
 if(f)t+=`🚚 Frete grátis\\n`;
 t+=`\\n🛒 PEGAR OFERTA:\\n${l}\\n\\n⚠️ Preço e estoque podem mudar.`;
 document.getElementById('saida').textContent=t;
}
</script></body></html>
"""

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
    params = {
        "response_type": "code",
        "client_id": ML_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "state": state,
    }
    return redirect(AUTH_URL + "?" + urlencode(params))

@app.get("/callback")
def callback():
    if request.args.get("state") != session.pop("oauth_state", None):
        return "State OAuth inválido. Tente conectar novamente.", 400
    code = request.args.get("code")
    if not code:
        return "Código de autorização não recebido.", 400
    data = {
        "grant_type": "authorization_code",
        "client_id": ML_CLIENT_ID,
        "client_secret": ML_CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    r = requests.post(TOKEN_URL, data=data, timeout=20)
    if not r.ok:
        return f"Falha ao obter token: {r.status_code} {r.text}", 400
    tok = r.json()
    session["access_token"] = tok["access_token"]
    # V1: refresh token não é persistido em banco; não exibimos tokens na tela/log.
    return redirect("/")

@app.get("/me")
def me():
    token = session.get("access_token")
    if not token:
        return redirect("/login")
    r = requests.get(API_URL + "/users/me",
                     headers={"Authorization": f"Bearer {token}"}, timeout=20)
    if not r.ok:
        return jsonify({"erro": "Não foi possível consultar a conta", "status": r.status_code}), r.status_code
    data = r.json()
    safe = {k: data.get(k) for k in ("id", "nickname", "site_id")}
    return jsonify(safe)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
