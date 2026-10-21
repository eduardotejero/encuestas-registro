# Registro público de pronósticos — generales del 29 de noviembre de 2026

Este repositorio contiene **una foto por día** del pronóstico de escaños que
publica el agregador, escrita automáticamente tras la ingesta diaria y
**nunca modificada después**. Existe para que, el 30 de noviembre, cualquiera
pueda comprobar qué se predijo y cuándo, sin tener que fiarse de nuestra base
de datos.

```
registro/AAAA/AAAA-MM-DD.json       la foto del día
registro/AAAA/AAAA-MM-DD.json.ots   su sello de tiempo OpenTimestamps
registro/AAAA/AAAA-MM-DD.hueco.json un día sin foto, declarado con su motivo
```

## Qué hay en cada foto

- `forecast`: el pronóstico tal como se publicó ese día: voto estimado,
  distribución de escaños (media de las simulaciones y reparto del voto
  central), probabilidad de cada bloque de llegar a 176, prueba de estrés,
  avisos y supuestos.
- `forecast.provinces` (desde el esquema 2, 13-oct-2026): por provincia y
  partido, la probabilidad de sacar al menos un escaño y los escaños
  esperados, de la misma simulación. Es lo que permite puntuar el 30-N
  provincia a provincia. Las fotos de esquema 1 no lo tienen y **no se
  reemiten**: esas fotos sólo se puntúan a escala nacional.
- `forecast.baselines.naive`: la línea base tonta del mismo día (media
  simple + swing uniforme), para compararla el 30-N sin recalcular nada.
- `inputs`: **todas** las encuestas que entraron en la estimación (casa,
  fechas, muestra, cifras) y su hash (`inputs_sha256`).
- `source`: la revisión exacta de Wikipedia de la que se leyeron.
- `model_version`, `model_fingerprint_sha256`, `code_commit`: con qué
  código se calculó (ver más abajo).

## Calendario operativo: cómo leer un día sin foto

- **Una foto al día**, a las **07:00 hora peninsular** (Europe/Madrid, con
  el cambio de hora incluido), del **12 de octubre al 23 de noviembre de
  2026**. Nada antes del 12 de octubre, nunca.
- **Del 24 al 29 de noviembre no hay fotos**: el artículo 69.7 de la LOREG
  prohíbe publicar sondeos los cinco días anteriores a la votación. Esos días
  no son huecos.
- **Cada foto se empuja a GitHub en cuanto se escribe** (en minutos). La
  hora del commit en GitHub es el sello de un tercero; el sello
  OpenTimestamps llega horas después, cuando el bloque de Bitcoin lo
  confirma. Si no hay red, el publicador reintenta cada 10 minutos sin
  perder el fichero.
- **Si la máquina estaba apagada o dormida a las 07:00**, la foto sale
  cuando vuelve, ese mismo día (su campo `generated_at_utc` y el commit lo
  dicen), y nunca con fecha de otro día.
- **Si un día termina sin foto, el publicador lo declara**: escribe
  `registro/AAAA/AAAA-MM-DD.hueco.json` con el motivo (por ejemplo, «host no
  disponible: ningún latido registrado») y lo comete aparte, con su propio
  sello. El motivo sale de los latidos del propio publicador: es lo que dice
  la máquina, no una prueba independiente.
- **Un vigía independiente del publicador** (`.github/workflows/vigia.yml`)
  comprueba cada mañana, desde GitHub y no desde la máquina que publica,
  que cada día exigible tenga foto o hueco declarado (el de hoy, a partir
  de las 09:00 hora peninsular). Si falta alguno, abre un issue con la
  etiqueta «vigía». Existe porque el 15-oct-2026 el publicador cayó y la
  caída no se detectó hasta el 21: la vigilancia vivía dentro del proceso
  caído. Los huecos del 16 al 21 de octubre se declararon ese día.
- **Un hueco no se rellena nunca.** No se publica una foto reconstruida a
  posteriori para un día pasado; el código se niega a hacerlo. Un hueco
  declarado se lee como hueco, no como selección: el día que el número
  hubiera sido incómodo no puede desaparecer en silencio, porque o hay foto
  o hay marcador con fecha propia.

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

### El compromiso exige que el código sea reproducible, y hasta el 21 de octubre no lo era

Un compromiso con el código sólo sirve si ese código, con las mismas entradas,
da las mismas cifras. Si no, nadie puede comprobar nada: volvería a ejecutarlo
y le saldrían otros números, sin saber si es por el modelo o por el azar.

**Las fotos del 12 al 15 de octubre de 2026 se calcularon con un modelo que no
era reproducible.** La simulación sorteaba un valor por bloque político
recorriendo un conjunto, y el orden en que Python recorre un conjunto de
cadenas cambia de una ejecución a otra: cada ejecución repartía los números
aleatorios de otra forma. El efecto medido sobre el error histórico del
modelo era de unas dos décimas de escaño.

Qué significa para esas cuatro fotos, dicho sin adornos:

- **el compromiso con el código sigue en pie**: la huella identifica el código
  exacto, y ese código es el que se ejecutó;
- **pero volver a ejecutarlo no reproduce la foto cifra a cifra**. Reproduce
  una foto del mismo modelo, con otro sorteo.

Se corrigió el 21 de octubre de 2026, en origen (orden fijo, no una semilla
que lo tapara), y ahora un test lo exige ejecutando el modelo en procesos
distintos y comparando. **Las cuatro fotos afectadas no se reemiten**, por la
misma razón que el registro del 12-oct: un registro que se corrige cuando
conviene no prueba nada. Queda escrito aquí, que es lo único honesto que se
puede hacer con ellas.

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
