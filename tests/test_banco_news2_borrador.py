"""Banco de NEWS2, BORRADOR para firma (2026-11-17): cada cita «t1:N — «…»» existe literal en su línea de la teoría
firmada, y los puntos de pulso que dicen las preguntas coinciden con `clinical.calculators.news2_pulse_score`."""
import re
from pathlib import Path

from clinical.calculators import news2_pulse_score

DOC = Path("docs/contenido/banco_preguntas_news2.md").read_text(encoding="utf-8")
T1 = Path("docs/contenido/teoria_citada.md").read_text(encoding="utf-8").splitlines()


def test_es_un_borrador_y_no_esta_en_la_app():
    assert "**Estado:** BORRADOR" in DOC
    import educational.quiz_bank as qb
    assert not hasattr(qb, "NEWS2_QUESTIONS")


def test_cada_cita_es_literal_en_su_linea_firmada():
    quotes = re.findall(r"\*Línea firmada:\* t1:(\d+) — «(.*)»$", DOC, flags=re.M)
    assert len(quotes) >= 7
    for n, text in quotes:
        assert T1[int(n) - 1] == text, n


def test_toda_linea_citada_existe_en_la_teoria():
    for n in {int(n) for n in re.findall(r"t1:(\d+)", DOC)}:
        assert 0 < n <= len(T1) and T1[n - 1].strip(), n


def test_los_puntos_de_pulso_coinciden_con_el_codigo():
    assert news2_pulse_score(120) == 2 and "2 puntos (tramo de 111 a 130 lpm)" in DOC
    assert news2_pulse_score(45) == 1 and "1 punto (tramo de 41 a 50 lpm)" in DOC
