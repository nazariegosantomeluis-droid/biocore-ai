# 🏗️ Arquitectura del Biomedical Reasoning Engine

## Flujo General

```
                         HRVMetrics
                       (Entrada)
                            │
                            ▼
                  BiomedicalReasoningEngine
                      (Orquestador)
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
PhysiologicalPattern   ClinicalHypothesis    RiskEstimator
Detector               Generator             
        │                   │                   │
        │                   │                   │
        ▼                   ▼                   ▼
    Hallazgos          Hipótesis            Risk Level
                                            Risk Score
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
Differential         Autonomic State    Educational
Diagnosis            Classifier         Recommendations
Generator                               Generator
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                            ▼
                     ReasoningOutput
                   (Salida Completa)
```

## Componentes Detallados

```
┌─────────────────────────────────────────────────────────────┐
│                  BIOMEDICAL REASONING ENGINE                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  DETECTION LAYER - Detectores de Patrones           │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │                                                       │  │
│  │  ReasoningPattern (Abstracción)                      │  │
│  │       │                                              │  │
│  │       ├── TachycardiaPattern                         │  │
│  │       ├── BradycardiaPattern                         │  │
│  │       ├── HighVariabilityPattern                     │  │
│  │       ├── LowVariabilityPattern                      │  │
│  │       ├── SympatheticDominancePattern                │  │
│  │       ├── ParasympatheticDominancePattern            │  │
│  │       ├── LowEntropyPattern                          │  │
│  │       └── HighEntropyPattern                         │  │
│  │                                                       │  │
│  │  PhysiologicalPatternDetector (Orquestador)         │  │
│  │       └─→ detect_all() → List[PhysiologicalFinding] │  │
│  │                                                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  REASONING LAYER - Generadores de Hipótesis         │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │                                                       │  │
│  │  ClinicalHypothesisGenerator                         │  │
│  │       └─→ generate_hypotheses()                      │  │
│  │           → List[ClinicalHypothesis]                 │  │
│  │                                                       │  │
│  │  DifferentialDiagnosisGenerator                      │  │
│  │       └─→ generate_differential_diagnoses()          │  │
│  │           → List[DifferentialDiagnosis]              │  │
│  │                                                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  EVALUATION LAYER - Estimadores                      │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │                                                       │  │
│  │  RiskEstimator                                       │  │
│  │       └─→ estimate_risk()                            │  │
│  │           → (RiskLevel, float[0-100])                │  │
│  │                                                       │  │
│  │  AutonomicStateClassifier                            │  │
│  │       └─→ classify()                                 │  │
│  │           → AutonomicState                           │  │
│  │                                                       │  │
│  │  EducationalRecommendationGenerator                  │  │
│  │       └─→ generate_recommendations()                 │  │
│  │           → List[EducationalRecommendation]          │  │
│  │                                                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  ORCHESTRATION - Motor Principal                     │  │
│  ├──────────────────────────────────────────────────────┤  │
│  │                                                       │  │
│  │  BiomedicalReasoningEngine                           │  │
│  │       │                                              │  │
│  │       ├─→ Valida métricas                            │  │
│  │       ├─→ Ejecuta detectores                         │  │
│  │       ├─→ Genera hipótesis                           │  │
│  │       ├─→ Genera diagnósticos                        │  │
│  │       ├─→ Estima riesgo                              │  │
│  │       ├─→ Clasifica estado autonómico                │  │
│  │       ├─→ Genera recomendaciones                     │  │
│  │       ├─→ Genera advertencias                        │  │
│  │       └─→ Produce ReasoningOutput                    │  │
│  │                                                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Pipeline de Datos

```
HRVMetrics (Input)
    │
    ▼
┌───────────────────┐
│ Validación        │ ← Verifica rangos
└────────┬──────────┘
         │
         ▼
┌─────────────────────┐
│ Detección Patrones  │ ← 9 patrones en paralelo
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ Generación Hipótesis│ ← 2-3 hipótesis típicas
└────────┬────────────┘
         │
         ▼
┌──────────────────────┐
│ Diagnósticos Diff.   │ ← 2-4 diagnósticos
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│ Estimación Riesgo    │ ← Cálculo puntuación
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│ Clasificación Auton. │ ← 1 estado
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│ Recomendaciones      │ ← 2-6 recomendaciones
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│ Generación Warnings  │ ← 0-3 advertencias
└────────┬─────────────┘
         │
         ▼
    ReasoningOutput ← Complete analysis
```

## Relaciones de Clases (SOLID)

```
                        ┌─────────────────┐
                        │  HRVMetrics     │
                        │  (Entrada)      │
                        └────────┬────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                        │
                    ▼                        ▼
        ┌─────────────────────┐  ┌──────────────────┐
        │ PhysiologicalFinding│  │ RiskLevel (Enum) │
        └────────┬────────────┘  └──────────────────┘
                 │
    ┌────────────┴────────────┐
    │                        │
    ▼                        ▼
