from facelessapp.models import WordTiming
from facelessapp.presets import VOICES
from facelessapp.tts import EspeakTTS, attach_punctuation, audio_duration, estimate_timings, synthesize


def test_estimate_timings_monotonic_within_duration():
    w = estimate_timings("Hello there, this is a test. Another sentence!", 4.0)
    assert len(w) == 8
    assert all(a.start <= a.end <= b.start + 1e-6 for a, b in zip(w, w[1:]))
    assert w[-1].end <= 4.0


def test_attach_punctuation_restores_tokens():
    words = [WordTiming("Hello", 0, .3), WordTiming("world", .3, .6), WordTiming("its", .7, .9), WordTiming("me", 1, 1.2)]
    out = attach_punctuation("Hello, world! It's me.", words)
    assert [w.text for w in out] == ["Hello,", "world!", "It's", "me."]


def test_espeak_synthesis(tmp_path, settings):
    wav = tmp_path / "v.wav"
    words, engine = synthesize(settings, "Testing the offline voice.", VOICES["en_male_deep"], wav)
    assert engine == "espeak" and wav.exists()
    assert 0.5 < audio_duration(wav) < 5
    assert len(words) == 4


def test_espeak_arabic(tmp_path):
    wav = tmp_path / "a.wav"
    words = EspeakTTS().synthesize("مرحبا بكم في القناة", VOICES["ar_male"], wav)
    assert len(words) == 4 and audio_duration(wav) > 0.5
