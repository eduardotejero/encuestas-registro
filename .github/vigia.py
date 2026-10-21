"""Vigía del registro, independiente del host que publica.

Corre en GitHub Actions, no en la máquina que hace las fotos: el 15-oct-2026
murió el publicador y nadie se enteró en seis días porque la vigilancia
vivía dentro del proceso caído.

Un vigía que acepte "foto O hueco declarado" se puede satisfacer con el
mismo fallo que debe detectar: si la ingesta revienta cada día y cada día se
declara un hueco, el vigía calla y la máquina está muerta en silencio. Así
que hay tres reglas, no una:

  1. FALTA: un día del calendario operativo sin foto y sin hueco declarado.
  2. AVERÍA: un hueco cuya clase es `averia` (el publicador estaba en marcha
     y falló). Avisa desde el PRIMER día.
  3. RACHA: más de MAX_RACHA huecos consecutivos, sean de la clase que sean.
     Un host que no vuelve en tres días no es un incidente operativo.

Calendario: del 12-oct al 23-nov de 2026 (el apagón del art. 69.7 LOREG no
es hueco). El día de hoy sólo se exige a partir de las 09:00 Europe/Madrid
(la foto es a las 07:00, más margen).

Escribe en GITHUB_OUTPUT `missing`, `broken`, `streak` y `summary`, y sale
con 1 si alguna regla se dispara.
"""
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")
START = date(2026, 10, 12)
LAST = date(2026, 11, 23)        # víspera del apagón del art. 69.7 LOREG
DUE_HOUR = 9
#: Más de estos huecos seguidos es una avería, aunque cada uno se declare
#: como operativo. Dos noches con el host apagado son un incidente; tres
#: días seguidos sin foto son una máquina que no vuelve.
MAX_RACHA = 2
GAP_AVERIA = "averia"


def expected(now: datetime) -> list[date]:
    today = now.date()
    last = min(LAST, today if now.hour >= DUE_HOUR else today - timedelta(days=1))
    return [START + timedelta(days=i) for i in range((last - START).days + 1)]


def _gap(root: Path, d: date) -> dict | None:
    p = root / "registro" / f"{d:%Y}" / f"{d.isoformat()}.hueco.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        # Un marcador ilegible es tan malo como no tenerlo.
        return {"class": GAP_AVERIA, "reason": "marcador de hueco ilegible"}


def audit(root: Path, now: datetime) -> dict:
    dias = expected(now)
    missing: list[date] = []       # ni foto ni hueco
    broken: list[tuple[date, str]] = []   # hueco por avería
    racha, peor_racha, fin_racha = 0, 0, None
    for d in dias:
        foto = (root / "registro" / f"{d:%Y}" / f"{d.isoformat()}.json").exists()
        hueco = _gap(root, d)
        if foto:
            racha = 0
            continue
        if hueco is None:
            missing.append(d)
        elif hueco.get("class") == GAP_AVERIA:
            broken.append((d, (hueco.get("reason") or "")[:200]))
        racha += 1
        if racha > peor_racha:
            peor_racha, fin_racha = racha, d
    return {"dias": len(dias), "missing": missing, "broken": broken,
            "streak": peor_racha, "streak_end": fin_racha}


def summarize(a: dict) -> tuple[bool, str]:
    lineas = []
    if a["missing"]:
        lineas.append("Días sin foto NI hueco declarado: "
                      + " ".join(d.isoformat() for d in a["missing"])
                      + ". El publicador no ha empujado nada: o el host está "
                      "caído, o la publicación está parada sin declarar el "
                      "hueco.")
    for d, motivo in a["broken"]:
        lineas.append(f"Hueco por AVERÍA el {d.isoformat()}: {motivo}")
    if a["streak"] > MAX_RACHA:
        lineas.append(f"{a['streak']} días seguidos sin foto hasta el "
                      f"{a['streak_end']}: más de {MAX_RACHA} es una avería, "
                      "aunque cada día se haya declarado como operativo.")
    return bool(lineas), "\n".join(lineas)


def main() -> int:
    now = (datetime.fromisoformat(os.environ["VIGIA_NOW"]).astimezone(MADRID)
           if os.environ.get("VIGIA_NOW") else datetime.now(MADRID))
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    a = audit(root, now)
    mal, texto = summarize(a)
    print(f"ahora {now.isoformat(timespec='minutes')} (Europe/Madrid); "
          f"{a['dias']} días exigibles; racha máxima sin foto {a['streak']}")
    print(texto or "todo en orden: cada día exigible tiene foto, o un hueco "
                   "operativo declarado y ninguna racha larga.")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"missing={' '.join(d.isoformat() for d in a['missing'])}\n")
            f.write(f"broken={' '.join(d.isoformat() for d, _ in a['broken'])}\n")
            f.write(f"streak={a['streak']}\n")
            f.write("summary<<FIN\n" + (texto or "ok") + "\nFIN\n")
    return 1 if mal else 0


if __name__ == "__main__":
    sys.exit(main())
