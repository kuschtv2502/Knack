"""Erzeugt die kleinen, lizenzfreien WAV-Effekte für Knack.

Das Spiel benötigt dieses Skript zur Laufzeit nicht. Es dokumentiert nur,
wie die mitgelieferten Audiodateien reproduzierbar entstanden sind.
"""

from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path


RATE = 44_100
OUTPUT = Path(__file__).resolve().parents[1] / "assets" / "sounds"


def envelope(position: float, duration: float, attack: float = 0.012) -> float:
    fade_in = min(1.0, position / attack) if attack else 1.0
    fade_out = min(1.0, max(0.0, duration - position) / 0.045)
    return fade_in * fade_out


def tone(frequency: float, duration: float, volume: float = 0.22) -> list[float]:
    samples = []
    for index in range(round(duration * RATE)):
        position = index / RATE
        value = math.sin(2 * math.pi * frequency * position)
        value += 0.22 * math.sin(2 * math.pi * frequency * 2 * position)
        samples.append(value * volume * envelope(position, duration))
    return samples


def silence(duration: float) -> list[float]:
    return [0.0] * round(duration * RATE)


def chord(frequencies: tuple[float, ...], duration: float, volume: float = 0.20) -> list[float]:
    tracks = [tone(frequency, duration, volume / len(frequencies)) for frequency in frequencies]
    return [sum(values) for values in zip(*tracks)]


def noise_click(duration: float = 0.085) -> list[float]:
    rng = random.Random(31)
    result = []
    for index in range(round(duration * RATE)):
        position = index / RATE
        decay = (1.0 - position / duration) ** 3
        paper = rng.uniform(-1.0, 1.0) * 0.10
        tap = math.sin(2 * math.pi * 185 * position) * 0.16
        result.append((paper + tap) * decay)
    return result


def metallic_coin() -> list[float]:
    duration = 0.34
    result = []
    for index in range(round(duration * RATE)):
        position = index / RATE
        decay = math.exp(-9.5 * position)
        value = (
            math.sin(2 * math.pi * 1_520 * position)
            + 0.55 * math.sin(2 * math.pi * 2_310 * position)
            + 0.28 * math.sin(2 * math.pi * 3_170 * position)
        )
        result.append(value * 0.12 * decay * min(1.0, position / 0.003))
    return result


def sequence(*parts: list[float]) -> list[float]:
    result: list[float] = []
    for part in parts:
        result.extend(part)
    return result


def write_wav(name: str, samples: list[float]) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    normalized = [max(-1.0, min(1.0, sample)) for sample in samples]
    payload = b"".join(struct.pack("<h", round(sample * 32_767)) for sample in normalized)
    with wave.open(str(OUTPUT / name), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(RATE)
        audio.writeframes(payload)


def main() -> None:
    write_wav("card.wav", noise_click())
    write_wav(
        "deal.wav",
        sequence(
            noise_click(0.06), silence(0.035), noise_click(0.06),
            silence(0.035), noise_click(0.07),
        ),
    )
    write_wav("turn.wav", sequence(tone(523.25, 0.09, 0.14), tone(659.25, 0.12, 0.14)))
    write_wav("coin.wav", metallic_coin())
    write_wav(
        "win.wav",
        sequence(tone(523.25, 0.13), tone(659.25, 0.13), tone(783.99, 0.25)),
    )
    write_wav(
        "knack.wav",
        sequence(chord((196.00, 293.66), 0.16, 0.30), chord((261.63, 392.00, 523.25), 0.38, 0.36)),
    )
    write_wav(
        "jackpot.wav",
        sequence(
            tone(523.25, 0.11), tone(659.25, 0.11), tone(783.99, 0.11),
            tone(1_046.50, 0.16), chord((523.25, 659.25, 783.99), 0.46, 0.40),
        ),
    )


if __name__ == "__main__":
    main()
