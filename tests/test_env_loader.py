"""El `.env` de la raíz se carga sin pisar el entorno ni aceptar el placeholder."""
import os

from app.utils.env_loader import load_dotenv_file, parse_dotenv


def test_parse_formats():
    parsed = parse_dotenv(
        "# comentario\n"
        "A=1\n"
        "export B = dos\n"
        "C=\"con espacios\"\n"
        "D='x=y'\n"
        "E=valor # nota\n"
        "linea sin igual\n"
    )
    assert parsed == {"A": "1", "B": "dos", "C": "con espacios", "D": "x=y", "E": "valor"}


def test_load_does_not_override_and_skips_placeholder(tmp_path, monkeypatch):
    monkeypatch.setenv("BIOCORE_YA_DEFINIDA", "entorno")
    monkeypatch.delenv("BIOCORE_NUEVA", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    env = tmp_path / ".env"
    env.write_text(
        "BIOCORE_YA_DEFINIDA=archivo\nBIOCORE_NUEVA=ok\nANTHROPIC_API_KEY=sk-your-key-here\n",
        encoding="utf-8",
    )
    loaded = load_dotenv_file(env)
    assert os.environ["BIOCORE_YA_DEFINIDA"] == "entorno"
    assert os.environ["BIOCORE_NUEVA"] == "ok"
    assert "ANTHROPIC_API_KEY" not in os.environ
    assert loaded == {"BIOCORE_NUEVA": "ok"}
    monkeypatch.delenv("BIOCORE_NUEVA")


def test_missing_file_is_noop(tmp_path):
    assert load_dotenv_file(tmp_path / "no_existe.env") == {}
