# RPG Discord Bot

Bot em Python para ajudar jogadores de um servidor de RPG a acessar os sistemas
da mesa e acompanhar fichas de personagem pelo Discord.

## O que ele faz

- `/ping` verifica se o bot esta online.
- `/sistemas` lista os sistemas de RPG configurados e seus links.
- `/link sistema` mostra o link de acesso de um sistema, como Aephirum.
- `/ficha-vincular sistema personagem_id apelido` vincula uma ficha ao usuario.
- `/fichas` mostra as fichas vinculadas ao usuario e o ultimo cache salvo.
- `/ficha-sincronizar` atualiza manualmente as fichas do usuario.

As fichas sao sincronizadas automaticamente 1x ao dia. Comandos de ficha usam
respostas efemeras por padrao para evitar expor informacoes do personagem no
canal.

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
python3 -m pip install -r requirements.txt
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
- `SHEETS_STORE_PATH`: arquivo local onde o bot guarda vinculos/cache de fichas.
- `SHEET_SYNC_INTERVAL_HOURS`: intervalo de sync; mantenha `24` em producao.
- tokens dos seus sistemas, como `AEPHIRUM_API_TOKEN`.

7. Crie sua configuracao de sistemas:

```bash
cp systems.example.json systems.json
```

8. Rode o bot:

```bash
python3 main.py
```

## Configurando sistemas de RPG

Cada sistema pode ter:

- `display_name`: nome amigavel mostrado no Discord.
- `description`: resumo do sistema.
- `link`: URL que o comando `/link` vai mostrar aos jogadores.
- `base_url`: URL base da API usada para buscar fichas.
- `headers`: headers HTTP opcionais, geralmente com token.
- `sheet`: qual acao busca a ficha de personagem.
- `actions`: chamadas HTTP internas usadas pelo bot.

Tokens e segredos devem ficar em variaveis de ambiente e podem ser referenciados
com `${NOME_DA_VARIAVEL}`.

```json
{
  "systems": {
    "aephirum": {
      "display_name": "Aephirum",
      "description": "Sistema principal de fichas do servidor",
      "link": "https://aephirum.example.com",
      "base_url": "https://api.aephirum.example.com",
      "headers": {
        "Authorization": "Bearer ${AEPHIRUM_API_TOKEN}"
      },
      "sheet": {
        "action": "character-sheet",
        "id_payload_key": "character_id"
      },
      "actions": {
        "character-sheet": {
          "description": "Busca uma ficha pelo ID usado no Aephirum",
          "method": "GET",
          "path": "/characters/{character_id}"
        }
      }
    }
  }
}
```

No Discord:

```text
/link sistema:aephirum
/ficha-vincular sistema:aephirum personagem_id:abc123 apelido:Arvand
/fichas
```

## Como a sincronizacao diaria funciona

Quando um usuario usa `/ficha-vincular`, o bot salva a relacao:

- ID do usuario no Discord
- sistema de RPG
- ID da ficha/personagem no sistema
- apelido opcional
- ultimo resumo sincronizado

Depois disso, a tarefa diaria percorre todos os vinculos em `SHEETS_STORE_PATH`,
chama a acao configurada em `sheet.action` para cada ficha e atualiza o cache
local. Se a API retornar JSON com campos comuns como `name`, `level`, `class`,
`race` ou `status`, o bot mostra um resumo curto; se nao, ele guarda um resumo
do corpo retornado.

## Boas praticas

- Exponha apenas a acao necessaria para buscar fichas.
- Use tokens com escopo minimo para o bot.
- Evite retornar segredos nas respostas das APIs.
- Se as fichas tiverem informacoes privadas, mantenha os comandos de ficha como
  respostas efemeras.
- Durante desenvolvimento, use `DISCORD_GUILD_ID` para sincronizar comandos
  rapidamente em um servidor de teste.
