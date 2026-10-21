from __future__ import annotations

import unittest
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOUNDS = ("card", "coin", "deal", "jackpot", "knack", "turn", "win")


class SoundAssetTests(unittest.TestCase):
    def test_all_sounds_are_valid_mono_wav_files(self) -> None:
        for name in SOUNDS:
            path = ROOT / "assets" / "sounds" / f"{name}.wav"
            self.assertTrue(path.is_file(), path)
            with wave.open(str(path), "rb") as audio:
                self.assertEqual(audio.getnchannels(), 1)
                self.assertEqual(audio.getsampwidth(), 2)
                self.assertEqual(audio.getframerate(), 44_100)
                self.assertGreater(audio.getnframes(), 1_000)

    def test_windows_build_includes_sound_folder(self) -> None:
        build_script = (ROOT / "BUILD_KNACK_EXE.bat").read_text(encoding="utf-8")
        self.assertIn('--add-data "%CD%\\assets\\sounds;assets\\sounds"', build_script)


if __name__ == "__main__":
    unittest.main()
