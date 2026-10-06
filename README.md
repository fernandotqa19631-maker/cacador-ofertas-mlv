# Caçador de Ofertas MLV

Primeira versão do painel.

## Render
Build command:
`pip install -r requirements.txt`

Start command:
`gunicorn app:app`

Environment variables:
- `ML_CLIENT_ID` = App ID do Mercado Livre
- `ML_CLIENT_SECRET` = Client Secret (somente no Render; nunca no GitHub)
- `BASE_URL` = URL pública do Render, sem barra final
- `FLASK_SECRET_KEY` = valor aleatório longo

Redirect URI a cadastrar no Mercado Livre:
`<BASE_URL>/callback`

Esta versão não persiste refresh tokens em banco. Serve para validar com segurança o OAuth e o fluxo inicial.
