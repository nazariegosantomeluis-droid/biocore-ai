"""Gemini como proveedor del narrador y el candado de privacidad (2026-11-16).

La API real de Google no se llama aquí (no hay clave ni salida a sus servidores): un transporte simulado devuelve lo
que devolvería la API (eventos SSE, listas de modelos, errores JSON) y se verifica la petición que arma el cliente.
Lo que sí se verifica de punta a punta es la garantía: el nivel gratuito nunca recibe datos de una persona.
"""

from __future__ import annotations

import io
import json
import os
import urllib.error

import pytest

import app.utils.ai_session as S
from domain.physiology.narrator import (DEFAULT_MODEL, DataOrigin, Finding, FindingsContext, GeminiClient,
                                        GeminiError, ProviderNotAllowedError, build_context, classify_source,
                                        stream_findings_narration, stream_narration, DepthLevel)
from domain.physiology.narrator.gemini import API_BASE, choose_model, parse_sse, validate_key


class FakeResponse(io.BytesIO):
    status = 200


class FakeOpener:
    """Hace de `urllib.request.urlopen`: guarda cada petición y devuelve la respuesta que se le dio."""

    def __init__(self, *responses):
        self.responses, self.requests = list(responses), []

    def __call__(self, request, timeout=None):
        self.requests.append(request)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item if isinstance(item, bytes) else json.dumps(item).encode())


def sse(*events):
    return b''.join(b'data: ' + json.dumps(e).encode() + b'\r\n\r\n' for e in events)


def http_error(code, reason=None, message=''):
    body = {'error': {'code': code, 'message': message, 'status': 'X',
                      'details': [{'@type': 'type.googleapis.com/google.rpc.ErrorInfo', 'reason': reason}]
                      if reason else []}}
    return urllib.error.HTTPError('https://x', code, 'error', {}, io.BytesIO(json.dumps(body).encode()))


def chunk(text=None, thought=False, finish=None):
    part = {'text': text}
    if thought:
        part['thought'] = True
    candidate = {'content': {'role': 'model', 'parts': [part] if text is not None else []}}
    if finish:
        candidate['finishReason'] = finish
    return {'candidates': [candidate]}


# ================================================================ cliente
def test_request_follows_the_rest_format_and_keeps_the_key_out_of_the_url():
    opener = FakeOpener(sse(chunk('Hola')))
    client = GeminiClient('clave-secreta', model='gemini-prueba', opener=opener)
    with client.messages.stream(max_tokens=321, system='Eres el narrador.',
                                messages=[{'role': 'user', 'content': 'datos'},
                                          {'role': 'assistant', 'content': 'previo'}]) as stream:
        assert ''.join(stream.text_stream) == 'Hola'
    request = opener.requests[0]
    assert request.full_url == f'{API_BASE}/models/gemini-prueba:streamGenerateContent?alt=sse'
    assert request.get_method() == 'POST' and 'clave-secreta' not in request.full_url
    assert request.get_header('X-goog-api-key') == 'clave-secreta'
    body = json.loads(request.data.decode())
    assert body['systemInstruction'] == {'parts': [{'text': 'Eres el narrador.'}]}
    assert body['contents'] == [{'role': 'user', 'parts': [{'text': 'datos'}]},
                                {'role': 'model', 'parts': [{'text': 'previo'}]}]
    assert body['generationConfig'] == {'maxOutputTokens': 321}


def test_stream_text_in_order_without_thoughts_and_says_when_it_was_cut():
    raw = sse(chunk('pensando…', thought=True), chunk('La FC '), chunk('subió.', finish='MAX_TOKENS'))
    assert ''.join(parse_sse(io.BytesIO(raw))) == 'La FC subió.\n\n[Respuesta incompleta: la respuesta llegó al ' \
                                                 'límite de longitud.]'
    assert ''.join(parse_sse(io.BytesIO(sse(chunk('ok', finish='STOP'))))) == 'ok'
    with pytest.raises(GeminiError, match='bloqueó la petición'):
        list(parse_sse(io.BytesIO(sse({'promptFeedback': {'blockReason': 'SAFETY'}}))))


