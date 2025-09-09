 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a//dev/null b/bot/main.py
index 0000000000000000000000000000000000000000..2ba3629588eda18a09053977db3f3de3fbd118a7 100644
--- a//dev/null
+++ b/bot/main.py
@@ -0,0 +1,46 @@
+import os
+import logging
+import random
+
+import discord
+from discord.ext import commands
+
+logging.basicConfig(level=logging.INFO)
+
+TOKEN = os.getenv("DISCORD_TOKEN")
+if not TOKEN:
+    raise RuntimeError("Environment variable DISCORD_TOKEN is required")
+
+intents = discord.Intents.default()
+intents.message_content = True
+
+bot = commands.Bot(command_prefix="!", intents=intents)
+
+@bot.event
+async def on_ready():
+    logging.info("Connected as %s (ID: %s)", bot.user, bot.user.id)
+
+@bot.command(name="roll")
+async def roll(ctx, dice: str):
+    try:
+        rolls, sides = map(int, dice.lower().split("d"))
+    except Exception:
+        await ctx.send("Formato inválido. Use XdY, por exemplo 1d20")
+        return
+
+    results = [random.randint(1, sides) for _ in range(rolls)]
+    total = sum(results)
+    await ctx.send(f"{ctx.author.mention} rolou {dice}: {results} (soma {total})")
+
+quests = [
+    "Escoltar uma caravana através de florestas sombrias.",
+    "Investigar ruínas antigas em busca de relíquias.",
+    "Libertar a aldeia do dragão que a aterroriza.",
+]
+
+@bot.command(name="quest")
+async def quest(ctx):
+    await ctx.send(f"A aventura de hoje: {random.choice(quests)}")
+
+if __name__ == "__main__":
+    bot.run(TOKEN)
 
EOF
)
