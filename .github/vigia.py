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
  3. RACHA: más de MAX_RACHA huecos consecutivos **que lleguen hasta hoy**,
     sean de la clase que sean. Un host que no vuelve en tres días no es un
     incidente operativo.

     Es la racha VIGENTE, no la máxima histórica. Con la máxima, la racha
     del 16 al 21 de octubre dejaba el vigía en rojo para siempre: no podía
     bajar de 6 nunca, así que a partir del 22-oct el vigía fallaba cada
     hora aunque la foto saliera, y un aviso que siempre está encendido no
     avisa de nada. Lo que la regla quiere detectar es una máquina que NO
     VUELVE, y una foto nueva es la prueba de que volvió. La máxima
     histórica se sigue imprimiendo en el log, como dato, no como alarma.
  4. WEB: la web pública no responde 200. El vigía miraba el registro y no la
     web, y ése es justo el hueco que costó seis días: algo que se cae y nadie
     se entera. Importa especialmente porque el proxy del VPS apunta a la IP
     de la pasarela de una red de Docker ajena: si alguien recrea esa red, la
     IP cambia y la web da 502 EN SILENCIO (ver deploy/PLAN-VPS.md).

  5. CÓDIGO VIEJO: la última foto se hizo con un clon que iba por detrás del
     repositorio. El 22-oct-2026 la foto salió con tres commits de retraso
     (al final del día eran nueve) porque el publicador vive en un clon que
     se actualiza a mano: salió sin la limitación que se había escrito esa
     noche, sin la tabla del recorte y con los avisos de barrera viejos. La
     foto lo dice todo, pero nadie lo miraba.

     El número lo pone el publicador (`code_behind`), no este vigía: el
     código es PRIVADO y desde el repositorio del registro no se puede leer
     su `origin/main`. Aquí sólo se lee lo que la foto declara. No bloquea
     nada: una foto con retraso es mejor que ninguna, pero deja de ser
     invisible.

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
#: Web pública. Se comprueba siempre que el nombre resuelva; mientras no
#: exista, no se avisa (no hay nada que vigilar todavía).
WEB_TIMEOUT = 20
#: Fichero versionado que dice si se vigila la web (ver .github/vigia-web.json).
WEB_CONF = Path(__file__).parent / "vigia-web.json"


def web_conf() -> dict:
    try:
        d = json.loads(WEB_CONF.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"vigilar": False, "url": "", "motivo": "sin vigia-web.json"}
    if os.environ.get("VIGIA_WEB"):
        d = {**d, "url": os.environ["VIGIA_WEB"], "vigilar": True}
    return d


def expected(now: datetime) -> list[date]:
    today = now.date()
    last = min(LAST, today if now.hour >= DUE_HOUR else today - timedelta(days=1))
    return [START + timedelta(days=i) for i in range((last - START).days + 1)]


def codigo_de_la_ultima_foto(root: Path, dias: list[date]) -> dict | None:
    """Qué dice la foto más reciente sobre el código que la hizo.

    `code_behind` lo publica el publicador (esquema 4). En fotos anteriores
    no existe: entonces no se puede afirmar nada y no se avisa, que es
    distinto de afirmar que estaba al día.
    """
    for d in reversed(dias):
        p = root / "registro" / f"{d:%Y}" / f"{d.isoformat()}.json"
        if not p.exists():
            continue
        try:
            foto = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            return {"date": d, "behind": None, "commit": None,
                    "motivo": "la foto no se puede leer"}
        return {"date": d, "behind": foto.get("code_behind"),
                "commit": (foto.get("code_commit") or "")[:12],
                "schema": foto.get("schema")}
    return None