@pytest.mark.parametrize('error,text', [
    (http_error(400, 'API_KEY_INVALID', 'API key not valid.'), 'Google rechazó la clave'),
    (http_error(403), 'no tiene permiso'),
    (http_error(404), 'El modelo gemini-prueba no está disponible'),
    (http_error(429), 'Se acabó la cuota gratuita'),
    (urllib.error.URLError('sin red'), 'No se pudo conectar con Gemini'),
])
def test_api_errors_are_explained_in_spanish(error, text):
    client = GeminiClient('k', model='gemini-prueba', opener=FakeOpener(error))
    with pytest.raises(GeminiError, match=text):
        with client.messages.stream(max_tokens=10, system='s', messages=[{'role': 'user', 'content': 'x'}]):
            pass


def test_key_validation_lists_models_and_picks_a_free_flash_model():
    page1 = {'models': [{'name': 'models/gemini-3.1-pro-preview', 'supportedGenerationMethods': ['generateContent']},
                        {'name': 'models/text-embedding-9', 'supportedGenerationMethods': ['embedContent']}],
             'nextPageToken': 'p2'}
    page2 = {'models': [{'name': 'models/gemini-3.5-flash-lite', 'supportedGenerationMethods': ['generateContent']}]}
    opener = FakeOpener(page1, page2)
    assert validate_key('k', opener) == ('gemini-3.5-flash-lite', None)
    assert opener.requests[1].full_url.endswith('pageToken=p2') and opener.requests[0].get_method() == 'GET'
    assert choose_model(['gemini-9-flash-image', 'gemini-9-flash']) == 'gemini-9-flash'
    assert validate_key('k', FakeOpener({'models': []}))[1].startswith('La clave es válida, pero no tiene')
    assert 'rechazó la clave' in validate_key('mala', FakeOpener(http_error(400, 'API_KEY_INVALID')))[1]


# ================================================================ privacidad
@pytest.mark.parametrize('provenance,detail,origin', [
    # Simulado por BIOCORE
    ('simulacion', 'escenario:sepsis:paso:3/6', 'simulado'),
    ('simulacion', 'escenario_rico:shock:modo:basal:horizonte:2', 'simulado'),
    ('simulacion', 'twin_shell_scenario_simulator:sepsis', 'simulado'),
    ('simulacion', 'twin_visual:checkpoint_manual', 'simulado'),
    ('simulacion', 'narrador:snapshot_bajo_demanda', 'simulado'),
    ('derivado', 'narrador:snapshot_bajo_demanda | news2_pulse_score', 'simulado'),
    ('simulacion', 'razonamiento_causal:snapshot_bajo_demanda', 'simulado'),
    ('simulacion', 'twin_shell_clinical_case_mode', 'simulado'),
    ('simulacion', 'academia_synthetic_case', 'simulado'),
    ('simulacion', 'estado_actual_en_memoria:sin_persistir', 'simulado'),
    ('simulacion', 'comparacion_en_contexto:hypertension', 'simulado'),
    ('simulacion', 'twin_os:ecg_sintetico:hr_real=72bpm', 'simulado'),
    ('simulacion', 'respiratory_lab:patron=Normal; respiratory_rate=60/media', 'simulado'),
    ('simulacion', 'ecg_lab:caso clínico 12', 'simulado'),
    ('simulacion', 'ecg_lab:ESP32 simulado (demo, SIMULACIÓN)', 'simulado'),
    ('simulacion', 'hrv_lab:sdnn_desde_serie_rr:fuente=Simulación: acoplamiento cardiopulmonar', 'simulado'),
    ('simulacion', 'emg_muscle_lab:origen=Demo', 'simulado'),
    ('simulacion', 'emg_muscle_lab:origen=placa EMG en SIMULADOR-EMG (firmware sim-1.0) (SIMULACIÓN)', 'simulado'),
    ('simulacion', 'eeg_neuro_lab:canal=O1:banda_dominante=alpha:fuente=Sintético', 'simulado'),
    # Bases públicas
    ('simulacion', 'ecg_lab:MIT-BIH 100 (PhysioNet)', 'base_publica'),
    ('simulacion', 'ecg_lab:PTB-XL 1234 (NORM, PhysioNet)', 'base_publica'),
    # De una persona
    ('sensor_real', 'ecg_lab:ESP32 + AD8232 en COM3 (SENSOR_REAL)', 'persona'),
    ('sensor_real', 'emg_muscle_lab:origen=placa EMG en COM9 (firmware 1.0) (SENSOR_REAL)', 'persona'),
    ('arrastre_temporal', 'ecg_lab:ESP32 + AD8232 en COM3 (SENSOR_REAL) | arrastrada (edad 30 s)', 'persona'),
    ('simulacion', 'patient_pipeline:entrada_manual', 'persona'),
    # No se sabe: cuenta como de una persona
    ('simulacion', 'emg_muscle_lab:origen=CSV', 'desconocido'),
    ('simulacion', 'eeg_neuro_lab:canal=O1:banda_dominante=alpha:fuente=CSV cargado', 'desconocido'),
    ('simulacion', 'eeg_neuro_lab:canal=Cz:fuente=Flujo LSL en red (origen no verificable)', 'desconocido'),
    ('simulacion', 'hrv_lab:sdnn_desde_serie_rr:fuente=Manual RR series', 'desconocido'),
    ('simulacion', 'una_ruta_nueva:sin_regla', 'desconocido'),
    ('simulacion', None, 'desconocido'),
])
def test_every_write_path_has_a_known_origin(provenance, detail, origin):
    assert classify_source(provenance, detail) == DataOrigin(origin)