┌─────────┐            ┌──────────────────────┐
│  Finding│            │ ClinicalHypothesis   │
│ (Data)  │            │ (Reasoning)          │
└─────────┘            └──────────────────────┘
    │                         │
    │                         ▼
    │                  ┌──────────────────────┐
    │                  │ Differential Dx      │
    │                  │ (Education)          │
    │                  └──────────────────────┘
    │
    └──────────────────────┬──────────────────────┐
                          │                      │
                          ▼                      ▼
                    ┌────────────┐        ┌──────────────────┐
                    │ Autonomic  │        │ Educational Rec. │
                    │ State      │        │ (Recommendations)│
                    └────────────┘        └──────────────────┘
                          │                      │
                          └──────────┬───────────┘
                                    │
                                    ▼
                          ┌────────────────────┐
                          │ ReasoningOutput    │
                          │ (Salida Completa)  │
                          └────────────────────┘
```

## Patrones de Diseño Aplicados

```
┌─────────────────────────────────────────────────────────┐
│           STRATEGY PATTERN - Patrones                  │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ ReasoningPattern (Strategy)                             │
│      │                                                  │
│      ├── TachycardiaPattern                             │
│      ├── BradycardiaPattern                             │
│      └── [+ 7 más]                                      │
│                                                         │
│ PhysiologicalPatternDetector (Context)                  │
│      └── Usa cualquier Strategy                         │
│                                                         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│      FACTORY PATTERN - Generadores                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ ClinicalHypothesisGenerator.generate_hypotheses()      │
│ DifferentialDiagnosisGenerator.generate_differential...│
│ EducationalRecommendationGenerator.generate_...         │
│                                                         │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│      FACADE PATTERN - Orquestación                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ BiomedicalReasoningEngine.reason()                      │
│      │                                                  │
│      ├─→ Validator                                      │
│      ├─→ PatternDetector                                │
│      ├─→ HypothesisGenerator                            │
│      ├─→ DiagnosisGenerator                             │
│      ├─→ RiskEstimator                                  │
│      ├─→ AutonomicClassifier                            │
│      ├─→ RecommendationGenerator                        │
│      └─→ WarningGenerator                               │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## Integración con Streamlit

```
┌─────────────────────────────────────────────┐
│  BiomedicalReasoningStreamlit               │
├─────────────────────────────────────────────┤
│                                             │
│  ┌─ input_metrics_panel()                  │
│  │   └─→ Captura entrada                   │
│  │                                         │
│  ├─ display_risk_dashboard(output)         │
│  │   └─→ Gauge + Métricas                  │
│  │                                         │
│  ├─ display_findings(output)                │
│  │   └─→ Hallazgos expandibles             │
│  │                                         │
│  ├─ display_hypotheses(output)              │
│  │   └─→ Hipótesis con scores              │
│  │                                         │
│  ├─ display_differential_diagnoses(output) │
│  │   └─→ Tabla + Detalles                  │
│  │                                         │
│  ├─ display_recommendations(output)        │
│  │   └─→ Categorizado por tipo             │
│  │                                         │
│  ├─ display_json_export(output)            │
│  │   └─→ Download + Preview                │
│  │                                         │
│  └─ run_app()                              │
│      └─→ Aplicación completa               │
│                                             │
│  create_reasoning_component()              │
│      └─→ Componente reutilizable          │
│                                             │
└─────────────────────────────────────────────┘
```

## Pipeline de Integración

```
ECG (Signal)
    │
    ▼
┌─────────────────┐
│ Filtrado        │ (Existente)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ R Peak Detection│ (Existente)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ HRV Calculation │ (Existente)
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│ BiomedicalReasoning ◄── NUEVO
│ Engine                  │
└────────┬────────────────┘
         │
         ▼
┌─────────────────┐
│ Machine Learning│ (Existente)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Explainable AI  │ (Existente)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Reports         │ (Existente, mejorado)
└─────────────────┘
```

## Matriz de Responsabilidades (SOLID)

```
┌─────────────────────────────────────────────────────────────┐
│ Componente                    │ Responsabilidad             │
├─────────────────────────────────────────────────────────────┤
│ HRVMetrics                    │ Datos de entrada + validación
│ PhysiologicalFinding          │ Datos de hallazgos           │
│ ClinicalHypothesis            │ Datos de hipótesis           │
│ DifferentialDiagnosis         │ Datos de diagnósticos        │
│ EducationalRecommendation     │ Datos de recomendaciones     │
│ ReasoningOutput               │ Salida consolidada           │
├─────────────────────────────────────────────────────────────┤
│ ReasoningPattern (Abstract)   │ Interfaz de patrones         │
│ TachycardiaPattern            │ Detectar taquicardia         │
│ BradycardiaPattern            │ Detectar bradicardia         │
│ [+ 7 patrones]                │ [+ específico c/uno]         │
├─────────────────────────────────────────────────────────────┤
│ PhysiologicalPatternDetector  │ Orquestar detectores         │
│ ClinicalHypothesisGenerator   │ Generar hipótesis            │
│ DifferentialDiagnosisGenerator│ Generar diagnósticos         │
│ RiskEstimator                 │ Calcular riesgo              │
│ AutonomicStateClassifier      │ Clasificar estado            │
│ EducationalRecommendation...  │ Generar recomendaciones      │
├─────────────────────────────────────────────────────────────┤
│ BiomedicalReasoningEngine     │ Orquestar TODO               │
└─────────────────────────────────────────────────────────────┘
```

---

**Arquitectura escalable, modular, mantenible y educativa.**
