"""Referencias clínicas del ECG, una sola copia (2026-11-14).

Las usan el banco de preguntas (`educational/quiz_bank.py`) y el analizador de 12
derivaciones (`src/signals/ecg/twelve_lead_measure.py`). Cada una se leyó del documento
original el 2026-11-14; la de las derivaciones contiguas, en su cita textual (se dice
dónde). Las fórmulas y escalas de `clinical/calculators.py` conservan sus propias
constantes `*_CITATION` (Bazett, umbrales del QTc, QTc > 500 ms, eje), y el método de la
tangente está en `src/signals/ecg/vcg.py` (`TANGENT_CITATION`).
"""

SURAWICZ_2009 = (
    "Surawicz B, Childers R, Deal BJ, Gettes LS. AHA/ACCF/HRS recommendations for the standardization and "
    "interpretation of the electrocardiogram, Part III: intraventricular conduction disturbances. "
    "Circulation 2009;119:e235–e240"
)
RAUTAHARJU_2009 = (
    "Rautaharju PM, Surawicz B, Gettes LS. AHA/ACCF/HRS recommendations for the standardization and "
    "interpretation of the electrocardiogram, Part IV: the ST segment, T and U waves, and the QT interval. "
    "Circulation 2009;119:e241–e250"
)
WAGNER_2009 = (
    "Wagner GS, Macfarlane P, Wellens H, et al. AHA/ACCF/HRS recommendations for the standardization and "
    "interpretation of the electrocardiogram, Part VI: acute ischemia/infarction. Circulation 2009;119:e262–e270"
)
KLIGFIELD_2007 = (
    "Kligfield P, Gettes LS, Bailey JJ, et al. Recommendations for the standardization and interpretation of "
    "the electrocardiogram, Part I: the electrocardiogram and its technology. Circulation 2007;115:1306–1324"
)
DREW_2010 = (
    "Drew BJ, Ackerman MJ, Funk M, et al. Prevention of torsade de pointes in hospital settings: a scientific "
    "statement from the American Heart Association and the American College of Cardiology Foundation. "
    "Circulation 2010;121:1047–1060"
)
AL_KHATIB_2017 = (
    "Al-Khatib SM, Stevenson WG, Ackerman MJ, et al. 2017 AHA/ACC/HRS guideline for management of patients with "
    "ventricular arrhythmias and the prevention of sudden cardiac death: executive summary. J Am Coll Cardiol "
    "2017. doi:10.1016/j.jacc.2017.10.053"
)
KUSUMOTO_2018 = (
    "Kusumoto FM, Schoenfeld MH, et al. 2018 ACC/AHA/HRS guideline on the evaluation and management of patients "
    "with bradycardia and cardiac conduction delay. J Am Coll Cardiol 2018. doi:10.1016/j.jacc.2018.10.044"
)
PAGE_2015 = (
    "Page RL, Joglar JA, Caldwell MA, et al. 2015 ACC/AHA/HRS guideline for the management of adult patients "
    "with supraventricular tachycardia. Heart Rhythm 2016;13:e136–e221"
)
BYRNE_2023 = (
    "Byrne RA, Rossello X, Coughlan JJ, et al. 2023 ESC Guidelines for the management of acute coronary "
    "syndromes. Eur Heart J Acute Cardiovasc Care 2024;13:55–161 (publicada también en Eur Heart J)"
)
THYGESEN_2012 = (
    "Thygesen K, Alpert JS, Jaffe AS, et al. Third universal definition of myocardial infarction. Eur Heart J "
    "2012;33(20):2551–2567 (definición de «derivaciones contiguas», leída en su cita textual en tomwademd.net)"
)
VAN_GELDER_2024 = (
    "Van Gelder IC, Rienstra M, Bunting KV, et al. 2024 ESC Guidelines for the management of atrial "
    "fibrillation. Eur Heart J 2024;45:3314–3414. doi:10.1093/eurheartj/ehae176"
)
SCHULZ_MENGER_2025 = (
    "Schulz-Menger J, Collini V, Gröschel J, et al. 2025 ESC Guidelines for the management of myocarditis and "
    "pericarditis. Eur Heart J 2025. doi:10.1093/eurheartj/ehaf192"
)
SOKOLOW_LYON_1949 = (
    "Sokolow M, Lyon TP. Am Heart J 1949 (criterio de Sokolow-Lyon), tal como lo resume la tabla «Criteria for "
    "ECG Diagnosis of Left Ventricular Hypertrophy» del Manual MSD para profesionales"
)
