"""Pruebas del sitio estático: `python .github/test_sitio.py`.

La que de verdad importa es el apagón. En un sitio estático no basta con
ocultar los números por JavaScript: los ficheros de datos seguirían siendo
descargables. Así que desde el 24-nov-2026 a las 00:00 (Europe/Madrid) el
sitio se CONSTRUYE sin ningún dato de estimación, y eso se comprueba con
fecha congelada, igual que en el backend.
"""
import json
import os
import shutil
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))
import construir_sitio as cs  # noqa: E402

MADRID = ZoneInfo("Europe/Madrid")
#: CIFRAS de estimación: ni una puede aparecer en ningún fichero servido
#: durante el apagón. Un derivado de encuestas es un sondeo.
CIFRAS = ("31.25", "27.13", "18.71", "0.9747", "193.5", "128.4", "131",
          "0.7994", "183.3")
#: HASHES y metadatos del registro: sí siguen. Decir qué días tienen foto, con
#: qué versión del modelo y con qué huella, no publica ninguna estimación, y
#: ya están en el repositorio público. Sin esto el índice del registro —lo
#: único que la ley deja ver esos días— perdería su valor probatorio.
HASHES = ("fc66bbf6", "2026.10.5")


def registro_falso(dias: dict) -> Path:
    """dias: {'2026-11-23': 'foto'|'operativo'|'averia'}"""
    root = Path(tempfile.mkdtemp())
    carpeta = root / "registro" / "2026"
    carpeta.mkdir(parents=True)
    for dia, que in dias.items():
        if que == "foto":
            (carpeta / f"{dia}.json").write_text(json.dumps({
                "date": dia, "schema": 2, "model_version": "2026.10.5",
                "model_fingerprint_sha256": "fc66bbf6" + "0" * 56,
                "inputs_sha256": "a" * 64,
                "forecast": {
                    "as_of": dia, "newest_poll": dia, "n_polls": 25,
                    "window_days": 30, "half_life_days": 10.0,
                    "regime": "disperso", "majority": 176,
                    "national": {"PP": 31.25, "PSOE": 27.13, "Vox": 18.71},
                    "seats": [{"party": "PP", "mean": 128.4, "central": 131,
                               "p10": 116, "p90": 141}],
                    "blocs": {"derecha": {"p_majority": 0.9747, "mean": 193.5,
                                          "p10": 182, "p90": 206,
                                          "parties": ["PP", "Vox"]}},
                    "stress": {"bloc": "derecha", "members": ["PP", "Vox"],
                               "p_majority": 0.9747, "mean": 193.5,
                               "scenarios": [{"label": "abril de 2019",
                                              "p_majority": 0.7994,
                                              "margin_error": 5.25,
                                              "mean": 183.3}]},
                    "model_version": "2026.10.5",
                },
            }), encoding="utf-8")
            (carpeta / f"{dia}.json.ots").write_bytes(b"sello")
        else:
            (carpeta / f"{dia}.hueco.json").write_text(json.dumps({
                "schema": 2, "type": "hueco", "date": dia, "class": que,
                "reason": f"motivo {que}"}), encoding="utf-8")
    return root


def construir(root: Path, cuando: str):
    destino = Path(tempfile.mkdtemp()) / "_sitio"
    now = datetime.fromisoformat(cuando).astimezone(MADRID)
    ix = cs.construir(root / "registro", destino, now)
    return ix, destino


