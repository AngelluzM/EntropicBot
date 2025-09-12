import os
import logging
import random
import json
import re

import discord
from discord.ext import commands

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("Environment variable DISCORD_TOKEN is required")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)

DATA_FILE = "sheets.json"


def load_sheets():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_sheets():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(sheets, f)


sheets = load_sheets()


def parse_dice(dice_str: str):
    match = re.fullmatch(r"(\d*)d(\d+)", dice_str)
    if match:
        rolls = int(match.group(1) or 1)
        sides = int(match.group(2))
        return rolls, sides
    if dice_str.isdigit():
        return 1, int(dice_str)
    raise ValueError


@bot.event
async def on_ready():
    logging.info("Connected as %s (ID: %s)", bot.user, bot.user.id)


@bot.group(name="ficha", invoke_without_command=True)
async def ficha(ctx):
    await ctx.send("Use /ficha set <atributo> <valor> ou /ficha show")


@ficha.command(name="set")
async def ficha_set(ctx, atributo: str, valor: str):
    user_id = str(ctx.author.id)
    sheet = sheets.setdefault(user_id, {})
    sheet[atributo] = valor
    save_sheets()
    await ctx.send(f"Atributo {atributo} definido como {valor} para {ctx.author.mention}")


@ficha.command(name="show")
async def ficha_show(ctx):
    user_id = str(ctx.author.id)
    sheet = sheets.get(user_id)
    if not sheet:
        await ctx.send("Você ainda não tem atributos definidos.")
        return
    attrs = "\n".join(f"{k}: {v}" for k, v in sheet.items())
    await ctx.send(f"Ficha de {ctx.author.mention}:\n{attrs}")


@bot.command(name="roll")
async def roll(ctx, dice: str):
    user_id = str(ctx.author.id)
    sheet = sheets.get(user_id, {})
    if dice in sheet:
        dice = str(sheet[dice])
    try:
        rolls, sides = parse_dice(dice.lower())
    except Exception:
        await ctx.send("Formato inválido. Use XdY, por exemplo 1d20")
        return
    results = [random.randint(1, sides) for _ in range(rolls)]
    total = sum(results)
    await ctx.send(f"{ctx.author.mention} rolou {dice}: {results} (soma {total})")


quests = [
    "Escoltar uma caravana através de florestas sombrias.",
    "Investigar ruínas antigas em busca de relíquias.",
    "Libertar a aldeia do dragão que a aterroriza.",
]


@bot.command(name="quest")
async def quest(ctx):
    await ctx.send(f"A aventura de hoje: {random.choice(quests)}")


if __name__ == "__main__":
    bot.run(TOKEN)
