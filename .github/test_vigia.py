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

# --- la web pública -------------------------------------------------------
# El 21-oct: el vigía miraba el registro y no la web. Importa porque el proxy
# del VPS apunta a la IP de la pasarela de una red de Docker ajena: si alguien
# la recrea, la web da 502 en silencio.
root = montar(dias_hasta("2026-10-22", "foto"))


def con_web(estado, vigilar=True):
    a = vigia.audit(root, ahora("2026-10-22T09:15+02:00"))
    a["web"] = {"url": "https://x/", "estado": estado, "vigilar": vigilar,
                "detalle": None if estado == 200 else f"HTTP {estado}"}
    return vigia.summarize(a)


check("web 200 no avisa", not con_web(200)[0])
mal, texto = con_web(502)
check("web 502 avisa", mal and "NO responde 200" in texto)
check("web inalcanzable avisa", con_web(0)[0])
check("web caída pero NO vigilada no avisa", not con_web(502, vigilar=False)[0])
check("un nombre que aún no resuelve no avisa", not con_web(None)[0])
check("registro y web son avisos distintos",
      "dos fallos distintos" in con_web(502)[1])

# 11. EL CASO REAL DEL 22-OCT. Seis huecos del 16 al 21 y foto el 22: la
#     racha ya está CERRADA, la máquina volvió, y el vigía tiene que estar
#     verde. Con la racha máxima histórica no podía bajar de 6 nunca, así
#     que el vigía fallaba cada hora hasta el 23-nov y dejaba de avisar de
#     nada. Un aviso permanentemente encendido no es un aviso.
d = dias_hasta("2026-10-22", "foto")
for x in ("2026-10-16", "2026-10-17", "2026-10-18",
          "2026-10-19", "2026-10-20", "2026-10-21"):
    d[x] = "operativo"
a = vigia.audit(montar(d), ahora("2026-10-22T09:15+02:00"))
mal, texto = vigia.summarize(a)
check("una racha larga YA CERRADA no deja el vigía en rojo", not mal)
check("la racha histórica se sigue contando, como dato", a["peor_racha"] == 6)
check("la racha vigente es cero cuando hay foto hoy", a["streak"] == 0)

# 12. Y si la racha llega hasta hoy, sigue avisando: la regla no se ha
#     ablandado, sólo se ha anclado al presente.
d2 = dias_hasta("2026-10-22", "foto")
for x in ("2026-10-20", "2026-10-21", "2026-10-22"):
    d2[x] = "operativo"
a2 = vigia.audit(montar(d2), ahora("2026-10-22T09:15+02:00"))
check("una racha abierta hasta hoy sigue avisando",
      vigia.summarize(a2)[0] and a2["streak"] == 3)

# 13. CÓDIGO VIEJO. La causa común de los tres fallos del 22-oct: el
#     publicador puede ir por detrás del repositorio sin que nadie se entere.
#     La foto declara `code_behind`; el vigía lo hace visible, sin bloquear.
def con_codigo(behind, schema=4):
    root = montar(dias_hasta("2026-10-22", "foto"))
    p = root / "registro" / "2026" / "2026-10-22.json"
    foto = {"schema": schema, "date": "2026-10-22",
            "code_commit": "abc123def456789", "model_version": "2026.10.6"}
    if behind is not None:
        foto["code_behind"] = behind
    p.write_text(json.dumps(foto), encoding="utf-8")
    return vigia.audit(root, ahora("2026-10-22T09:15+02:00"))


a = con_codigo(0)
check("código al día no avisa", not vigia.summarize(a)[0])
check("y lo dice en el log", vigia._texto_codigo(a["codigo"]) == "al día")

a = con_codigo(9)
mal, texto = vigia.summarize(a)
check("nueve commits de retraso avisan", mal and "código VIEJO" in texto)
check("el aviso dice cuántos y qué commit",
      "9 commits" in texto and "abc123def456" in texto)
check("y dice que la foto NO se reemite", "no se reemite" in texto)

a = con_codigo(None, schema=3)
check("una foto que no lo declara no avisa", not vigia.summarize(a)[0])
check("«sin declarar» no es «al día»",
      vigia._texto_codigo(a["codigo"]) == "sin declarar")

conf = json.loads((Path(__file__).parent / "vigia-web.json")
                  .read_text(encoding="utf-8"))
check("vigia-web.json declara url, vigilar y motivo",
      bool(conf.get("url")) and "vigilar" in conf and bool(conf.get("motivo")))

print(f"\n{check.fallos} fallos")
sys.exit(1 if check.fallos else 0)
