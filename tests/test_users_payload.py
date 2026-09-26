import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from omada_client.users import LocalUserInput


def test_to_payload_basic_fields():
    data = LocalUserInput(user_name="jdoe", password="Sup3rSecret!", max_users=2)
    payload = data.to_payload()

    assert payload["userName"] == "jdoe"
    assert payload["password"] == "Sup3rSecret!"
    assert payload["maxUsers"] == 2
    assert payload["applyToAllPortals"] is True


def test_to_payload_no_expiration_defaults_to_end_of_current_year():
    # El controlador exige expirationTime > tiempo actual (no acepta 0 como
    # "sin expiración"). Igual que la interfaz gráfica de Omada al crear un
    # usuario sin especificar fecha, expiration_days=0 debe producir el 31
    # de diciembre del año en curso a las 23:59:59.
    import time
    from datetime import datetime

    payload = LocalUserInput(user_name="jdoe", password="x", expiration_days=0).to_payload()
    now = datetime.now()
    expected = datetime(now.year, 12, 31, 23, 59, 59)
    if expected <= now:
        expected = datetime(now.year + 1, 12, 31, 23, 59, 59)

    assert payload["expirationTime"] == int(expected.timestamp() * 1000)
    assert payload["expirationTime"] > time.time() * 1000


def test_to_payload_with_expiration():
    data = LocalUserInput(user_name="jdoe", password="x", expiration_days=1)
    payload = data.to_payload()
    assert payload["expirationTime"] > 0


def test_to_payload_daily_limit_within_valid_range():
    # customTimeout se valida en la API incluso con dailyLimitEnable=False
    # (debe estar entre 1 y 1440 minutos).
    payload = LocalUserInput(user_name="a", password="x").to_payload()
    assert 1 <= payload["dailyLimit"]["customTimeout"] <= 1440


def test_to_payload_rate_limit_mode():
    without_limits = LocalUserInput(user_name="a", password="x").to_payload()
    assert without_limits["rateLimit"]["mode"] == 0

    with_limits = LocalUserInput(user_name="a", password="x", down_limit_kbps=1024).to_payload()
    assert with_limits["rateLimit"]["mode"] == 2
    assert with_limits["rateLimit"]["customRateLimit"]["downLimitEnable"] is True
