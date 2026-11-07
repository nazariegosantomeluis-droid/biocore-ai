"""Tanda 2 (2026-11-07, Art. I): la documentación también puede ser una fachada.

Fija lo que se corrigió: CLAUDE.md corto y sin referencias a archivos que no existen, ningún
PLAN.md citado, avisos de terceros íntegros (sin texto truncado), docs obsoletos fuera, y ni
una sola afirmación de SHAP/LIME fuera de los registros históricos.
"""

import re
import subprocess
from pathlib import Path

import pytest

TEXT_EXT = (".py", ".md", ".txt", ".toml", ".bat", ".ps1")
HISTORIA = {"CHANGELOG.md", "docs/INVENTARIO_BIOCORE_2026-11-05.md"}
ESTE_ARCHIVO = "tests/test_docs_honest_tanda2.py"


def _tracked():
    try:
        out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("git no disponible")
    return [p for p in out.splitlines() if p]


def _text(path):
    return Path(path).read_text(encoding="utf-8", errors="replace")


def test_no_file_cites_plan_md_except_history_and_the_guide_that_says_it_does_not_exist():
    permitidos = HISTORIA | {"CLAUDE.md", ESTE_ARCHIVO}
    for p in _tracked():
        if p.endswith(TEXT_EXT) and p not in permitidos and Path(p).exists():
            assert "PLAN.md" not in _text(p), p


def test_claude_md_is_short_and_every_file_it_names_exists():
    text = _text("CLAUDE.md")
    assert len(text.splitlines()) < 200
    tracked = set(_tracked())
    suffixes = tracked | {p.rsplit("/", 1)[-1] for p in tracked}
    for token in set(re.findall(r"`([A-Za-z0-9_\-./]+\.(?:py|md|txt|toml|bat|ps1))`", text)):
        if token == "PLAN.md":  # CLAUDE.md lo nombra solo para decir que no existe
            continue
        assert token in suffixes or any(p.endswith("/" + token) for p in tracked), f"CLAUDE.md cita {token}, que no existe"


def test_claude_md_states_the_ups_domains_the_schema_really_models():
    from datetime import datetime, timezone

    from domain.physiology.state import DomainState, UnifiedPhysiologicalState
    from domain.physiology.state.schema import Provenance

    dominios = list(UnifiedPhysiologicalState(
        patient_id="", timestamp=datetime.now(timezone.utc),
        cardiovascular=DomainState(domain="cardiovascular"), respiratory=DomainState(domain="respiratory"),
    ).all_domains())
    text = _text("CLAUDE.md")
    for d in dominios:
        assert f"`{d}`" in text, d
    for p in Provenance:
        assert f"`{p.name}`" in text, p.name


def test_claude_md_menu_matches_the_real_hubs():
    import ast

    src = Path("app/main.py").read_text(encoding="utf-8")
    hubs = ast.literal_eval(re.search(r"^HUBS = (\{.*?^\})", src, re.S | re.M).group(1))
    text = _text("CLAUDE.md")
    assert f"{len(hubs)} hubs y {sum(len(v) for v in hubs.values())} entradas" in text
    for hub in hubs:
        assert hub in text, hub


def test_third_party_notices_are_complete_and_not_truncated():
    text = _text("THIRD_PARTY_NOTICES.md")
    assert "[...]" not in text
    assert "Copyright 2016-2025 Stanford University, The Regents of the University of California, and others." in text
    assert "“AS IS”" in text  # comillas curvas del original, no las rectas de una copia a mano
    for doi in ("10.13026/kfzx-aw45", "10.13026/C2F305", "10.1038/s41597-020-0495-6"):
        assert doi in text, doi
    assert "PENDIENTE" in text  # lo que no se pudo obtener de su fuente figura como pendiente
    nested = _text("domain/physiology/hemodynamics/THIRD_PARTY_NOTICES.md")
    assert "[...]" not in nested


def test_obsolete_specialty_docs_are_gone_and_the_mixed_ones_carry_the_banner():
    assert not Path("docs/especialidades/README.md").exists()
    assert not Path("docs/especialidades/QUICK_START_USER_MANUAL.md").exists()
    for name in ("CARDIOLOGIA_EXPLICITO_PRINCIPIANTES.md", "NEUROLOGIA_EXPLICITO_PRINCIPIANTES.md"):
        text = _text(f"docs/especialidades/{name}")
        assert text.startswith("> **Obsoleto en parte: describe una versión anterior; la referencia vigente es [CLAUDE.md]")
        for frase in ("IA compara con millones", "IA dice:", "Confianza: 8", "PREDICCIÓN AUTOMÁTICA"):
            assert frase not in text, (name, frase)


def test_no_literal_shap_lime_claim_outside_history_and_tests():
    for p in _tracked():
        if p.endswith(TEXT_EXT) and p not in HISTORIA and not p.startswith("tests/") and Path(p).exists():
            assert "SHAP/LIME" not in _text(p), p


def test_readme_no_longer_makes_the_false_claims():
    text = _text("README.md")
    assert "Los tres hubs" not in text
    assert "basado en un modelo publicado" not in text
    assert "activación fisiológica real" not in text
    assert "Requiere Python 3.10+" not in text
    assert "THIRD_PARTY_NOTICES.md" in text


def test_ui_text_about_ups_domains_is_not_hardcoded_anymore():
    src = Path("app/supermodules/twin_shell/pages.py").read_text(encoding="utf-8")
    assert "solo cardiovascular y" not in src
    assert "AHI y eventos de apnea (en corrección)" in Path("app/supermodules/respiratory_lab/pages.py").read_text(encoding="utf-8")
