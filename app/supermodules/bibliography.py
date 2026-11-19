"""Bibliografía (Biblioteca → Bibliografía; antes Aprender; pulido profesional, 2026-11-16).

Dos partes:
1. `SIGNED`: las referencias de `docs/contenido/teoria_citada.md` (firmado por Luis el 2026-11-16) y de
   `docs/contenido/teoria_citada_2.md` (EMG y HRV, firmado el 2026-11-17), con su clave. Aparte, `HEMODYNAMICS`: las de
   `docs/contenido/teoria_citada_3.md` (hemodinámica, firmado el 2026-11-17). Cada
   bloque de teoría cita su clave ([K2007], [MCM]...) y enlaza aquí. Los metadatos de StatPearls y de Kors 1990 se
   completaron con el registro de PubMed (decisión adicional 3 de la hoja de firma).
2. `REPO`: las que la plataforma ya citaba en su código (una sola copia de cada cita en su módulo), en formato uniforme:
   «Autores. Título. Revista año;volumen:páginas», sin las notas de uso que el código les pega; DOI enlazado si lo hay.

Los datos, ecuaciones y bibliotecas de terceros están en `THIRD_PARTY_NOTICES.md`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

PAGE_URL = "bibliografia"


@dataclass(frozen=True)
class Reference:
    key: str
    group: str
    text: str                                     # Markdown, formato uniforme
    links: Tuple[Tuple[str, str], ...] = ()       # (etiqueta, url)
    note: str = ""


GUIDES, BOOKS, ARTICLES = "Guías y documentos de consenso", "Libros de texto (acceso abierto)", "Artículos originales"

SIGNED: Tuple[Reference, ...] = (
    Reference("K2007", GUIDES,
              "Kligfield P, Gettes LS, Bailey JJ, et al. Recommendations for the standardization and interpretation of "
              "the electrocardiogram: part I: the electrocardiogram and its technology. A scientific statement from the "
              "AHA Electrocardiography and Arrhythmias Committee, Council on Clinical Cardiology; the ACCF; and the HRS. "
              "*Circulation*. 2007;115:1306–1324 (publicado también en *Heart Rhythm*. 2007;4:394–412).",
              (("PDF de la HRS", "https://hrsonline.org/documents/part-i-electrocardiogram-and-its-technologypdf/download"),)),
    Reference("W2009", GUIDES,
              "Wagner GS, Macfarlane P, Wellens H, et al. AHA/ACCF/HRS recommendations for the standardization and "
              "interpretation of the electrocardiogram: part VI: acute ischemia/infarction. *Circulation*. "
              "2009;119:e262–e270.",
              (("PDF de la HRS", "https://hrsonline.org/documents/standardization-and-interpretation-electrocardiogram-part-vipdf/download"),)),
    Reference("RCP2017", GUIDES,
              "Royal College of Physicians. *National Early Warning Score (NEWS) 2: Standardising the assessment of "
              "acute-illness severity in the NHS. Updated report of a working party.* Londres: RCP; 2017.",
              (("Resumen ejecutivo", "https://www.rcp.ac.uk/media/ctulqqbn/news2-executive-summary_0.pdf"),
               ("Informe completo", "https://www.rcp.ac.uk/media/a4ibkkbf/news2-final-report_0_0.pdf"))),
    Reference("B2012", GUIDES,
              "Berry RB, Budhiraja R, Gottlieb DJ, et al. Rules for scoring respiratory events in sleep: update of the "
              "2007 AASM Manual. *J Clin Sleep Med*. 2012;8(5):597–619."),
    Reference("E2009", GUIDES,
              "Epstein LJ, Kristo D, Strollo PJ Jr, et al. Clinical guideline for the evaluation, management and "
              "long-term care of obstructive sleep apnea in adults. *J Clin Sleep Med*. 2009;5(3):263–276."),
    Reference("IFCN2017", GUIDES,
              "Kane N, Acharya J, Beniczky S, et al. A revised glossary of terms most commonly used by clinical "
              "electroencephalographers and updated proposal for the report format of the EEG findings. Revision 2017. "
              "*Clin Neurophysiol Pract*. 2017;2:170–185.",
              (("doi:10.1016/j.cnp.2017.07.002", "https://doi.org/10.1016/j.cnp.2017.07.002"),
               ("PDF", "https://discovery-pp.ucl.ac.uk/id/eprint/10076640/1/Kane_1-s2.0-S2467981X17300215-main.pdf"))),
    Reference("MCM", BOOKS,
              "Sibbald M, Dąbrowski A, Leśniak W. Standard Electrocardiography. En: *McMaster Textbook of Internal "
              "Medicine*. Cracovia: Medycyna Praktyczna.",
              (("Capítulo en línea", "https://empendium.com/mcmtextbook/chapter/B31.1269.3.6.1"),)),
    Reference("CS2023", BOOKS,
              "Chapa-Rodriguez A, Para K, Sankari A, Bollu PC. Cheyne-Stokes Respirations. En: *StatPearls*. Treasure "
              "Island (FL): StatPearls Publishing; actualizado el 31 de julio de 2023. NCBI Bookshelf NBK448165; "
              "PMID 28846350.",
              (("Capítulo", "https://www.statpearls.com/point-of-care/19395"),
               ("NCBI Bookshelf", "https://www.ncbi.nlm.nih.gov/books/NBK448165/")),
              note="Autores tomados del registro de PubMed (PMID 28846350), cuya versión actual es del 17 de agosto de "
                   "2026; el texto firmado se leyó en la versión del 31 de julio de 2023."),
    # Cierre del pulido (2026-11-16): autores corregidos según PubMed (PMID 29262235); decía «Whited L, Graham DD».
    Reference("AR2025", BOOKS,
              "Porter R, Graham DD. Abnormal Respirations. En: *StatPearls*. Treasure Island (FL): StatPearls "
              "Publishing; actualizado el 13 de diciembre de 2025. NCBI Bookshelf NBK470309; PMID 29262235.",
              (("Capítulo", "https://www.statpearls.com/point-of-care/23959"),
               ("NCBI Bookshelf", "https://www.ncbi.nlm.nih.gov/books/NBK470309/")),
              note="Autores corregidos según PubMed el 16 de noviembre de 2026."),
    Reference("KORS1990", ARTICLES,
              "Kors JA, van Herpen G, Sittig AC, van Bemmel JH. Reconstruction of the Frank vectorcardiogram from "
              "standard electrocardiographic leads: diagnostic comparison of different methods. *Eur Heart J*. "
              "1990;11(12):1083–1092. PMID 2292255.",
              (("doi:10.1093/oxfordjournals.eurheartj.a059647",
                "https://doi.org/10.1093/oxfordjournals.eurheartj.a059647"),)),
    Reference("VZ2014", ARTICLES,
              "Vozda M, Peterek T, Cerny M. Novel method for deriving vectorcardiographic leads based on artificial "
              "neural networks. En: *Electrocardiology 2014 – Proceedings of the 41st International Congress on "
              "Electrocardiology*; 2014:61–64.",
              (("PDF", "https://www.measurement.sk/ICE2014/proceedings/061.pdf"),)),
    # ── Teoría citada 2 (docs/contenido/teoria_citada_2.md, EMG y HRV, firmada el 2026-11-17) ──
    Reference("DL1997", ARTICLES,
              "De Luca CJ. The use of surface electromyography in biomechanics. *J Appl Biomech*. 1997;13(2):135–163.",
              (("PDF", "https://people.stfx.ca/smackenz/Courses/HK474/Readings/THE%20USE%20OF%20SURFACE%20ELECTROMYOGRAPHY.pdf"),)),
    Reference("DL2010", ARTICLES,
              "De Luca CJ, Gilmore LD, Kuznetsov M, Roy SH. Filtering the surface EMG signal: movement artifact and "
              "baseline noise contamination. *J Biomech*. 2010;43(8):1573–1579.",
              (("doi:10.1016/j.jbiomech.2010.01.027", "https://doi.org/10.1016/j.jbiomech.2010.01.027"),
               ("PDF", "https://www.bu.edu/nmrc/files/2010/06/103.pdf"))),
    Reference("V2018", ARTICLES,
              "Vigotsky AD, Halperin I, Lehman GJ, Trajano GS, Vieira TM. Interpreting signal amplitudes in surface "
              "electromyography studies in sport and rehabilitation sciences. *Front Physiol*. 2018;8:985.",
              (("doi:10.3389/fphys.2017.00985", "https://doi.org/10.3389/fphys.2017.00985"),
               ("PDF", "https://iris.polito.it/retrieve/handle/11583/2697782/183144/Vigotsky_et_al_2018-FP.pdf"))),
    Reference("H2000", ARTICLES,
              "Hermens HJ, Freriks B, Disselhorst-Klug C, Rau G. Development of recommendations for SEMG sensors and "
              "sensor placement procedures. *J Electromyogr Kinesiol*. 2000;10(5):361–374.",
              (("doi:10.1016/S1050-6411(00)00027-4", "https://doi.org/10.1016/S1050-6411(00)00027-4"),)),
    Reference("SG2017", ARTICLES,
              "Shaffer F, Ginsberg JP. An overview of heart rate variability metrics and norms. *Front Public Health*. "
              "2017;5:258.",
              (("doi:10.3389/fpubh.2017.00258", "https://doi.org/10.3389/fpubh.2017.00258"),
               ("Artículo", "https://www.frontiersin.org/journals/public-health/articles/10.3389/fpubh.2017.00258"))),
    Reference("B2013", ARTICLES,
              "Billman GE. The LF/HF ratio does not accurately measure cardiac sympatho-vagal balance. *Front Physiol*. "
              "2013;4:26.",
              (("doi:10.3389/fphys.2013.00026", "https://doi.org/10.3389/fphys.2013.00026"),
               ("PDF", "https://www.frontiersin.org/journals/physiology/articles/10.3389/fphys.2013.00026/pdf"))),
    Reference("TF1996", GUIDES,
              "Task Force of the European Society of Cardiology and the North American Society of Pacing and "
              "Electrophysiology (Camm AJ, Malik M, Bigger JT, et al.). Heart rate variability: standards of "
              "measurement, physiological interpretation and clinical use. *Circulation*. 1996;93(5):1043–1065.",
              (("doi:10.1161/01.CIR.93.5.1043", "https://doi.org/10.1161/01.CIR.93.5.1043"),),
              note="Es el estándar fundacional de la HRV. No se leyó su texto completo, así que no se le atribuye "
                   "ninguna afirmación directamente: las definiciones vienen de [SG2017], que se basa en él."),
)

# Métodos que la plataforma cita en pantalla con su clave, fuera de la teoría firmada (2026-11-17). Wilson 1927: el
# intervalo de 95 % del acierto en «Tu calibración en esta sesión»; metadatos verificados en Crossref el 2026-11-17.
METHODS_GROUP = "Métodos que usa la plataforma"
METHODS: Tuple[Reference, ...] = (
    Reference("WILSON1927", METHODS_GROUP,
              "Wilson EB. Probable inference, the law of succession, and statistical inference. *J Am Stat Assoc*. "
              "1927;22(158):209–212.",
              (("doi:10.1080/01621459.1927.10502953", "https://doi.org/10.1080/01621459.1927.10502953"),)),
    # Tanda de heurísticas (2026-11-19): reemplazan valores que se mostraban como «Heurística» o «Valor BIOCORE».
    # Metadatos verificados en la página del artículo (Kwon: experts.umn.edu; Marui: el PDF de Springer) el 2026-11-19.
    Reference("KWON2020", METHODS_GROUP,
              "Kwon Y, Mariani S, Reid M, Jacobs D, Lima J, Kapur V, Punjabi N, Redline S. Lung to finger circulation "
              "time in sleep study and coronary artery calcification: the Multi-Ethnic Study of Atherosclerosis. "
              "*Sleep Med*. 2020;75:8–11.",
              (("doi:10.1016/j.sleep.2020.05.033", "https://doi.org/10.1016/j.sleep.2020.05.033"),),
              note="De aquí sale el retardo Tc de 19.4 s del laboratorio de Respiración (la mediana del estudio)."),
    Reference("MARUI2017", METHODS_GROUP,
              "Marui S, Misawa A, Tanaka Y, Nagashima K. Assessment of axillary temperature for the evaluation of "
              "normal body temperature of healthy young adults at rest in a thermoneutral environment. *J Physiol "
              "Anthropol*. 2017;36:18.",
              (("doi:10.1186/s40101-017-0133-y", "https://doi.org/10.1186/s40101-017-0133-y"),),
              note="De aquí sale «estable» del sensor de temperatura: ±0.1 °C durante 3 min (su criterio para el "
                   "termómetro timpánico)."),
)

SIGNED_KEYS = tuple(r.key for r in SIGNED)

# Hemodinámica (`docs/contenido/teoria_citada_3.md`, firmado por Luis el 2026-11-17 con la condición «que salga de
# referencias verídicas»). Grupo aparte: los registros se leyeron en Consensus (Semantic Scholar, OpenAlex, PubMed) y de
# ellos solo hay autor principal, título, revista y año; volumen, páginas y DOI quedan por completar en la fuente.
HEMO_GROUP = "Hemodinámica (teoría firmada 3)"
_HEMO_NOTE = "Registro leído en Consensus el 2026-11-17; volumen, páginas y DOI por completar en la fuente original."
HEMODYNAMICS: Tuple[Reference, ...] = tuple(
    Reference(key, HEMO_GROUP, text, (("Registro", url),), note=_HEMO_NOTE) for key, text, url in (
        ("DW2019", "DeMers D, et al. Physiology, Mean Arterial Pressure. *StatPearls*. Treasure Island (FL): StatPearls "
                   "Publishing; 2019.",
         "https://consensus.app/papers/details/w:8df53f3a-df91-4c5b-88d8-55afabeabd83/"),
        ("ME2000", "Meaney E, et al. Formula and nomogram for the sphygmomanometric calculation of the mean arterial "
                   "pressure. *Heart*. 2000.",
         "https://consensus.app/papers/details/w:82b2646b-b849-4db3-871e-d97746887ee4/"),
        ("JO2024", "Jozwiak M, et al. Value and Variability of Pulse Shape Indicator for Estimating Mean Arterial Pressure "
                   "in the Radial and Femoral Arteries. *J Am Heart Assoc*. 2024.",
         "https://consensus.app/papers/details/w:b3ea8507-dbe6-474c-ad8e-f64d0e34721b/"),
        ("MY2003", "Mayet J, et al. Cardiac and vascular pathophysiology in hypertension. *Heart*. 2003.",
         "https://consensus.app/papers/details/w:1d168653-b62e-4650-aa40-09b3f80606c9/"),
        ("SQ2015", "Sequeira V, et al. Historical perspective on heart function: the Frank–Starling Law. *Biophys Rev*. "
                   "2015.",
         "https://consensus.app/papers/details/w:1789598a-bd26-4709-bdb3-3cedc967949c/"),
    ))
HEMO_KEYS = tuple(r.key for r in HEMODYNAMICS)


# «Oehler 2014» (auditoría firmada, decisión 2): es una publicación verificable (PubMed 25201032) y sostiene lo que el
# panel del VCG le atribuye («ángulos amplios se asocian a mayor riesgo»: el resumen la asocia con muerte súbita y
# mortalidad en estudios observacionales). Por eso se completa, no se sustituye.
OEHLER_2014 = Reference(
    "OEHLER2014", ARTICLES,
    "Oehler A, Feldman T, Henrikson CA, Tereshchenko LG. QRS-T angle: a review. *Ann Noninvasive Electrocardiol*. "
    "2014;19(6):534–542. PMID 25201032.",
    (("doi:10.1111/anec.12206", "https://doi.org/10.1111/anec.12206"),),
)


def _uniform(citation: str) -> Tuple[str, Tuple[Tuple[str, str], ...]]:
    """Quita la nota de uso que el código le pega a una cita entre paréntesis («(eje normal del adulto...)») y separa
    el DOI como enlace."""
    doi = re.search(r"doi:\s*(10\.\S+?)\.?(?=\s|$)", citation)
    year = re.search(r"\b(19|20)\d{2}(?=[;.:]| \(|$)", citation)       # la nota va después del año, el título antes
    start = year.end() if year else 0
    note = re.search(r" \((?!publicada)", citation[start:])
    text = citation[:start + note.start()] if note else citation
    text = re.sub(r"\.?\s*doi:\s*10\.\S+", "", text).strip().rstrip(".") + "."
    links = ((f"doi:{doi.group(1)}", f"https://doi.org/{doi.group(1)}"),) if doi else ()
    return text, links


def repo_references() -> List[Reference]:
    """Las citas que la plataforma ya usaba en su código, sin repetir las de `SIGNED`."""
    from clinical import calculators as C
    from clinical import ecg_references as E
    from clinical import eeg_references as G
    from src.signals.ecg import vcg

    citations = [
        E.SURAWICZ_2009, E.RAUTAHARJU_2009, E.DREW_2010, E.AL_KHATIB_2017, E.KUSUMOTO_2018, E.PAGE_2015,
        E.BYRNE_2023, E.THYGESEN_2012, E.VAN_GELDER_2024, E.SCHULZ_MENGER_2025,
        C.BAZETT_CITATION, C.FRIDERICIA_CITATION, C.FRAMINGHAM_QTC_CITATION, C.HODGES_CITATION, C.QRS_AXIS_CITATION,
        C.MAP_TARGET_CITATION, C.SHOCK_INDEX_CITATION,
        "Mutschler M, Nienaber U, Münzberg M, et al. The Shock Index revisited -- a fast guide to transfusion "
        "requirement? Crit Care 2013;17:R172",                                   # 2.ª cita de SHOCK_INDEX_CITATION
        C.FORRESTER_CITATION, C.WHO_BMI_CITATION, C.MOSTELLER_CITATION, C.DUBOIS_CITATION, C.BERLIN_CITATION,
        C.QSOFA_CITATION.split("; Singer")[0],
        "Singer M, et al. The Third International Consensus Definitions for Sepsis and Septic Shock (Sepsis-3). "
        "JAMA 2016;315:801–810",                                                 # 2.ª cita de QSOFA_CITATION
        C.GCS_CITATION, C.PRQ_REFERENCE, C.EXPECTED_AA_CITATION,
        G.SEECK_2017, G.TATUM_2011, vcg.TANGENT_CITATION,
    ]
    refs = []
    for citation in citations:
        text, links = _uniform(citation)
        refs.append(Reference("", "Otras referencias que cita la plataforma", text, links))
    refs.append(OEHLER_2014)
    try:
        from src.signals.reference_recordings import load

        for key in ("ptb_s0010", "cap_n16"):
            rec = load(key)
            text, links = _uniform(rec.citation)
            refs.append(Reference("", "Registros reales que muestra la plataforma",
                                  f"{text} {rec.title} (licencia {rec.license}).", links))
    except Exception:                                                         # sin los archivos: no se listan
        pass
    return refs


def cite(key: str) -> str:
    """La clave entre corchetes, tal como la escribe el texto firmado."""
    if key not in SIGNED_KEYS:
        raise KeyError(key)
    return f"[{key}]"


def render_bibliography_page() -> None:
    import streamlit as st

    from app.utils.design_system import render_module_header, render_section_header

    render_module_header("Bibliografía", icon="📚",
                         subtitle="Las fuentes de la teoría y de los laboratorios, en un solo lugar.")
    st.caption("Cada bloque de teoría lleva su clave entre corchetes ([K2007], [MCM]...): aquí está la referencia "
               "completa. Datos, ecuaciones y bibliotecas de terceros: `THIRD_PARTY_NOTICES.md`.")
    for group in (GUIDES, BOOKS, ARTICLES):
        render_section_header(group)
        for ref in SIGNED:
            if ref.group == group:
                _render_reference(st, ref)
    render_section_header(HEMO_GROUP)
    for ref in HEMODYNAMICS:
        _render_reference(st, ref)
    render_section_header(METHODS_GROUP)
    for ref in METHODS:
        _render_reference(st, ref)
    extra = repo_references()
    for group in dict.fromkeys(r.group for r in extra):
        render_section_header(group)
        for ref in extra:
            if ref.group == group:
                _render_reference(st, ref)


def _render_reference(st, ref: Reference) -> None:
    links = " · ".join(f"[{label}]({url})" for label, url in ref.links)
    head = f"**[{ref.key}]** " if ref.key else ""          # las de `REPO` no tienen clave
    st.markdown(f"- {head}{ref.text}" + (f" {links}" if links else ""))
    if ref.note:
        st.caption(ref.note)
