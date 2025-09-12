import os
import json
import logging
import random

import discord
from discord.ext import commands

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("Environment variable DISCORD_TOKEN is required")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Caminho para o arquivo JSON onde as macros serão persistidas
MACROS_PATH = os.path.join(os.path.dirname(__file__), "macros.json")


def load_macros():
    try:
        with open(MACROS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_macros(data):
    with open(MACROS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)


macros = load_macros()


def roll_expression(expr: str):
    try:
        rolls, sides = map(int, expr.lower().split("d"))
    except Exception:
        return None, "Formato inválido. Use XdY, por exemplo 1d20"
    results = [random.randint(1, sides) for _ in range(rolls)]
    total = sum(results)
    return results, total


@bot.event
async def on_ready():
    logging.info("Connected as %s (ID: %s)", bot.user, bot.user.id)
    await bot.tree.sync()


@bot.command(name="roll")
async def roll(ctx, dice: str):
    results, total_or_msg = roll_expression(dice)
    if results is None:
        await ctx.send(total_or_msg)
        return
    await ctx.send(
        f"{ctx.author.mention} rolou {dice}: {results} (soma {total_or_msg})"
    )


quests = [
    "Escoltar uma caravana através de florestas sombrias.",
    "Investigar ruínas antigas em busca de relíquias.",
    "Libertar a aldeia do dragão que a aterroriza.",
]


@bot.command(name="quest")
async def quest(ctx):
    await ctx.send(f"A aventura de hoje: {random.choice(quests)}")


macro_group = discord.app_commands.Group(
    name="macro", description="Gerencia macros de rolagem"
)


@macro_group.command(name="add")
async def macro_add(
    interaction: discord.Interaction, nome: str, expressao: str
):
    uid = str(interaction.user.id)
    user_macros = macros.setdefault(uid, {})
    user_macros[nome] = expressao
    save_macros(macros)
    await interaction.response.send_message(
        f"Macro `{nome}` salva como `{expressao}`", ephemeral=True
    )


@macro_group.command(name="roll")
async def macro_roll(interaction: discord.Interaction, nome: str):
    uid = str(interaction.user.id)
    user_macros = macros.get(uid, {})
    expr = user_macros.get(nome)
    if not expr:
        await interaction.response.send_message(
            "Macro não encontrada", ephemeral=True
        )
        return
    results, total_or_msg = roll_expression(expr)
    if results is None:
        await interaction.response.send_message(total_or_msg, ephemeral=True)
        return
    await interaction.response.send_message(
        f"{interaction.user.mention} rolou {expr}: {results} (soma {total_or_msg})"
    )


@macro_group.command(name="list")
async def macro_list(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    user_macros = macros.get(uid, {})
    if not user_macros:
        await interaction.response.send_message(
            "Nenhuma macro encontrada.", ephemeral=True
        )
        return
    lines = [f"`{n}`: `{e}`" for n, e in user_macros.items()]
    await interaction.response.send_message(
        "Suas macros:\n" + "\n".join(lines), ephemeral=True
    )


bot.tree.add_command(macro_group)

if __name__ == "__main__":
    bot.run(TOKEN)
