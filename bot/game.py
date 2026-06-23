from __future__ import annotations

import random
import re
from dataclasses import dataclass


_DICE_PATTERN = re.compile(r"^\s*(\d+)d(\d+)\s*$", re.IGNORECASE)


class DiceError(ValueError):
    """Raised when a dice expression is invalid."""


@dataclass(frozen=True)
class DiceRoll:
    expression: str
    rolls: list[int]
    sides: int

    @property
    def total(self) -> int:
        return sum(self.rolls)


def roll_dice(expression: str, rng: random.Random | None = None) -> DiceRoll:
    match = _DICE_PATTERN.match(expression)
    if not match:
        raise DiceError("Formato invalido. Use XdY, por exemplo 1d20 ou 2d6.")

    count = int(match.group(1))
    sides = int(match.group(2))

    if count < 1 or count > 20:
        raise DiceError("Quantidade de dados deve ser entre 1 e 20.")
    if sides < 2 or sides > 1000:
        raise DiceError("Numero de faces deve ser entre 2 e 1000.")

    roller = rng or random
    rolls = [roller.randint(1, sides) for _ in range(count)]
    return DiceRoll(expression=f"{count}d{sides}", rolls=rolls, sides=sides)


def format_roll(roll: DiceRoll, author_mention: str, reason: str | None = None) -> str:
    rolls_text = ", ".join(str(value) for value in roll.rolls)
    summary = f"{author_mention} rolou **{roll.expression}**"

    if reason:
        summary += f" ({reason})"

    if len(roll.rolls) == 1:
        summary += f": **{roll.total}**"
    else:
        summary += f": [{rolls_text}] = **{roll.total}**"

    return summary