def recording_gemini(*responses):
    opener = FakeOpener(*responses)
    return GeminiClient('k', model='gemini-prueba', opener=opener), opener


def test_the_free_tier_never_receives_data_of_a_person():
    findings = [Finding('heart_rate_bpm', '72', 'FC')]
    for origin in (DataOrigin.PERSONA, DataOrigin.DESCONOCIDO):
        client, opener = recording_gemini()
        with pytest.raises(ProviderNotAllowedError, match='solo se explican datos simulados'):
            list(stream_findings_narration(FindingsContext('Lab', findings, origin=origin), client=client))
        assert opener.requests == []                                   # ni una petición
    assert FindingsContext('Lab', findings).origin == DataOrigin.DESCONOCIDO      # sin declarar: no se manda
    for origin in (DataOrigin.SIMULADO, DataOrigin.BASE_PUBLICA):
        client, opener = recording_gemini(sse(chunk('Explicación.')))
        assert ''.join(stream_findings_narration(FindingsContext('Lab', findings, origin=origin),
                                                 client=client)) == 'Explicación.'
        assert len(opener.requests) == 1 and 'gemini-prueba' in opener.requests[0].full_url


def test_anthropic_keeps_working_as_before_with_any_origin():
    seen = {}

    class FakeAnthropic:
        class messages:
            @staticmethod
            def stream(model, max_tokens, system, messages):
                seen['model'] = model

                class _S:
                    text_stream = iter(['ok'])

                    def __enter__(self):
                        return self

                    def __exit__(self, *a):
                        return False
                return _S()

    context = FindingsContext('Lab', [Finding('x', '1')], origin=DataOrigin.PERSONA)
    assert ''.join(stream_findings_narration(context, client=FakeAnthropic())) == 'ok'
    assert seen['model'] == DEFAULT_MODEL


def _ups(tmp_path):
    from domain.physiology.state import create_patient, init_db, make_engine, make_session_factory

    engine = make_engine(tmp_path / 'gemini_ups.db')
    init_db(engine)
    factory = make_session_factory(engine)
    with factory() as s:
        pid = create_patient(s, display_name='Paciente de prueba')
    return factory, pid


