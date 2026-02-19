# Interpretacion sociologica automatica

- Generado: 2026-02-19T00:38:40.800717+00:00
- Fuente: data/derived/*

## Tesis
La red combina alta eficiencia operativa con alta concentracion estructural: coordina rapido, pero arriesga monocultura si no sostiene diversidad epistemica.

## Snapshot
- Posts=152,980, comentarios=704,450, submolts=3,430, autores=35,211, runs=27
- Ventana posts: 2026-01-28T00:00:49.827751+00:00 -> 2026-02-11T21:06:53.498583+00:00
- Ventana comentarios: 2026-01-28T01:48:37.645343+00:00 -> 2026-02-11T20:23:34.316802+00:00

## Indicadores clave
- Top 5 share: 44.4%
- Top 2% share: 78.6%
- Gini submolt: 0.944
- Infraestructura vs narrativa: 47.6% / 52.4%
- Cross-submolt post->comentario: 82.8%

## Modulos
### 1.1 Actividad y cobertura del snapshot
- Que es: Este bloque responde una pregunta simple: cuanta informacion real entra al analisis y en que fechas.
- Por que importa: Si no se entiende el tamano del snapshot, cualquier conclusion posterior puede sobredimensionarse o quedarse corta.
El snapshot actual incluye 152,980 posts, 704,450 comentarios, 3,430 submolts, 35,211 autores y 27 runs. Con este volumen ya se pueden observar regularidades estructurales, pero sigue siendo una foto temporal.
- Terminos clave:
  - Snapshot: foto de datos tomada en una ventana de tiempo especifica.
  - Run: una ejecucion de recoleccion del scraper.
  - Ventana temporal: fecha minima y maxima incluidas en el snapshot.
- Como leerlo:
  - Primero, verificar ventana de posts (2026-01-28T00:00:49.827751+00:00 -> 2026-02-11T21:06:53.498583+00:00, ~357.1 horas) y de comentarios (2026-01-28T01:48:37.645343+00:00 -> 2026-02-11T20:23:34.316802+00:00, ~354.6 horas).
  - Segundo, separar patrones estables (estructura) de picos puntuales (evento).
  - Tercero, antes de comparar con otro periodo, confirmar que la cobertura sea equivalente.
- Errores comunes:
  - Confundir snapshot con censo completo de la plataforma.
  - Asumir que mas volumen siempre significa mas diversidad.
- Lo que no significa:
  - No es censo total de la plataforma; es un corte temporal bajo reglas de captura.
  - No representa una poblacion general; representa este sistema en este periodo.
- Preguntas auditables:
  - Si repito el pipeline con este mismo snapshot, se conservan los agregados principales?
  - Si cambio la ventana temporal, que hallazgos se mantienen y cuales no?

### 1.2 Concentracion por submolt
- Que es: Mide cuanto del volumen total se acumula en pocas comunidades.
- Por que importa: Una red puede parecer grande por cantidad de submolts, pero seguir concentrada en pocos centros de atencion.
En este snapshot, el top 5 concentra 44.4% del volumen total y el top 2% concentra 78.6% (Gini=0.944). Esto describe una estructura con muchos espacios formales, pero con trafico muy desigual.
- Terminos clave:
  - Top 5 share: porcentaje del volumen total acumulado por las 5 comunidades mas grandes.
  - Top 2% share: porcentaje acumulado por el 2% superior de comunidades.
  - Gini: indicador de desigualdad (0 = muy distribuido, 1 = extremadamente concentrado).
- Como leerlo:
  - Si la curva acumulada sube muy rapido al inicio, la atencion esta centralizada.
  - Si el Gini sube entre snapshots, aumenta la concentracion estructural.
  - Comparar resultados en posts y comentarios por separado evita sesgo de una sola metrica.
- Errores comunes:
  - Tratar volumen como sinonimo de calidad o valor.
  - Leer concentracion como prueba automatica de manipulacion.
- Lo que no significa:
  - Volumen alto no equivale a calidad.
  - Concentracion no implica manipulacion por si sola.
- Preguntas auditables:
  - La concentracion se mantiene cuando se analiza solo comentarios?
  - El patron cambia significativamente al excluir 'general'?

### 1.3 Actividad por idioma
- Que es: Describe en que idiomas se publica y en que idiomas se responde.
- Por que importa: El idioma condiciona quien participa, quien responde y como se difunden las ideas entre comunidades.
Idioma dominante en posts: en (89.9%). Idioma dominante en comentarios: en (89.2%). La lectura de influencia cultural debe considerar este sesgo de idioma base.
- Terminos clave:
  - Share por idioma: proporcion relativa de documentos en cada idioma.
  - Posts vs comentarios: diferencia entre lenguaje de emision y lenguaje de reaccion.
  - Lingua franca: idioma dominante que permite coordinacion amplia.
- Como leerlo:
  - Comparar posts y comentarios permite ver si la conversacion se abre o se cierra linguisticamente.
  - Ocultar temporalmente el idioma dominante ayuda a ver estructuras que quedan ocultas.
  - Cruzar con transmision semantica permite evaluar si las ideas cruzan barreras de idioma.
- Errores comunes:
  - Confundir frecuencia de idioma con calidad argumental.
  - Asumir comprension intercultural solo por coexistencia de idiomas.
- Lo que no significa:
  - No mide calidad argumental.
  - No prueba comprension cruzada entre idiomas.
- Preguntas auditables:
  - Los marcos narrativos cruzan idiomas via embeddings o quedan encapsulados?

### 2.1 Memetica: infraestructura vs narrativa
- Que es: Separa memes de operacion tecnica de memes de significado cultural.
- Por que importa: Permite ver si el sistema esta mas enfocado en ejecutar (infraestructura) o en construir marcos de sentido (narrativa).
El balance actual es infraestructura=47.6% y narrativa=52.4%. Este mix muestra como la red combina coordinacion tecnica diaria con conversaciones de identidad, valores y sentido.
- Terminos clave:
  - Meme de infraestructura: patron tecnico repetido (api, tooling, stack).
  - Meme narrativo: patron de significado compartido (valores, identidad, relato).
  - Share memetico: peso relativo de cada familia de memes en el total observado.
- Como leerlo:
  - Si sube infraestructura, normalmente crece la coordinacion operativa.
  - Si sube narrativa, normalmente crece la disputa o consolidacion de marcos de sentido.
  - La comparacion entre snapshots muestra cambios de fase en la conversacion.
- Errores comunes:
  - Tratar infraestructura como ruido descartable.
  - Tratar narrativa como decoracion sin efectos practicos.
- Lo que no significa:
  - Infraestructura no es ruido: define acceso y gramatica de participacion.
  - Narrativa no es humo: coordina conducta cuando no hay manual.
- Preguntas auditables:
  - La narrativa es transversal o queda localizada en pocos submolts?

### 2.2 Vida, burst y dispersion memetica
- Que es: Combina tres lecturas: cuanto dura un meme, cuan brusco es su pico y cuantas comunidades alcanza.
- Por que importa: Distingue normas estables de eventos cortos y permite ver que memes funcionan como puentes entre comunidades.
En este corte: persistencia alta en 'looking forward' (349.0h), evento de mayor burst en 'looking forward' (score 107.0) y mayor dispersion en 'api v1' (2,229 submolts).
- Terminos clave:
  - Lifetime (vida): horas entre primera y ultima aparicion del meme.
  - Burst score: intensidad del pico de frecuencia en poco tiempo.
  - Dispersion: numero de submolts donde aparece el meme.
- Como leerlo:
  - Vida alta + burst bajo suele indicar una norma conversacional estable.
  - Burst alto + vida baja suele indicar un episodio coyuntural.
  - Dispersion alta sugiere capacidad de viajar entre comunidades.
- Errores comunes:
  - Confundir persistencia con veracidad del contenido.
  - Confundir burst con importancia estructural de largo plazo.
- Lo que no significa:
  - Vida no implica verdad; implica estabilidad de repeticion.
  - Burst no implica importancia estructural; implica sensibilidad a eventos.
- Preguntas auditables:
  - La dispersion de memes altos ocurre por hubs puntuales o por red distribuida?

### 3.1 Actos de habla y coordinacion
- Que es: Cuenta estilos de accion en el lenguaje: afirmar, preguntar, pedir, ofrecer, rechazar, etc.
- Por que importa: El tipo de acto dominante muestra como coordina la red: explorando, ejecutando, normando o negociando.
Se observa afirmacion=0.615/doc frente a pregunta=0.303/doc. Eso sugiere una dinamica mas orientada a enunciar y operar que a abrir preguntas.
- Terminos clave:
  - Acto de habla: funcion practica de una frase (afirmar, pedir, prometer, etc.).
  - Rate/doc: promedio de apariciones por documento.
  - Coordinacion conversacional: forma en que la red organiza accion a traves del lenguaje.
- Como leerlo:
  - Dominio de preguntas suele indicar fase de exploracion.
  - Dominio de afirmaciones/instrucciones suele indicar fase de ejecucion y estandarizacion.
  - Cambios fuertes entre submolts pueden revelar microculturas discursivas.
- Errores comunes:
  - Confundir estilo de habla con inteligencia o calidad total.
  - Suponer que un solo acto explica toda la cultura de la red.
- Lo que no significa:
  - No clasifica inteligencia de la red.
  - Describe estilo de coordinacion conversacional.
- Preguntas auditables:
  - Este perfil de actos es transversal o cambia fuerte por submolt?

### 3.2 Marcadores epistemicos
- Que es: Mide como se justifica lo dicho: evidencia, matiz/hedge, certeza, duda.
- Por que importa: Ayuda a distinguir una cultura de argumentacion auditable de una cultura de afirmacion cerrada.
En este snapshot: evidencia=0.122/doc, hedge=0.049/doc, certeza=0.009/doc. El balance sugiere presencia de justificacion, con baja declaracion absoluta.
- Terminos clave:
  - Evidencia: marcas linguisticas de justificacion o soporte.
  - Hedge: expresiones de atenuacion (posiblemente, podria, etc.).
  - Certeza: enunciados de cierre o seguridad fuerte.
- Como leerlo:
  - Mas evidencia y mas hedge suelen aumentar la auditabilidad del discurso.
  - Mas certeza absoluta puede indicar doctrina o estandar consolidado.
  - Cruzar con ejemplos textuales evita confundir forma retorica con calidad real.
- Errores comunes:
  - Asumir que mencionar evidencia equivale a evidencia de buena calidad.
  - Interpretar hedge como debilidad intelectual por defecto.
- Lo que no significa:
  - Mas 'evidencia' no implica mejor evidencia.
- Preguntas auditables:
  - Sube evidencia junto con fuentes verificables o solo como retorica?

### 3.3 Co-ocurrencia de conceptos
- Que es: Cuenta que conceptos aparecen juntos dentro de un mismo documento.
- Por que importa: Muestra paquetes narrativos: ideas que la red tiende a enlazar de forma recurrente.
Par dominante: agent + agents (60,277 co-ocurrencias). Estos pares recurrentes ayudan a mapear asociaciones estables en el discurso.
- Terminos clave:
  - Co-ocurrencia: presencia conjunta de dos conceptos en el mismo texto.
  - Par dominante: par con mayor frecuencia observada.
  - Paquete narrativo: conjunto de ideas que suelen viajar juntas.
- Como leerlo:
  - Pares estables suelen reflejar stack consolidado o marco ideologico repetido.
  - Pares con cambios bruscos entre snapshots suelen reflejar eventos o campanas.
  - Revisar variantes singular/plural evita sobreinterpretar artefactos linguisticos.
- Errores comunes:
  - Leer co-ocurrencia como causalidad directa.
  - Ignorar que pares muy frecuentes pueden venir de terminos nucleares del tema.
- Lo que no significa:
  - Co-ocurrencia no implica causalidad.
- Preguntas auditables:
  - Que pares cambian al excluir idioma dominante o submolt general?

### 3.4 Mapa ontologico (PCA 2D)
- Que es: Es una reduccion visual de muchos indicadores linguisticos a dos ejes para comparar submolts en un mismo plano.
- Por que importa: Permite ver rapidamente que comunidades hablan de forma parecida y cuales quedan alejadas del patron general.
El mapa proyecta 250 submolts (top por volumen). La razon p90/p50 de distancia es 3.03: cuanto mayor esta razon, mayor heterogeneidad entre periferia y nucleo. PCA no inventa variables nuevas de contenido; reordena combinaciones de actos, moods y marcadores epistemicos para hacer visible la estructura relativa.
- Terminos clave:
  - PCA: tecnica de reduccion de dimensionalidad que comprime muchas variables en pocos ejes.
  - Componente 1/2: combinaciones matematicas de variables originales, no categorias humanas directas.
  - Outlier: punto alejado del centro; puede indicar estilo propio o baja muestra.
- Como leerlo:
  - Paso 1: mirar cercania entre puntos (submolts cercanos suelen tener estilos similares).
  - Paso 2: mirar densidad de clusters (zonas compactas indican gramatica discursiva compartida).
  - Paso 3: revisar outliers con su doc_count para separar estilo real de ruido por baja actividad.
  - Paso 4: comparar con otro snapshot para ver si los grupos se mueven de forma estable o abrupta.
- Errores comunes:
  - Interpretar eje X o eje Y como si fueran etiquetas semanticas fijas.
  - Leer distancia corta como influencia causal directa entre submolts.
  - Concluir cambio cultural sin controlar cambios de muestra o filtros.
- Lo que no significa:
  - Los ejes no tienen significado semantico directo; son combinaciones de variables.
  - Cercania en el mapa no prueba causalidad ni coordinacion intencional.
- Preguntas auditables:
  - El mapa se mantiene estable entre snapshots con filtros equivalentes?
  - Los outliers siguen siendo outliers al exigir un minimo mayor de actividad?

### 4.1 Transmision por embeddings
- Que es: Mide similitud de significado entre textos, no solo coincidencia literal de palabras.
- Por que importa: Permite detectar eco semantico: cuando ideas parecidas circulan entre comunidades aunque cambie la redaccion.
Post-post mean=0.943 (cross=49.8%) y post->coment mean=0.906 (cross=82.8%). El cruce alto entre submolts sugiere difusion transversal de marcos semanticos.
- Terminos clave:
  - Embedding: vector numerico que representa significado aproximado de un texto.
  - Mean score: similitud promedio entre pares seleccionados.
  - Cross-submolt: porcentaje de pares que conecta comunidades distintas.
- Como leerlo:
  - Comparar post-post vs post->comentario muestra cuanto se conserva o transforma la idea al responder.
  - Cross alto sugiere circulacion entre comunidades; cross bajo sugiere encapsulamiento.
  - Validar cualitativamente ejemplos de score alto evita sobreinterpretar el numero.
- Errores comunes:
  - Tomar similitud alta como prueba de copia o plagio.
  - Inferir coordinacion intencional sin evidencia contextual adicional.
- Lo que no significa:
  - Similitud no implica coordinacion intencional.
  - El modulo detecta convergencia semantica, no plagio.
- Preguntas auditables:
  - Que tipo de pares domina en percentiles altos de similitud?

### 4.2 Sensibilidad por threshold
- Que es: Muestra como cambia la cantidad de matches cuando haces mas estricto o mas laxo el umbral de similitud.
- Por que importa: Evita elegir un threshold arbitrario sin mostrar el costo en falsos positivos o falsos negativos.
Con threshold 0.70 aparecen 764,731 pares; con 0.95 quedan 81,014 pares. El codo estimado en 0.93 (caida relativa 66.2%) marca una zona practica para balancear cobertura y precision.
- Terminos clave:
  - Threshold: minimo de similitud requerido para aceptar un match.
  - Recall: sensibilidad para capturar muchos casos (incluye mas ruido).
  - Precision: pureza de casos aceptados (pero puede perder variantes validas).
- Como leerlo:
  - Si al subir threshold la curva cae de golpe, la senal es fragil o muy heterogenea.
  - Si cae de forma gradual, la senal es mas robusta.
  - Usar la zona de codo como referencia y luego validar con muestras textuales.
- Errores comunes:
  - Buscar un threshold unico y universal para todos los contextos.
  - Elegir threshold solo por conveniencia narrativa.
- Lo que no significa:
  - No existe threshold universal correcto; depende del costo aceptable de error.
- Preguntas auditables:
  - Coinciden los ejemplos cualitativos con la zona de codo seleccionada?

### 4.3 TF-IDF vs embeddings (baseline)
- Que es: Compara dos tipos de similitud: lexical (palabras) y semantica (significado).
- Por que importa: Ayuda a distinguir copia literal de parafrasis o convergencia conceptual.
VSM/TF-IDF matched=0.137 vs shuffled=0.037, AUC=0.647, corr(emb,VSM)=0.582. La diferencia matched-shuffled confirma senal lexical por encima del azar; la correlacion parcial con embeddings indica que no todo match semantico depende de repetir las mismas palabras.
- Terminos clave:
  - TF-IDF o VSM: similitud basada en coincidencia de terminos.
  - AUC: capacidad de separar pares reales vs aleatorios (0.5 ~= azar).
  - Correlacion emb-VSM: cuanto se mueven juntas la similitud semantica y lexical.
- Como leerlo:
  - TF-IDF alto + embeddings alto suele ser repeticion fuerte o slogan.
  - TF-IDF bajo + embeddings alto suele indicar parafrasis.
  - TF-IDF alto + embeddings bajo puede ser choque de keywords con sentidos distintos.
- Errores comunes:
  - Confundir baseline con validacion final de causalidad.
  - Descartar la dimension semantica por enfocarse solo en keywords.
- Lo que no significa:
  - No es validacion final de verdad de transmision; es contraste lexical minimo.
- Preguntas auditables:
  - Que fraccion de matches fuertes depende de solape literal de tokens?

### 4.4 Muestras auditables de transmision
- Que es: Conjunto de ejemplos concretos para revisar manualmente si el match tiene sentido.
- Por que importa: Sin inspeccion humana, un score numerico puede sostener lecturas equivocadas.
Se publican 300 muestras para auditoria contextual. Estas muestras no reemplazan la estadistica global, pero permiten validar semantica, contexto e idioma caso por caso.
- Terminos clave:
  - Muestra auditable: subconjunto publicado para revision cualitativa.
  - Contexto: metadatos minimos (fecha, idioma, submolt, texto).
  - Validacion manual: lectura humana de coherencia semantica real.
- Como leerlo:
  - Revisar texto y metadatos juntos, no solo el score.
  - Buscar falsos positivos recurrentes y trazarlos a reglas/filtros.
  - Usar ejemplos de distintos rangos de score para calibrar umbral.
- Errores comunes:
  - Tomar la muestra como representacion exacta de todo el universo.
  - Aceptar score alto sin leer el contenido real.
- Lo que no significa:
  - Las muestras no son representativas del universo total; son auditables y pedagogicas.
- Preguntas auditables:
  - Los top score preservan coherencia semantica al leer texto completo?

### 5.1 Centralidad de red
- Que es: Describe como circula la atencion en la red: hubs, puentes y reciprocidad.
- Por que importa: Permite ver si la conversacion esta distribuida o depende de pocos nodos dominantes.
Reply graph con 6,377 nodos y 21,963 aristas; reciprocidad=3.6%, top 2% share=58.1%, Gini in-degree=0.855. El patron describe una red con hubs marcados y dialogo reciproco relativamente bajo.
- Terminos clave:
  - PageRank: indicador de centralidad por flujo de enlaces.
  - Betweenness: capacidad de un nodo para actuar como puente entre zonas.
  - Reciprocidad: proporcion de relaciones de ida y vuelta.
- Como leerlo:
  - PageRank alto sugiere concentracion de atencion.
  - Betweenness alto sugiere brokers que conectan comunidades.
  - Reciprocidad baja sugiere broadcasting por encima de conversacion bilateral.
- Errores comunes:
  - Confundir centralidad con razon, calidad o legitimidad.
  - Interpretar red estructural como red de influencia causal directa.
- Lo que no significa:
  - Centralidad no equivale a moralidad ni a calidad argumental.
- Preguntas auditables:
  - La estructura depende de pocos brokers o existen puentes distribuidos?

### 5.2 Autores activos y diversidad
- Que es: Cuantifica que parte de la actividad total esta en pocas cuentas versus distribuida en muchas.
- Por que importa: Complementa la lectura por submolt con una lectura por actores para detectar dependencia de pocos emisores.
Top 10 autores concentran 28.5% de la actividad total (Gini autores=0.897). Esto indica desigualdad relevante en participacion individual.
- Terminos clave:
  - Top 10 share autores: porcentaje de actividad acumulado por las 10 cuentas mas activas.
  - Gini de autores: desigualdad de actividad entre cuentas.
  - Actividad: suma de posts y comentarios por autor.
- Como leerlo:
  - Si top share sube, aumenta dependencia de pocos actores.
  - Cruzar con submolts permite distinguir autores locales de autores puente.
  - Comparar periodos ayuda a detectar rotacion o consolidacion de elites activas.
- Errores comunes:
  - Asumir que actividad alta equivale a influencia deliberativa real.
  - Confundir cuenta muy activa con representatividad del sistema.
- Lo que no significa:
  - Actividad alta no equivale a influencia deliberativa real.
- Preguntas auditables:
  - Aumentan los autores puente en eventos globales o en periodos normales?

### 6.1 Pipeline 01-04 y trazabilidad
- Que es: Resume la cadena completa: ingesta, normalizacion, derivados y visualizacion.
- Por que importa: Sin trazabilidad tecnica, la interpretacion sociologica queda en opinion no verificable.
La lectura sociologica solo es defendible si cada afirmacion puede rastrearse desde la UI hasta los archivos derivados y los scripts que la producen.
- Terminos clave:
  - Trazabilidad: capacidad de seguir un resultado hasta su fuente.
  - Derivado: archivo intermedio o final calculado desde datos crudos.
  - Reproducibilidad: posibilidad de obtener el mismo resultado con mismo pipeline y datos.
- Como leerlo:
  - Cada grafico debe tener ruta a su archivo fuente.
  - Cada metrica debe explicar filtro y transformacion aplicada.
  - Diferenciar observacion empirica de interpretacion narrativa.
- Errores comunes:
  - Asumir que reproducible significa libre de sesgo.
  - Presentar conclusion fuerte sin ruta de evidencia.
- Lo que no significa:
  - Pipeline reproducible no elimina sesgos de origen; los vuelve observables y debatibles.
- Preguntas auditables:
  - Cada claim publico tiene evidencia y archivo fuente verificable?

### 6.2 Contrato de metricas (claim matrix)
- Que es: Define reglas minimas para que una metrica pueda usarse como evidencia.
- Por que importa: Evita saltar de numero a conclusion sin declarar supuestos, limites y alcance inferencial.
Una metrica solo entra al argumento cuando tiene contrato: fuente, transformacion, filtros, limitaciones y pregunta que pretende responder.
- Terminos clave:
  - Claim matrix: tabla que vincula afirmaciones con evidencia y limites.
  - Alcance inferencial: hasta donde se puede concluir sin extrapolar de mas.
  - Limite metodologico: condicion que restringe interpretacion valida.
- Como leerlo:
  - Antes de usar un numero, verificar su definicion operacional.
  - Separar dato observado de interpretacion propuesta.
  - Explicitar que no puede responder cada metrica.
- Errores comunes:
  - Tratar la existencia de metrica como prueba automatica de causalidad.
  - Asumir que un contrato metodologico valida cualquier narrativa.
- Lo que no significa:
  - El contrato no legitima cualquier conclusion; solo delimita lectura valida y revisable.
- Preguntas auditables:
  - Claim matrix disponible: si (reports/audit/claim_matrix.csv).