def _texto_codigo(cod: dict | None) -> str:
    """«sin declarar» no es «al día»: una foto de esquema 3 no lo dice."""
    if not cod:
        return "sin foto"
    if cod.get("behind") == 0:
        return "al día"
    if cod.get("behind"):
        return f"{cod['behind']} commits por detrás"
    return "sin declarar"


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
    # `racha` quedó con la que llega hasta el último día exigible: ésa es la
    # que alarma. `peor_racha` es historia y sólo se imprime.
    return {"dias": len(dias), "missing": missing, "broken": broken,
            "streak": racha, "streak_end": dias[-1] if dias and racha else None,
            "peor_racha": peor_racha, "peor_racha_fin": fin_racha,
            "codigo": codigo_de_la_ultima_foto(root, dias)}


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
                      "aunque cada día se haya declarado como operativo. La "
                      "racha SIGUE ABIERTA: no hay foto del último día "
                      "exigible.")
    cod = a.get("codigo")
    if cod and cod.get("behind"):
        lineas.append(
            f"La foto del {cod['date']} se hizo con código VIEJO: "
            f"{cod['behind']} commits por detrás de origin/main "
            f"(code_commit {cod['commit']}). El publicador vive en un clon "
            f"que se actualiza a mano; desplegar es `git pull` en el clon Y "
            f"reiniciar la tarea. La foto es válida y no se reemite, pero "
            f"no lleva lo que se arregló después.")

    web = a.get("web")
    if web and web.get("vigilar") and web["estado"] not in (None, 200):
        lineas.append(
            f"La web pública NO responde 200: {web['url']} -> "
            f"{web.get('detalle') or web['estado']}. El pronóstico puede "
            "estar saliendo y la web caída: son dos fallos distintos.")
    return bool(lineas), "\n".join(lineas)


def comprobar_web(url: str) -> dict:
    """¿Responde la web pública? `estado: None` si el nombre aún no resuelve:
    eso no es una avería, es que todavía no existe."""
    import socket
    import urllib.error
    import urllib.request
    from urllib.parse import urlparse
    host = urlparse(url).hostname
    try:
        socket.getaddrinfo(host, 443)
    except OSError:
        return {"url": url, "estado": None,
                "detalle": f"{host} todavía no resuelve"}
    try:
        req = urllib.request.Request(
            url, method="GET", headers={"User-Agent": "vigia-registro"})
        with urllib.request.urlopen(req, timeout=WEB_TIMEOUT) as r:
            return {"url": url, "estado": r.status,
                    "bytes": len(r.read(2048))}
    except urllib.error.HTTPError as e:
        return {"url": url, "estado": e.code, "detalle": f"HTTP {e.code}"}
    except Exception as e:  # noqa: BLE001
        return {"url": url, "estado": 0,
                "detalle": f"{type(e).__name__}: {e}"}


def main() -> int:
    now = (datetime.fromisoformat(os.environ["VIGIA_NOW"]).astimezone(MADRID)
           if os.environ.get("VIGIA_NOW") else datetime.now(MADRID))
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    a = audit(root, now)
    conf = web_conf()
    medida = (comprobar_web(conf["url"]) if conf.get("url")
              else {"url": "", "estado": None, "detalle": "sin url"})
    a["web"] = {**medida, "vigilar": bool(conf.get("vigilar")),
                "motivo": conf.get("motivo", "")}
    mal, texto = summarize(a)
    web = a["web"]
    print(f"ahora {now.isoformat(timespec='minutes')} (Europe/Madrid); "
          f"{a['dias']} días exigibles; racha vigente sin foto {a['streak']} "
          f"(máxima histórica {a['peor_racha']}"
          + (f", hasta el {a['peor_racha_fin']}" if a["peor_racha_fin"] else "")
          + f"); código de la última foto: {_texto_codigo(a.get('codigo'))}; "
          + f"web {web.get('detalle') or web['estado']}"
          + ("" if web.get("vigilar") else
             f" (NO vigilada: {web.get('motivo')})"))
    print(texto or "todo en orden: cada día exigible tiene foto, o un hueco "
                   "operativo declarado y ninguna racha larga.")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"missing={' '.join(d.isoformat() for d in a['missing'])}\n")
            f.write(f"broken={' '.join(d.isoformat() for d, _ in a['broken'])}\n")
            f.write(f"streak={a['streak']}\n")
            f.write(f"web={a['web']['estado']}\n")
            f.write("summary<<FIN\n" + (texto or "ok") + "\nFIN\n")
    return 1 if mal else 0


if __name__ == "__main__":
    sys.exit(main())
