"""Vigía del registro, independiente del host que publica.

Corre en GitHub Actions, no en la máquina que hace las fotos: el 15-oct-2026
murió el publicador y nadie se enteró en seis días porque la vigilancia
vivía dentro del proceso caído.

Para cada día del calendario operativo (12-oct a 23-nov de 2026, sin el
apagón) hasta HOY en hora peninsular, exige `registro/AAAA/AAAA-MM-DD.json`
o un hueco declarado `AAAA-MM-DD.hueco.json`. El día de hoy sólo se exige a
partir de las 09:00 Europe/Madrid (foto a las 07:00 más margen).

Escribe en GITHUB_OUTPUT `missing` (fechas separadas por espacios) y sale
con 1 si falta alguna, para que el fallo sea visible.
"""
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")
START = date(2026, 10, 12)
LAST = date(2026, 11, 23)        # víspera del apagón del art. 69.7 LOREG
DUE_HOUR = 9


def expected(now: datetime) -> list[date]:
    today = now.date()
    last = min(LAST, today if now.hour >= DUE_HOUR else today - timedelta(days=1))
    return [START + timedelta(days=i) for i in range((last - START).days + 1)]


def missing(root: Path, now: datetime) -> list[date]:
    out = []
    for d in expected(now):
        base = root / "registro" / f"{d:%Y}"
        if not (base / f"{d.isoformat()}.json").exists() and \
                not (base / f"{d.isoformat()}.hueco.json").exists():
            out.append(d)
    return out


def main() -> int:
    now = (datetime.fromisoformat(os.environ["VIGIA_NOW"]).astimezone(MADRID)
           if os.environ.get("VIGIA_NOW") else datetime.now(MADRID))
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    miss = missing(root, now)
    print(f"ahora {now.isoformat(timespec='minutes')} (Europe/Madrid); "
          f"{len(expected(now))} días exigibles; faltan: "
          + (" ".join(d.isoformat() for d in miss) or "ninguno"))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"missing={' '.join(d.isoformat() for d in miss)}\n")
    return 1 if miss else 0


if __name__ == "__main__":
    sys.exit(main())
