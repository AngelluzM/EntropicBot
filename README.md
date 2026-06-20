# Discord Systems Bot

Bot em Python para acionar seus sistemas a partir do Discord usando comandos slash.

## O que ele faz

- `/ping` verifica se o bot esta online.
- `/systems` lista os sistemas e acoes configuradas.
- `/run system action payload` executa uma acao HTTP configurada em `systems.json`.

As respostas sao efemeras por padrao, entao apenas quem executou o comando ve o
retorno.

## Setup

1. Crie um app no [Discord Developer Portal](https://discord.com/developers/applications).
2. Na aba **Bot**, crie o bot e copie o token.
3. Na aba **OAuth2 > URL Generator**, selecione:
   - `bot`
   - `applications.commands`
   - permissoes: `Send Messages` e `Use Slash Commands`
4. Use a URL gerada para adicionar o bot ao seu servidor.
5. Instale dependencias:

```bash
python -m pip install -r requirements.txt
```

6. Configure variaveis de ambiente:

```bash
cp .env.example .env
```

Edite `.env` e preencha:

- `DISCORD_TOKEN`: token do bot.
- `DISCORD_GUILD_ID`: opcional, ID do servidor para sincronizar slash commands
  imediatamente em desenvolvimento.
- `SYSTEMS_CONFIG_PATH`: caminho do arquivo de sistemas, por padrao `systems.json`.
- tokens dos seus sistemas, como `ORDERS_API_TOKEN`.

7. Crie sua configuracao de sistemas:

```bash
cp systems.example.json systems.json
```

8. Rode o bot:

```bash
python main.py
```

## Configurando sistemas

Cada sistema tem uma `base_url`, headers opcionais e uma lista de acoes. Tokens e
segredos devem ficar em variaveis de ambiente e podem ser referenciados com
`${NOME_DA_VARIAVEL}`.

```json
{
  "systems": {
    "orders": {
      "description": "API interna de pedidos",
      "base_url": "https://orders.example.com",
      "headers": {
        "Authorization": "Bearer ${ORDERS_API_TOKEN}"
      },
      "actions": {
        "find": {
          "description": "Busca um pedido por ID",
          "method": "GET",
          "path": "/orders/{order_id}"
        }
      }
    }
  }
}
```

No Discord:

```text
/run system:orders action:find payload:{"order_id":"123"}
```

Para metodos `GET` e `DELETE`, o payload tambem e enviado como query string.
Para `POST`, `PUT` e `PATCH`, o payload e mesclado ao corpo JSON configurado na
acao.

## Boas praticas

- Crie acoes pequenas e explicitas em vez de expor endpoints genericos demais.
- Use tokens com escopo minimo para o bot.
- Evite retornar segredos nas respostas das APIs, pois o bot exibira o corpo da
  resposta no Discord.
- Durante desenvolvimento, use `DISCORD_GUILD_ID` para sincronizar comandos
  rapidamente em um servidor de teste.
