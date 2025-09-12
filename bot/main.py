import os
import logging
import random
import re

import discord
from discord import app_commands
from discord.ext import commands

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("Environment variable DISCORD_TOKEN is required")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


class NPC(commands.GroupCog, name="npc"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.names: dict[int, str] = {}

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if discord.utils.get(interaction.user.roles, name="mestre") is None:
            await interaction.response.send_message(
                "Somente usuários com o papel @mestre podem usar este comando.",
                ephemeral=True,
            )
            return False
        return True

    @app_commands.command(name="dizer", description="Envia uma mensagem como NPC.")
    async def dizer(self, interaction: discord.Interaction, mensagem: str):
        name = self.names.get(interaction.guild_id, "NPC")
        await interaction.response.send_message(f"**[{name}]** {mensagem}")

    @app_commands.command(name="roll", description="Rola dados como NPC.")
    async def roll(self, interaction: discord.Interaction, expressao: str):
        match = re.fullmatch(r"(\d*)d(\d+)([+-]\d+)?", expressao.replace(" ", ""))
        if not match:
            await interaction.response.send_message(
                "Formato inválido. Use XdY ou XdY+Z.", ephemeral=True
            )
            return
        qtd = int(match.group(1)) if match.group(1) else 1
        lados = int(match.group(2))
        mod = int(match.group(3)) if match.group(3) else 0

        resultados = [random.randint(1, lados) for _ in range(qtd)]
        total = sum(resultados) + mod
        mod_str = f"{mod:+}" if mod else ""
        name = self.names.get(interaction.guild_id, "NPC")
        await interaction.response.send_message(
            f"**[{name}]** rolou {qtd}d{lados}{mod_str}: {resultados} (total {total})"
        )

    @app_commands.command(name="setnome", description="Define o nome do NPC.")
    async def setnome(self, interaction: discord.Interaction, nome: str):
        self.names[interaction.guild_id] = nome
        await interaction.response.send_message(
            f"Nome do NPC definido para {nome}.", ephemeral=True
        )


@bot.event
async def setup_hook():
    await bot.add_cog(NPC(bot))
    await bot.tree.sync()


@bot.event
async def on_ready():
    logging.info("Connected as %s (ID: %s)", bot.user, bot.user.id)


@bot.command(name="roll")
async def roll_command(ctx, dice: str):
    try:
        rolls, sides = map(int, dice.lower().split("d"))
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
