from dataclasses import asdict, dataclass

ERROR = 'error'
WARNING = 'warning'


@dataclass(frozen=True)
class Finding:
    rule_id: str            # 'noi_dung.line_spacing'
    severity: str           # ERROR | WARNING
    zone: str
    location: str           # 'Đoạn 14'
    expected: str
    actual: str
    suggestion: str = ''

    def as_dict(self):
        return asdict(self)
