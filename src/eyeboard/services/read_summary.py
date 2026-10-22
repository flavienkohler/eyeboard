"""What was detected or chosen when a file was read, in a form the interface can list."""

from dataclasses import dataclass

from eyeboard.i18n import t
from eyeboard.models import CsvReadReport, DateSettings, ReadOptions

_AUTO_PREFIX = "Auto-detected "


@dataclass(frozen=True, slots=True)
class DetectedSetting:
    """One reading setting, and whether EyeBoard found it rather than being told."""

    name: str
    value: str
    auto: bool

    def text(self) -> str:
        value = t(self.value)
        return t("{value} (auto)", value=value) if self.auto else value


def detected_settings(
    report: CsvReadReport,
    options: ReadOptions,
    date_settings: DateSettings,
    date_order: str | None,
) -> list[DetectedSetting]:
    """List the separator, decimal, encoding, header and date settings in effect."""
    separator = report.separator_label.removeprefix(_AUTO_PREFIX)
    settings = [
        DetectedSetting("Separator", separator, report.separator_auto_detected),
        DetectedSetting("Decimal", report.decimal_label, False),
        DetectedSetting("Encoding", report.encoding_label, options.encoding is None),
        DetectedSetting("Header", report.header_label, False),
    ]
    if date_settings.column is None:
        settings.append(DetectedSetting("Date column", "none selected", False))
    else:
        auto = date_settings.mode == "Auto-detect" and not date_settings.format
        settings.append(
            DetectedSetting("Date column", f"`{date_settings.column}`", False)
        )
        settings.append(DetectedSetting("Date order", date_order or "unknown", auto))
    return settings
