"""Configuration helpers for the biomedical platform."""

from dataclasses import dataclass


@dataclass
class AppConfig:
    project_name: str = 'Biomedical Signal Visualizer'
    default_fs: int = 250
    safe_mode: bool = True
    language: str = 'es'
    rural_mode: bool = True
    low_bandwidth: bool = True

    def as_dict(self):
        return {
            'project_name': self.project_name,
            'default_fs': self.default_fs,
            'safe_mode': self.safe_mode,
            'language': self.language,
            'rural_mode': self.rural_mode,
            'low_bandwidth': self.low_bandwidth,
        }
