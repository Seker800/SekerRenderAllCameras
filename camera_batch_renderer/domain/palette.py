from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IdColor:
    key: str
    rgb: tuple[int, int, int]

    @property
    def hex(self) -> str:
        return "#" + "".join(f"{value:02X}" for value in self.rgb)


def _candidate(key: str, attempt: int) -> tuple[int, int, int]:
    digest = hashlib.blake2s(f"{key}\0{attempt}".encode(), digest_size=3).digest()
    # Keep labels visible and reserve black/near-black for the background.
    return tuple(48 + (value * 207 // 255) for value in digest)  # type: ignore[return-value]


def allocate_colors(keys: Iterable[str]) -> tuple[IdColor, ...]:
    used: set[tuple[int, int, int]] = {(0, 0, 0)}
    colors: list[IdColor] = []
    for key in sorted(set(keys)):
        attempt = 0
        while True:
            color = _candidate(key, attempt)
            if color not in used:
                used.add(color)
                colors.append(IdColor(key=key, rgb=color))
                break
            attempt += 1
    return tuple(colors)
