"""Construye el sitio estático a partir del registro (TAREA 25).

Reglas:

* La página sólo muestra lo que está en el registro firmado y fechado. No
  recalcula nada: ni medias, ni escaños, ni probabilidades. Si una cifra no
  está en la foto, no sale.
* Un día sin foto se DIBUJA como hueco, con su motivo. No se interpola.
* EL APAGÓN SE RESUELVE AQUÍ, NO EN EL CLIENTE. Desde el 24-nov-2026 a las
  00:00 (Europe/Madrid) y hasta el cierre de los colegios, el sitio se
  construye SIN NINGÚN dato de estimación: no se copia ninguna foto ni se
  escribe ninguna cifra en `index.json`. Ocultarlo con JavaScript no serviría:
  los ficheros seguirían siendo descargables.

Uso:  python .github/construir_sitio.py <destino>
Entorno: SITIO_NOW (ISO) congela la hora, para los tests.
"""
import json
import os
import shutil
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")
START = date(2026, 10, 12)
LAST = date(2026, 11, 23)
#: Las mismas fechas que el backend (`ENCUESTAS_BLACKOUT_*`): art. 69.7 LOREG,
#: cinco días antes de la votación, y reapertura al cierre de los colegios.
BLACKOUT_START = datetime(2026, 11, 24, 0, 0, tzinfo=MADRID)
BLACKOUT_END = datetime(2026, 11, 29, 20, 0, tzinfo=MADRID)

#: Lo que la página necesita de cada foto. Se copia tal cual; no se calcula.
CAMPOS_PORTADA = ("as_of", "newest_poll", "days_since_newest", "n_polls",
                  "window_days", "half_life_days", "regime", "majority",
                  "national", "seats", "seats_definitions", "blocs", "stress",
                  "conditional_on", "assumptions", "barrier_alerts",
                  "bias_correction", "baselines", "profiles", "model_version")


def ahora() -> datetime:
    v = os.environ.get("SITIO_NOW")
    return (datetime.fromisoformat(v).astimezone(MADRID) if v
            else datetime.now(MADRID))


def apagon(now: datetime) -> bool:
    return BLACKOUT_START <= now < BLACKOUT_END


def dias_esperados(now: datetime) -> list[date]:
    hoy = now.date()
    ultimo = min(LAST, hoy)
    n = (ultimo - START).days + 1
    return [date.fromordinal(START.toordinal() + i) for i in range(max(n, 0))]


def leer(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def recopilar(registro: Path, now: datetime) -> list[dict]:
    """Un renglón por día del calendario: foto, hueco o nada todavía."""
    filas = []
    for d in dias_esperados(now):
        carpeta = registro / f"{d:%Y}"
        foto = carpeta / f"{d.isoformat()}.json"
        hueco = carpeta / f"{d.isoformat()}.hueco.json"
        fila = {"date": d.isoformat()}
        if foto.exists():
            rec = leer(foto) or {}
            fila.update({
                "tipo": "foto",
                "model_version": rec.get("model_version"),
                "sha256_huella": rec.get("model_fingerprint_sha256")
                or rec.get("model_fingerprint"),
                "inputs_sha256": rec.get("inputs_sha256"),
                "schema": rec.get("schema"),
                "sello": (carpeta / f"{d.isoformat()}.json.ots").exists(),
            })
        elif hueco.exists():
            h = leer(hueco) or {}
            fila.update({
                "tipo": "hueco",
                # Los marcadores de esquema 1 (16 al 21-oct-2026) no llevan
                # `class`: se declararon antes de que existiera el campo y el
                # registro no se reescribe.
                "clase": h.get("class"),
                "motivo": h.get("reason"),
            })
        else:
            fila["tipo"] = "pendiente"
        filas.append(fila)
    return filas


def portada(registro: Path, filas: list[dict]) -> dict | None:
    """El `forecast` de la foto más reciente, tal cual se publicó."""
    for fila in reversed(filas):
        if fila["tipo"] != "foto":
            continue
        d = date.fromisoformat(fila["date"])
        rec = leer(registro / f"{d:%Y}" / f"{d.isoformat()}.json")
        fc = (rec or {}).get("forecast")
        if not fc:
            continue
        return {"date": fila["date"],
                **{k: fc[k] for k in CAMPOS_PORTADA if k in fc}}
    return None


def tendencia(registro: Path, filas: list[dict]) -> list[dict]:
    """Serie del voto publicado cada día. Los huecos van con `national: null`
    para que la página dibuje la interrupción en lugar de unir los puntos."""
    out = []
    for fila in filas:
        if fila["tipo"] == "foto":
            d = date.fromisoformat(fila["date"])
            fc = (leer(registro / f"{d:%Y}" / f"{d.isoformat()}.json")
                  or {}).get("forecast", {})
            out.append({"date": fila["date"],
                        "national": fc.get("national"),
                        "blocs": {k: v.get("p_majority")
                                  for k, v in (fc.get("blocs") or {}).items()}})
        else:
            out.append({"date": fila["date"], "national": None,
                        "blocs": None, "tipo": fila["tipo"]})
    return out


def construir(registro: Path, destino: Path, now: datetime) -> dict:
    datos = destino / "datos"
    datos.mkdir(parents=True, exist_ok=True)
    filas = recopilar(registro, now)
    cerrado = apagon(now)

    indice = {
        "generado_utc": now.astimezone(ZoneInfo("UTC")).isoformat(
            timespec="seconds"),
        "apagon": {
            "activo": cerrado,
            "desde": BLACKOUT_START.isoformat(),
            "hasta": BLACKOUT_END.isoformat(),
            "base_legal": "artículo 69.7 de la LOREG: no se publican sondeos "
                          "en los cinco días anteriores a la votación.",
        },
        "calendario": {"desde": START.isoformat(), "hasta": LAST.isoformat()},
        "dias": filas,
        "resumen": {
            "fotos": sum(1 for f in filas if f["tipo"] == "foto"),
            "huecos": sum(1 for f in filas if f["tipo"] == "hueco"),
        },
    }

    if cerrado:
        # Nada de estimación: ni portada, ni tendencia, ni copias de las
        # fotos. El índice del registro sí: decir qué días existen no es
        # publicar un sondeo.
        indice["portada"] = None
        indice["tendencia"] = None
        for viejo in datos.glob("*.json"):
            viejo.unlink()
    else:
        indice["portada"] = portada(registro, filas)
        indice["tendencia"] = tendencia(registro, filas)
        for fila in filas:
            if fila["tipo"] != "foto":
                continue
            d = date.fromisoformat(fila["date"])
            origen = registro / f"{d:%Y}" / f"{d.isoformat()}.json"
            shutil.copyfile(origen, datos / origen.name)

    (datos / "index.json").write_text(
        json.dumps(indice, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")

    plantilla = Path(__file__).parent / "sitio"
    for f in plantilla.iterdir():
        if f.is_file():
            shutil.copyfile(f, destino / f.name)
    return indice


def main() -> int:
    destino = Path(sys.argv[1] if len(sys.argv) > 1 else "_sitio")
    registro = Path("registro")
    now = ahora()
    indice = construir(registro, destino, now)
    print(f"sitio en {destino} | {now.isoformat(timespec='minutes')} "
          f"(Europe/Madrid) | apagón: {indice['apagon']['activo']} | "
          f"{indice['resumen']['fotos']} fotos, "
          f"{indice['resumen']['huecos']} huecos")
    if indice["portada"]:
        print("  portada:", indice["portada"]["date"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
