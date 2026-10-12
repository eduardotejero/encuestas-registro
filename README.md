# Registro público de pronósticos — generales del 29 de noviembre de 2026

Este repositorio contiene **una foto por día** del pronóstico de escaños que
publica el agregador, escrita automáticamente tras la ingesta diaria y
**nunca modificada después**. Existe para que, el 30 de noviembre, cualquiera
pueda comprobar qué se predijo y cuándo, sin tener que fiarse de nuestra base
de datos.

```
registro/AAAA/AAAA-MM-DD.json       la foto del día
registro/AAAA/AAAA-MM-DD.json.ots   su sello de tiempo OpenTimestamps
```

## Qué hay en cada foto

- `forecast`: el pronóstico tal como se publicó ese día: voto estimado,
  distribución de escaños (media de las simulaciones y reparto del voto
  central), probabilidad de cada bloque de llegar a 176, prueba de estrés,
  avisos y supuestos.
- `inputs`: **todas** las encuestas que entraron en la estimación (casa,
  fechas, muestra, cifras) y su hash (`inputs_sha256`).
- `source`: la revisión exacta de Wikipedia de la que se leyeron.
- `model_version`, `model_fingerprint_sha256`, `code_commit`: con qué
  código se calculó (ver más abajo).

## Tres pruebas de fecha, independientes

1. **El historial de este repositorio.** La fecha de un commit la pone quien
   lo escribe y se puede falsear; lo que no se puede falsear es que GitHub lo
   recibió en un repositorio público. Depende de GitHub.
2. **OpenTimestamps.** Cada `.json` lleva un `.json.ots` que ancla su hash en
   la cadena de bloques de Bitcoin. No depende de nadie. Para verificarlo:

   ```
   pip install opentimestamps-client
   ots verify registro/2026/2026-10-12.json.ots
   ```

   El sello se crea al publicar y se **completa** unas horas después, cuando
   el calendario se confirma en un bloque; la versión completada se comete
   aparte ("Prueba OpenTimestamps completada").
3. **El propio contenido.** `inputs_sha256` permite comprobar que las
   encuestas de entrada no se han tocado.

## Por qué el código está comprometido aunque todavía no sea público

Cada foto publica `model_fingerprint_sha256`: el sha256 del código del
modelo, de los datos editables que lo alimentan (perímetros de coalición) y de
la configuración que cambia cifras (`model_env`). La lista exacta de ficheros
hasheados va en `model_fingerprint_files`.

Eso es un **esquema de compromiso**: hoy nos obliga al código exacto que
produjo cada predicción, sin tener que enseñarlo todavía. Cuando se abra el
repositorio de código, cualquiera podrá hacer

```
git checkout <code_commit>
cd backend && python -m app.fingerprint
```

y comprobar que sale el mismo hash. Si alguien cambiara el código después
(para "acertar a posteriori"), dejaría de coincidir. Es más fuerte que
publicar el código: publicar el código prueba lo que hay hoy; el compromiso
prueba lo que había el día de cada predicción.

## El primer registro (12 de octubre) es más débil, y se queda así

El registro del 12-oct-2026 se escribió antes de que el formato incluyera el
hash completo: lleva sólo `model_fingerprint` (16 caracteres hexadecimales,
64 bits) y el `code_commit` del repositorio de código. Compromete menos que
los siguientes. **No se ha reemitido ni se reemitirá**: un registro que se
corrige cuando conviene no prueba nada.

## Lo que NO hay aquí, a propósito

- **Nada anterior al 12 de octubre de 2026.** El registro no se rellena
  hacia atrás, ni siquiera con días reconstruidos y etiquetados como tales.
- **Del 24 al 29 de noviembre no hay fotos.** El artículo 69.7 de la LOREG
  prohíbe publicar sondeos los cinco días anteriores a la votación, y un
  derivado de encuestas es un sondeo. El hueco es la ley, no un fallo.
- **Ninguna foto se reescribe.** Si algo hubiera que corregir, sería un
  fichero nuevo con su explicación, no una edición.

## Licencia

Los datos de encuestas proceden de Wikipedia (EN), «Opinion polling for the
2026 Spanish general election», bajo
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Los
resultados electorales son datos abiertos del Ministerio del Interior.
