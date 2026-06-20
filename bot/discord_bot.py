from __future__ import annotations

import json
import logging
from collections.abc import Iterable

import discord
from discord import app_commands
from discord.ext import commands

from bot.settings import Settings
from bot.systems import ConfigError, SystemClient, SystemRegistry


LOGGER = logging.getLogger(__name__)
MAX_DISCORD_MESSAGE_LENGTH = 1900


class SystemsCog(commands.Cog):
    def __init__(self, registry: SystemRegistry, client: SystemClient) -> None:
        self._registry = registry
        self._client = client

    @app_commands.command(name="ping", description="Confere se o bot esta online.")
    async def ping(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("Estou online e pronto para ajudar.", ephemeral=True)

    @app_commands.command(name="systems", description="Lista os sistemas e acoes disponiveis.")
    async def systems(self, interaction: discord.Interaction) -> None:
        if not self._registry.systems:
            await interaction.response.send_message(
                "Nenhum sistema configurado ainda. Configure o arquivo systems.json.",
                ephemeral=True,
            )
            return

        lines: list[str] = []
        for system in self._registry.systems.values():
            description = f" - {system.description}" if system.description else ""
            lines.append(f"**{system.name}**{description}")
            for action in system.actions.values():
                action_description = f" - {action.description}" if action.description else ""
                lines.append(f"  /run `{system.name}` `{action.name}`{action_description}")

        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @app_commands.command(name="run", description="Executa uma acao configurada em um sistema.")
    @app_commands.describe(
        system="Nome do sistema configurado em systems.json.",
        action="Nome da acao dentro do sistema.",
        payload="JSON opcional com parametros para path, query string ou corpo da requisicao.",
    )
    async def run(
        self,
        interaction: discord.Interaction,
        system: str,
        action: str,
        payload: str = "{}",
    ) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            parsed_payload = _parse_payload(payload)
            result = await self._client.execute(system, action, parsed_payload)
        except ConfigError as exc:
            await interaction.followup.send(f"Configuracao invalida: {exc}", ephemeral=True)
            return
        except json.JSONDecodeError as exc:
            await interaction.followup.send(f"Payload precisa ser JSON valido: {exc.msg}", ephemeral=True)
            return
        except Exception:
            LOGGER.exception("Failed to execute %s.%s", system, action)
            await interaction.followup.send(
                "Nao consegui executar essa acao. Veja os logs do bot para detalhes.",
                ephemeral=True,
            )
            return

        status = "OK" if result.ok else "ERRO"
        body = result.body.strip() or "(sem corpo na resposta)"
        if len(body) > MAX_DISCORD_MESSAGE_LENGTH:
            body = f"{body[:MAX_DISCORD_MESSAGE_LENGTH]}\n... (resposta truncada)"

        await interaction.followup.send(
            f"{status} `{result.status}` de `{system}.{action}`\n```text\n{body}\n```",
            ephemeral=True,
        )

    @run.autocomplete("system")
    async def system_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        del interaction
        return _choices(self._registry.systems.keys(), current)

    @run.autocomplete("action")
    async def action_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        system_name = getattr(interaction.namespace, "system", None)
        if not system_name or system_name not in self._registry.systems:
            return []

        actions = self._registry.systems[system_name].actions.keys()
        return _choices(actions, current)


class SystemsBot(commands.Bot):
    def __init__(self, settings: Settings, registry: SystemRegistry) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix=settings.command_prefix, intents=intents)
        self._settings = settings
        self._registry = registry

    async def setup_hook(self) -> None:
        await self.add_cog(SystemsCog(self._registry, SystemClient(self._registry)))

        if self._settings.discord_guild_id:
            guild = discord.Object(id=self._settings.discord_guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            LOGGER.info("Synced %s commands to guild %s", len(synced), self._settings.discord_guild_id)
            return

        synced = await self.tree.sync()
        LOGGER.info("Synced %s global commands", len(synced))

    async def on_ready(self) -> None:
        LOGGER.info("Connected as %s (ID: %s)", self.user, self.user.id if self.user else "unknown")


def _parse_payload(payload: str) -> dict[str, object]:
    if not payload.strip():
        return {}

    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise ConfigError("Payload must be a JSON object")

    return parsed


def _choices(values: Iterable[object], current: str) -> list[app_commands.Choice[str]]:
    current_lower = current.lower()
    matches = [
        str(value)
        for value in values
        if not current_lower or current_lower in str(value).lower()
    ]
    return [app_commands.Choice(name=value, value=value) for value in sorted(matches)[:25]]
