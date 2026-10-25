"""Engine abstraction: one class per TTS project."""

from __future__ import annotations

from dataclasses import dataclass, field


class TTSError(RuntimeError):
    """Raised when an engine cannot synthesise the request."""


@dataclass(slots=True)
class Voice:
    id: str
    label: str
    lang: str = "yue"
    note: str = ""


@dataclass(slots=True)
class Probe:
    available: bool
    detail: str = ""
    voices: list[Voice] = field(default_factory=list)


class Engine:
    """Base class. `kind` is one of local / online / remote."""

    id: str = ""
    name: str = ""
    vendor: str = ""
    kind: str = "local"
    category: str = "ready"          # quality | baseline | selfhost | paid
    free: bool = True
    requires_key: bool = False
    accepts_key: bool = False
    description: str = ""
    homepage: str = ""
    supports_rate: bool = False
    supports_pitch: bool = False

    async def probe(self) -> Probe:  # pragma: no cover - interface only
        raise NotImplementedError

    async def synth(
        self, text: str, voice: str, rate: int = 0, pitch: int = 0, api_key: str = ""
    ) -> tuple[bytes, str, str]:  # pragma: no cover - interface only
        """Return (audio bytes, mime type, file extension)."""
        raise NotImplementedError

    def meta(self, probe: Probe) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "vendor": self.vendor,
            "kind": self.kind,
            "category": self.category,
            "free": self.free,
            "requires_key": self.requires_key,
            "accepts_key": self.accepts_key,
            "description": self.description,
            "homepage": self.homepage,
            "supports_rate": self.supports_rate,
            "supports_pitch": self.supports_pitch,
            "available": probe.available,
            "detail": probe.detail,
            "voices": [
                {"id": v.id, "label": v.label, "lang": v.lang, "note": v.note}
                for v in probe.voices
            ],
        }