def test_ups_context_counts_the_whole_window_not_only_the_last_snapshot(tmp_path):
    from app.engines.digital_twin_organism import DigitalTwinOrganism
    from domain.physiology.scenarios import run_scenario
    from domain.physiology.state import Provenance, from_digital_twin_organism, save_state

    factory, pid = _ups(tmp_path)
    with factory() as s:
        list(run_scenario(s, pid, 'taquicardia_estres', steps=3, organism=DigitalTwinOrganism()))
        assert build_context(s, pid).origin == DataOrigin.SIMULADO
        real = DigitalTwinOrganism()
        real.update_from_sensors({'ecg': {'heart_rate': 64}})
        save_state(s, from_digital_twin_organism(real, pid, provenance=Provenance.SENSOR_REAL,
                                                 source_detail='ecg_lab:ESP32 + AD8232 en COM3 (SENSOR_REAL)'))
        assert build_context(s, pid).origin == DataOrigin.PERSONA
        list(run_scenario(s, pid, 'taquicardia_estres', steps=2, organism=DigitalTwinOrganism()))
        context = build_context(s, pid)                                # lo último es simulado…
    hr = next(d for d in context.descriptors if d.name == 'heart_rate')
    assert hr.provenance == 'simulacion' and context.origin == DataOrigin.PERSONA   # …pero el «antes» no
    client, opener = recording_gemini()
    with pytest.raises(ProviderNotAllowedError):
        list(stream_narration(context, DepthLevel.ESTUDIANTE, client=client))
    assert opener.requests == []
    assert 'origin' not in context.to_payload()                        # el origen no va al modelo


# ================================================================ panel de la clave y laboratorios (AppTest)
@pytest.fixture(autouse=True)
def _no_env_key(monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)


def _app():
    from app.main import main
    main()


def test_entry_panel_accepts_a_gemini_key_for_this_session_only(monkeypatch):
    from streamlit.testing.v1 import AppTest

    checked = []
    monkeypatch.setattr(S, 'validate_gemini_key', lambda k: checked.append(k) or ('gemini-3.5-flash-lite', None))
    monkeypatch.setattr(S, 'validate_api_key', lambda k: pytest.fail('no debe verificar con Anthropic'))
    at = AppTest.from_function(_app, default_timeout=180)
    at.run()
    at.radio(key=S._PROVIDER).set_value(S.GEMINI).run()
    assert any('Nivel gratuito de Gemini' in i.value for i in at.info)
    at.text_input(key=S._INPUT).input('  clave-gemini  ')
    next(b for b in at.button if b.label == 'Entrar con mi clave').click().run()
    assert not at.exception, at.exception
    assert checked == ['clave-gemini'] and at.session_state[S.GEMINI_SESSION_KEY] == 'clave-gemini'
    assert at.session_state[S.GEMINI_MODEL_KEY] == 'gemini-3.5-flash-lite' and S.SESSION_KEY not in at.session_state
    assert 'IA activa con Gemini' in ' '.join(c.value for c in at.sidebar.caption)
    assert 'ANTHROPIC_API_KEY' not in os.environ
    next(b for b in at.sidebar.button if b.label == 'Olvidar mi clave').click().run()
    assert S.GEMINI_SESSION_KEY not in at.session_state


def test_lab_narrator_with_gemini_explains_simulated_data_and_blocks_a_person(monkeypatch):
    from streamlit.testing.v1 import AppTest

    import domain.physiology.narrator as N

    seen = []
    real_stream = N.stream_findings_narration

    def spy(context, client=None, **kw):
        seen.append((type(client).__name__, context.origin))
        if context.origin in (DataOrigin.SIMULADO, DataOrigin.BASE_PUBLICA):
            yield 'Explicación simulada.'
            return
        yield from real_stream(context, client=client, **kw)             # el candado real decide

    monkeypatch.setattr(N, 'stream_findings_narration', spy)

    def _script(origin):
        from app.main import render_findings_narrator
        render_findings_narrator('Lab de prueba', [('FC', '72 lpm', 'normal')], origin=origin)

    for origin, expected in ((DataOrigin.SIMULADO, 'Explicación simulada.'),
                             (DataOrigin.PERSONA, 'solo se explican datos simulados')):
        at = AppTest.from_function(_script, args=(origin,), default_timeout=120)
        at.session_state[S.GEMINI_SESSION_KEY] = 'clave-gemini'
        at.session_state[S.GEMINI_MODEL_KEY] = 'gemini-prueba'
        at.run()
        next(b for b in at.button if 'Explicar' in b.label).click().run()
        assert not at.exception, at.exception
        page = ' '.join(m.value for m in at.markdown) + ' ' + ' '.join(w.value for w in at.warning)
        assert expected in page, page
    assert seen == [('GeminiClient', DataOrigin.SIMULADO), ('GeminiClient', DataOrigin.PERSONA)]