def ficheros(destino: Path) -> str:
    """Todo el texto servido: si una cifra está aquí, es descargable."""
    out = []
    for f in destino.rglob("*"):
        if f.is_file():
            out.append(f.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(out)


def check(nombre, cond):
    print(("OK   " if cond else "FALLA") + "  " + nombre)
    if not cond:
        check.fallos += 1


check.fallos = 0

todos = {(cs.START + timedelta(days=i)).isoformat(): "foto"
         for i in range((cs.LAST - cs.START).days + 1)}

# --- Antes del apagón: los datos están y la portada es la última foto ------
root = registro_falso(todos)
ix, destino = construir(root, "2026-11-23T10:00:00+01:00")
check("antes del apagón hay portada", ix["portada"] is not None)
check("antes del apagón hay tendencia", bool(ix["tendencia"]))
check("antes del apagón se copian las fotos",
      (destino / "datos" / "2026-11-23.json").exists())
check("antes del apagón las cifras son descargables",
      all(h in ficheros(destino) for h in CIFRAS))
check("la portada es la foto más reciente", ix["portada"]["date"] == "2026-11-23")

# --- El margen de dos horas sobre el apagón legal -------------------------
check("el sitio se apaga antes que la ley",
      cs.BLACKOUT_START < cs.LEGAL_BLACKOUT_START)
check("el margen es de dos horas",
      cs.LEGAL_BLACKOUT_START - cs.BLACKOUT_START == timedelta(hours=2))
ix, _ = construir(root, "2026-11-23T21:59:00+01:00")
check("a las 21:59 del 23 el sitio sigue abierto",
      ix["apagon"]["activo"] is False and ix["portada"] is not None)

# --- EL APAGÓN: ni un número de estimación en ningún fichero --------------
for cuando, etiqueta in (
    ("2026-11-23T22:00:00+01:00", "a las 22:00 del 23 (dos horas antes de la ley)"),
    ("2026-11-23T23:30:00+01:00", "la noche del 23, antes de la medianoche legal"),
    ("2026-11-24T00:00:00+01:00", "en el primer instante del apagón legal"),
    ("2026-11-24T00:01:00+01:00", "un minuto después"),
    ("2026-11-26T12:00:00+01:00", "en mitad del apagón"),
    ("2026-11-29T19:59:00+01:00", "un minuto antes de cerrar los colegios"),
):
    ix, destino = construir(root, cuando)
    texto = ficheros(destino)
    check(f"{etiqueta}: apagón activo", ix["apagon"]["activo"] is True)
    check(f"{etiqueta}: sin portada", ix["portada"] is None)
    check(f"{etiqueta}: sin tendencia", ix["tendencia"] is None)
    check(f"{etiqueta}: ninguna foto copiada",
          not list((destino / "datos").glob("2026-*.json")))
    fugas = [h for h in CIFRAS if h in texto]
    check(f"{etiqueta}: ninguna cifra descargable ({fugas})", not fugas)
    check(f"{etiqueta}: las huellas del registro sí siguen",
          all(h in texto for h in HASHES))
    check(f"{etiqueta}: el índice del registro sigue",
          len(ix["dias"]) > 0 and any(d["tipo"] == "foto" for d in ix["dias"]))

# --- Reapertura al cierre de los colegios --------------------------------
ix, destino = construir(root, "2026-11-29T20:00:00+01:00")
check("al cerrar los colegios vuelven los datos",
      ix["apagon"]["activo"] is False and ix["portada"] is not None)

# --- Una construcción durante el apagón BORRA lo de la anterior ----------
destino2 = Path(tempfile.mkdtemp()) / "_sitio"
cs.construir(root / "registro", destino2,
             datetime.fromisoformat("2026-11-23T10:00:00+01:00"))
assert (destino2 / "datos" / "2026-11-23.json").exists()
cs.construir(root / "registro", destino2,
             datetime.fromisoformat("2026-11-25T10:00:00+01:00"))
check("una reconstrucción en apagón borra las fotos ya copiadas",
      not list((destino2 / "datos").glob("2026-*.json")))
check("y no quedan cifras en el destino reutilizado",
      not [h for h in CIFRAS if h in ficheros(destino2)])

# --- Huecos: se dibujan, con su motivo, y no se interpolan ---------------
mixto = dict(todos)
for d in ("2026-10-16", "2026-10-17", "2026-10-18"):
    mixto[d] = "operativo"
mixto["2026-10-19"] = "averia"
ix, destino = construir(registro_falso(mixto), "2026-10-20T10:00:00+02:00")
huecos = [d for d in ix["dias"] if d["tipo"] == "hueco"]
check("los huecos salen en el índice con su motivo",
      len(huecos) == 4 and all(h["motivo"] for h in huecos))
check("la avería se distingue en el índice",
      [h["clase"] for h in huecos].count("averia") == 1)
serie = {x["date"]: x["national"] for x in ix["tendencia"]}
check("un día sin foto va a null en la tendencia (no se interpola)",
      serie["2026-10-17"] is None and serie["2026-10-15"] is not None)

# --- El calendario no exige los días del apagón --------------------------
check("el calendario acaba el 23 de noviembre",
      cs.dias_esperados(datetime.fromisoformat(
          "2026-12-01T10:00:00+01:00").astimezone(MADRID))[-1]
      == date(2026, 11, 23))

shutil.rmtree(root, ignore_errors=True)
print(f"\n{check.fallos} fallos")
sys.exit(1 if check.fallos else 0)
