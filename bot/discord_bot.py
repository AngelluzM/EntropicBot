from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands, tasks

from bot.game import DiceError, format_roll, roll_dice
from bot.players import PlayerStore, format_profile
from bot.rpg import CharacterSheetStore, CharacterSheetSyncer, format_binding
from bot.settings import Settings
from bot.systems import ConfigError, SystemClient, SystemRegistry


LOGGER = logging.getLogger(__name__)
MAX_DISCORD_MESSAGE_LENGTH = 1900


class RpgCog(commands.Cog):
    def __init__(
        self,
        bot: commands.Bot,
        settings: Settings,
        registry: SystemRegistry,
        client: SystemClient,
        sheet_store: CharacterSheetStore,
        player_store: PlayerStore,
    ) -> None:
        self._bot = bot
        self._settings = settings
        self._registry = registry
        self._client = client
        self._sheet_store = sheet_store
        self._player_store = player_store
        self._syncer = CharacterSheetSyncer(registry, client, sheet_store)

    async def cog_load(self) -> None:
        self.sync_character_sheets.change_interval(hours=self._settings.sheet_sync_interval_hours)
        self.sync_character_sheets.start()

    async def cog_unload(self) -> None:
        self.sync_character_sheets.cancel()

    @app_commands.command(name="ping", description="Confere se o bot esta online.")
    async def ping(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message("Estou online e pronto para ajudar seu RPG.", ephemeral=True)

    @app_commands.command(name="ajuda", description="Mostra os comandos do bot para gestao e jogo.")
    async def ajuda(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "**Gestao de jogadores**\n"
            "- `/registrar` cadastra voce no servidor de RPG\n"
            "- `/perfil` mostra seu cadastro e fichas vinculadas\n"
            "- `/jogadores` lista quantos jogadores estao cadastrados (staff)\n\n"
            "**Sistemas e fichas**\n"
            "- `/sistemas` lista os sistemas disponiveis\n"
            "- `/link` mostra o link de um sistema, como Aephirum\n"
            "- `/ficha-vincular` vincula sua ficha de personagem\n"
            "- `/fichas` mostra suas fichas acompanhadas\n"
            "- `/ficha-sincronizar` atualiza suas fichas agora\n\n"
            "**Jogo**\n"
            "- `/rolar` rola dados no formato XdY, por exemplo 1d20",
            ephemeral=True,
        )

    @app_commands.command(name="registrar", description="Cadastra voce como jogador do servidor de RPG.")
    @app_commands.describe(
        sistema="Sistema principal que voce usa, por exemplo aephirum.",
    )
    async def registrar(
        self,
        interaction: discord.Interaction,
        sistema: str | None = None,
    ) -> None:
        if sistema:
            try:
                system = self._registry.get_system(sistema)
                preferred_system = system.display_name
            except ConfigError as exc:
                await interaction.response.send_message(f"Sistema invalido: {exc}", ephemeral=True)
                return
        else:
            preferred_system = None

        profile = self._player_store.register(
            discord_user_id=interaction.user.id,
            display_name=interaction.user.display_name,
            preferred_system=preferred_system,
        )
        sheet_count = len(self._sheet_store.list_for_user(interaction.user.id))

        await interaction.response.send_message(
            "Cadastro concluido.\n\n" + format_profile(profile, sheet_count),
            ephemeral=True,
        )

    @app_commands.command(name="perfil", description="Mostra seu cadastro e fichas vinculadas.")
    async def perfil(self, interaction: discord.Interaction) -> None:
        profile = self._player_store.get(interaction.user.id)
        sheet_count = len(self._sheet_store.list_for_user(interaction.user.id))

        if profile is None:
            await interaction.response.send_message(
                "Voce ainda nao esta registrado. Use `/registrar` para comecar.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            format_profile(profile, sheet_count),
            ephemeral=True,
        )

    @app_commands.command(name="jogadores", description="Mostra quantos jogadores estao cadastrados.")
    async def jogadores(self, interaction: discord.Interaction) -> None:
        if not _is_staff(interaction, self._settings.staff_role_ids):
            await interaction.response.send_message(
                "Apenas staff pode usar este comando.",
                ephemeral=True,
            )
            return

        total = self._player_store.count()
        await interaction.response.send_message(
            f"Jogadores cadastrados no bot: **{total}**",
            ephemeral=True,
        )

    @app_commands.command(name="rolar", description="Rola dados no formato XdY, por exemplo 1d20.")
    @app_commands.describe(
        dados="Expressao de dados, por exemplo 1d20 ou 2d6.",
        motivo="Motivo opcional da rolagem.",
    )
    async def rolar(
        self,
        interaction: discord.Interaction,
        dados: str,
        motivo: str | None = None,
    ) -> None:
        try:
            result = roll_dice(dados)
        except DiceError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        await interaction.response.send_message(
            format_roll(result, interaction.user.mention, motivo),
            ephemeral=False,
        )

    @app_commands.command(name="sistemas", description="Lista os sistemas de RPG configurados.")
    async def sistemas(self, interaction: discord.Interaction) -> None:
        if not self._registry.systems:
            await interaction.response.send_message(
                "Nenhum sistema configurado ainda. Configure o arquivo systems.json.",
                ephemeral=False,
            )
            return

        lines: list[str] = []
        for system in self._registry.systems.values():
            description = f" - {system.description}" if system.description else ""
            link = system.link or "link ainda nao configurado"
            sheet_status = "fichas sincronizadas" if system.sheet else "sem sync de fichas"
            lines.append(f"**{system.display_name}**{description}\nLink: {link}\nStatus: {sheet_status}")

        await interaction.response.send_message(_truncate_message("\n\n".join(lines)), ephemeral=False)

    @app_commands.command(name="link", description="Mostra o link de acesso de um sistema de RPG.")
    @app_commands.describe(
        sistema="Sistema de RPG, por exemplo aephirum.",
    )
    async def link(self, interaction: discord.Interaction, sistema: str) -> None:
        try:
            system = self._registry.get_system(sistema)
        except ConfigError as exc:
            await interaction.response.send_message(f"Sistema nao encontrado: {exc}", ephemeral=True)
            return

        if not system.link:
            await interaction.response.send_message(
                f"O sistema {system.display_name} ainda nao tem link configurado.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"Link do **{system.display_name}**: {system.link}",
            ephemeral=False,
        )

    @app_commands.command(name="ficha-vincular", description="Vincula sua ficha de personagem ao bot.")
    @app_commands.describe(
        sistema="Sistema onde a ficha existe.",
        personagem_id="ID da sua ficha/personagem no sistema.",
        apelido="Nome curto opcional para identificar a ficha no Discord.",
    )
    async def ficha_vincular(
        self,
        interaction: discord.Interaction,
        sistema: str,
        personagem_id: str,
        apelido: str | None = None,
    ) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            system = self._registry.get_system(sistema)
            if not system.sheet:
                raise ConfigError(f"{system.display_name} ainda nao tem sync de ficha configurado")

            self._player_store.register(
                discord_user_id=interaction.user.id,
                display_name=interaction.user.display_name,
                preferred_system=system.display_name,
            )
            binding = self._sheet_store.upsert_binding(
                discord_user_id=interaction.user.id,
                system_name=system.name,
                character_id=personagem_id,
                alias=apelido,
            )
            synced = await self._syncer.sync_binding(binding)
        except ConfigError as exc:
            await interaction.followup.send(f"Nao consegui vincular a ficha: {exc}", ephemeral=True)
            return

        await interaction.followup.send(
            "Ficha vinculada. Ela sera atualizada automaticamente 1x ao dia.\n\n"
            + format_binding(synced, system),
            ephemeral=True,
        )

    @app_commands.command(name="fichas", description="Mostra as suas fichas acompanhadas pelo bot.")
    async def fichas(self, interaction: discord.Interaction) -> None:
        bindings = self._sheet_store.list_for_user(interaction.user.id)
        if not bindings:
            await interaction.response.send_message(
                "Voce ainda nao vinculou fichas. Use /ficha-vincular primeiro.",
                ephemeral=True,
            )
            return

        sections = [
            format_binding(binding, self._registry.systems.get(binding.system_name))
            for binding in bindings
        ]
        await interaction.response.send_message(
            _truncate_message("\n\n".join(sections)),
            ephemeral=True,
        )

    @app_commands.command(name="ficha-sincronizar", description="Atualiza suas fichas agora.")
    async def ficha_sincronizar(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)
        synced = await self._syncer.sync_user(interaction.user.id)
        if not synced:
            await interaction.followup.send(
                "Voce ainda nao vinculou fichas. Use /ficha-vincular primeiro.",
                ephemeral=True,
            )
            return

        sections = [
            format_binding(binding, self._registry.systems.get(binding.system_name))
            for binding in synced
        ]
        await interaction.followup.send(
            "Fichas sincronizadas.\n\n" + _truncate_message("\n\n".join(sections)),
            ephemeral=True,
        )

    @tasks.loop(hours=24)
    async def sync_character_sheets(self) -> None:
        synced = await self._syncer.sync_all()
        LOGGER.info("Synced %s RPG character sheets", len(synced))

    @sync_character_sheets.before_loop
    async def before_sync_character_sheets(self) -> None:
        await self._bot.wait_until_ready()

    @link.autocomplete("sistema")
    @ficha_vincular.autocomplete("sistema")
    @registrar.autocomplete("sistema")
    async def rpg_system_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        del interaction
        return _system_choices(self._registry, current)

class RpgBot(commands.Bot):
    def __init__(self, settings: Settings, registry: SystemRegistry) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix=settings.command_prefix, intents=intents)
        self._settings = settings
        self._registry = registry

    async def setup_hook(self) -> None:
        client = SystemClient(self._registry)
        store = CharacterSheetStore(self._settings.sheets_store_path)
        players = PlayerStore(self._settings.players_store_path)
        await self.add_cog(
            RpgCog(self, self._settings, self._registry, client, store, players)
        )

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


def _system_choices(registry: SystemRegistry, current: str) -> list[app_commands.Choice[str]]:
    current_lower = current.lower()
    choices: list[app_commands.Choice[str]] = []
    for system in registry.systems.values():
        searchable = f"{system.name} {system.display_name}".lower()
        if current_lower and current_lower not in searchable:
            continue

        choices.append(app_commands.Choice(name=system.display_name, value=system.name))

    return sorted(choices, key=lambda choice: choice.name.lower())[:25]


def _truncate_message(message: str) -> str:
    if len(message) <= MAX_DISCORD_MESSAGE_LENGTH:
        return message

    return f"{message[:MAX_DISCORD_MESSAGE_LENGTH]}\n... (mensagem truncada)"


def _is_staff(interaction: discord.Interaction, staff_role_ids: frozenset[int]) -> bool:
    if not staff_role_ids:
        return interaction.user.guild_permissions.manage_guild

    if not isinstance(interaction.user, discord.Member):
        return False

    return any(role.id in staff_role_ids for role in interaction.user.roles)
