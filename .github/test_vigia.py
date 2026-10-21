"""Pruebas del vigía, sin dependencias: `python .github/test_vigia.py`.

Las reglas del vigía son afirmaciones sobre el comportamiento del sistema, y
en este proyecto una afirmación sin test se borra. La que importa: un fallo
diario declarado como hueco diario NO puede dejar callado al vigía.
"""
import json
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
import vigia  # noqa: E402

MADRID = ZoneInfo("Europe/Madrid")


def montar(dias: dict) -> Path:
    """dias: {'2026-10-12': 'foto' | 'operativo' | 'averia' | None}"""
    root = Path(tempfile.mkdtemp())
    carpeta = root / "registro" / "2026"
    carpeta.mkdir(parents=True)
    for dia, que in dias.items():
        if que == "foto":
            (carpeta / f"{dia}.json").write_text("{}", encoding="utf-8")
        elif que in ("operativo", "averia"):
            (carpeta / f"{dia}.hueco.json").write_text(
                json.dumps({"schema": 2, "type": "hueco", "date": dia,
                            "class": que, "reason": f"motivo {que}"}),
                encoding="utf-8")
    return root


def dias_hasta(hasta: str, que: str) -> dict:
    fin = date.fromisoformat(hasta)
    n = (fin - vigia.START).days + 1
    return {(vigia.START + timedelta(days=i)).isoformat(): que
            for i in range(n)}


def ahora(txt: str) -> datetime:
    return datetime.fromisoformat(txt).astimezone(MADRID)


def check(nombre, cond):
    print(("OK   " if cond else "FALLA") + "  " + nombre)
    if not cond:
        check.fallos += 1


check.fallos = 0


# 1. Todo con foto: calla.
root = montar(dias_hasta("2026-10-22", "foto"))
mal, texto = vigia.summarize(vigia.audit(root, ahora("2026-10-22T09:15+02:00")))
check("con todas las fotos no avisa", not mal)

# 2. Un día sin nada: avisa.
d = dias_hasta("2026-10-22", "foto"); d["2026-10-18"] = None
mal, texto = vigia.summarize(vigia.audit(montar(d),
                                         ahora("2026-10-22T09:15+02:00")))
check("un día sin foto ni hueco avisa", mal and "2026-10-18" in texto)

# 3. UN hueco operativo aislado: no avisa (host apagado una noche).
d = dias_hasta("2026-10-22", "foto"); d["2026-10-18"] = "operativo"
mal, _ = vigia.summarize(vigia.audit(montar(d),
                                     ahora("2026-10-22T09:15+02:00")))
check("un hueco operativo aislado se tolera", not mal)

# 4. UN hueco por avería: avisa el primer día.
d = dias_hasta("2026-10-22", "foto"); d["2026-10-22"] = "averia"
mal, texto = vigia.summarize(vigia.audit(montar(d),
                                         ahora("2026-10-22T09:15+02:00")))
check("un hueco por avería avisa desde el primer día",
      mal and "AVERÍA" in texto)

# 5. LA REGLA QUE IMPORTA: huecos operativos todos los días no callan al
#    vigía. Es el 15-oct con otro disfraz.
root = montar(dias_hasta("2026-10-22", "operativo"))
mal, texto = vigia.summarize(vigia.audit(root, ahora("2026-10-22T09:15+02:00")))
check("una racha de huecos operativos avisa igual",
      mal and "días seguidos sin foto" in texto)

# 6. Dos huecos operativos seguidos: todavía no (un fin de semana apagado).
d = dias_hasta("2026-10-22", "foto")
d["2026-10-21"] = d["2026-10-22"] = "operativo"
mal, _ = vigia.summarize(vigia.audit(montar(d),
                                     ahora("2026-10-22T09:15+02:00")))
check("dos huecos seguidos se toleran", not mal)

# 7. Tres seguidos: sí.
d["2026-10-20"] = "operativo"
mal, texto = vigia.summarize(vigia.audit(montar(d),
                                         ahora("2026-10-22T09:15+02:00")))
check("tres huecos seguidos avisan", mal and "3 días seguidos" in texto)

# 8. La foto corta la racha.
d = dias_hasta("2026-10-22", "foto")
for x in ("2026-10-15", "2026-10-16", "2026-10-18", "2026-10-19"):
    d[x] = "operativo"
mal, _ = vigia.summarize(vigia.audit(montar(d),
                                     ahora("2026-10-22T09:15+02:00")))
check("una foto en medio corta la racha", not mal)

# 9. El día de hoy no se exige antes de las 09:00, y sí después.
root = montar(dias_hasta("2026-10-21", "foto"))
check("hoy no se exige a las 08:30",
      not vigia.summarize(vigia.audit(root, ahora("2026-10-22T08:30+02:00")))[0])
check("hoy se exige a las 09:15",
      vigia.summarize(vigia.audit(root, ahora("2026-10-22T09:15+02:00")))[0])

# 10. Después del cambio de hora, la hora peninsular es la que manda: las
#     08:15 UTC del 26-oct son las 09:15 en Madrid.
check("el cambio de hora no desplaza el corte de las 09:00",
      vigia.audit(root, ahora("2026-10-26T08:15+00:00"))["dias"]
      > vigia.audit(root, ahora("2026-10-26T07:15+00:00"))["dias"])

# 11. El apagón no es hueco.
check("el apagón no se exige",
      vigia.expected(ahora("2026-12-01T10:00+01:00"))[-1] == date(2026, 11, 23))

# 12. Un marcador ilegible cuenta como avería, no como hueco válido.
root = montar(dias_hasta("2026-10-22", "foto"))
(root / "registro" / "2026" / "2026-10-22.json").unlink()
(root / "registro" / "2026" / "2026-10-22.hueco.json").write_text(
    "{roto", encoding="utf-8")
mal, texto = vigia.summarize(vigia.audit(root, ahora("2026-10-22T09:15+02:00")))
check("un marcador ilegible avisa", mal and "AVERÍA" in texto)

print(f"\n{check.fallos} fallos")
sys.exit(1 if check.fallos else 0)
