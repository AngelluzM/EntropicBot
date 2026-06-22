from __future__ import annotations

import logging

from bot.discord_bot import RpgBot
from bot.settings import load_settings
from bot.systems import SystemRegistry


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = load_settings()
    registry = SystemRegistry.from_file(settings.systems_config_path)
    bot = RpgBot(settings, registry)
    bot.run(settings.discord_token)
