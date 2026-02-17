# Interpretacion sociologica automatica

- Generado: 2026-02-17T21:26:22.901086+00:00
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
El marco de validez del observatorio es robusto: 152,980 posts, 704,450 comentarios, 3,430 submolts, 35,211 autores y 27 runs.
- Como leerlo:
  - Ventana temporal posts 2026-01-28T00:00:49.827751+00:00 -> 2026-02-11T21:06:53.498583+00:00 (~357.1 horas) y comentarios 2026-01-28T01:48:37.645343+00:00 -> 2026-02-11T20:23:34.316802+00:00 (~354.6 horas).
  - Diferenciar estructura (patrones estables) de evento (picos puntuales) segun el largo de la ventana.
  - Comparar snapshots por consistencia de agregados antes de inferir cambios culturales.
- Lo que no significa:
  - No es censo total de la plataforma; es snapshot bajo reglas de captura.
  - No representa una poblacion general; representa este sistema y este periodo.
- Preguntas auditables:
  - Si repito el pipeline con el mismo snapshot, se conservan estos agregados?
  - Si cambio la ventana temporal, que resultados se mantienen?

### 1.2 Concentracion por submolt
Top 5 submolts concentran 44.4% y top 2% concentran 78.6% (Gini=0.944). La red se organiza en pocos hubs de atencion.
- Como leerlo:
  - Curva acumulada alta al inicio implica diversidad formal con peso concentrado.
  - Si Gini sube entre snapshots, aumenta centralizacion estructural.
- Lo que no significa:
  - Volumen alto no equivale a calidad.
  - Concentracion no implica manipulacion por si sola.
- Preguntas auditables:
  - Se mantiene la concentracion al medir solo comentarios?
  - La concentracion cambia al excluir 'general'?

### 1.3 Actividad por idioma
Idioma dominante en posts: en (89.9%). Idioma dominante en comentarios: en (89.2%).
- Como leerlo:
  - Si posts son mas monolingues y comentarios mas mixtos, hay publicacion global y debate local.
  - Ocultar ingles permite estimar cuanto depende la lectura publica de la lingua franca.
- Lo que no significa:
  - No mide calidad argumental.
  - No prueba comprension cruzada entre idiomas.
- Preguntas auditables:
  - Los marcos narrativos cruzan idioma via embeddings o quedan encapsulados?

### 2.1 Memetica: infraestructura vs narrativa
Infraestructura=47.6% y narrativa=52.4%. La mezcla describe el modo del sistema (operacion, significacion o institucionalizacion).
- Como leerlo:
  - Suba de infraestructura sugiere foco operativo (coordinar stack, ejecutar).
  - Suba de narrativa sugiere foco de sentido (identidad, valores, marcos).
- Lo que no significa:
  - Infraestructura no es ruido: define acceso y gramatica de participacion.
  - Narrativa no es humo: coordina conducta cuando no hay manual.
- Preguntas auditables:
  - La narrativa es transversal o queda localizada en pocos submolts?

### 2.2 Vida, burst y dispersion memetica
Persistencia: 'looking forward' (349.0h). Evento: 'looking forward' (burst 107.0). Viaje: 'api v1' (2,229 submolts).
- Como leerlo:
  - Vida alta + burst bajo suele indicar norma estable.
  - Burst alto + vida baja suele indicar episodio.
  - Dispersion alta marca memes puente entre comunidades.
- Lo que no significa:
  - Vida no implica verdad; implica estabilidad de repeticion.
  - Burst no implica importancia estructural; implica sensibilidad a eventos.
- Preguntas auditables:
  - La dispersion esta concentrada en hubs o distribuida de forma organica?

### 3.1 Actos de habla y coordinacion
Afirmacion=0.615/doc vs pregunta=0.303/doc. La red tiende a coordinar por enunciados afirmativos mas que por indagacion.
- Como leerlo:
  - Dominio de preguntas: exploracion.
  - Dominio de instrucciones/afirmaciones: ejecucion y estandarizacion.
  - Evaluacion/moralizacion alta: fase normativa.
- Lo que no significa:
  - No clasifica inteligencia de la red.
  - Describe estilo de coordinacion conversacional.
- Preguntas auditables:
  - Este perfil es transversal o varía por submolt?

### 3.2 Marcadores epistemicos
Evidencia=0.122/doc, hedge=0.049/doc, certeza=0.009/doc.
- Como leerlo:
  - Mas evidencia/condicionalidad suele indicar mejor auditabilidad argumentativa.
  - Mas certeza absoluta puede indicar cierre doctrinal o estandar consolidado.
  - Duda sin evidencia puede indicar especulacion ansiosa.
- Lo que no significa:
  - Mas 'evidencia' no implica mejor evidencia.
- Preguntas auditables:
  - Sube evidencia junto con fuentes verificables o solo como retorica?

### 3.3 Co-ocurrencia de conceptos
Par dominante: agent + agents (60,277). Esto sugiere paquetes narrativos estables en el discurso.
- Como leerlo:
  - Pares estables suelen reflejar stack o ideologia consolidada.
  - Pares con burst suelen reflejar eventos o campanas narrativas.
- Lo que no significa:
  - Co-ocurrencia no implica causalidad.
- Preguntas auditables:
  - Que pares cambian al excluir idioma dominante o submolt general?

### 3.4 Mapa ontologico (PCA 2D)
Mapa sobre 250 submolts top; razon p90/p50 de distancia=3.03.
- Como leerlo:
  - Cercania en el mapa implica estilos de coordinacion similares.
  - Outliers pueden indicar dialecto local o baja muestra.
- Lo que no significa:
  - Los ejes no tienen significado semantico directo.
- Preguntas auditables:
  - El mapa se mantiene estable entre snapshots con filtros equivalentes?

### 4.1 Transmision por embeddings
Post-post mean=0.943 (cross=49.8%); post->coment mean=0.906 (cross=82.8%).
- Como leerlo:
  - Cross-submolt alto sugiere marcos que viajan entre comunidades.
  - Diferencia post-post vs post->comentario sugiere cuanto eco se conserva en respuesta.
- Lo que no significa:
  - Similitud no implica coordinacion intencional.
  - El modulo detecta convergencia, no plagio.
- Preguntas auditables:
  - Que tipo de pares domina en los percentiles altos de similitud?

### 4.2 Sensibilidad por threshold
Threshold 0.70: 764,731 pares; 0.95: 81,014 pares. Codo estimado en 0.93 (drop relativo 66.2%).
- Como leerlo:
  - Threshold bajo prioriza recall y agrega ruido.
  - Threshold alto prioriza precision y pierde parafrasis suaves.
  - La pendiente de caida informa robustez de la senal.
- Lo que no significa:
  - No existe threshold universal correcto; depende de tolerancia a falsos positivos.
- Preguntas auditables:
  - Coinciden los ejemplos cualitativos con la zona de codo elegida?

### 4.3 TF-IDF vs embeddings (baseline)
VSM matched=0.137 vs shuffled=0.037; AUC=0.647; corr(emb,VSM)=0.582.
- Como leerlo:
  - TF-IDF alto + embeddings alto: repeticion lexical fuerte.
  - TF-IDF bajo + embeddings alto: parafrasis o eco semantico.
- Lo que no significa:
  - No es evaluacion final de verdad de transmision; es baseline de contraste lexical.
- Preguntas auditables:
  - Que fraccion de matches fuertes depende de solape literal de tokens?

### 4.4 Muestras auditables de transmision
Se publican 300 muestras para inspeccion humana contextual.
- Como leerlo:
  - Usar metadatos (fecha, idioma, submolt) para validar la lectura de cada match.
- Lo que no significa:
  - Las muestras no son representativas del universo; son auditables.
- Preguntas auditables:
  - Las muestras de top score preservan coherencia semantica al leer texto completo?

### 5.1 Centralidad de red
Reply graph: 6,377 nodos, 21,963 aristas, reciprocidad=3.6%, top 2% share=58.1%, Gini in-degree=0.855.
- Como leerlo:
  - PageRank alto indica hubs de atencion.
  - Betweenness alto indica brokers entre tribus.
  - Reciprocidad baja sugiere broadcasting mas que dialogo.
- Lo que no significa:
  - Centralidad no equivale a moralidad ni a calidad argumental.
- Preguntas auditables:
  - La estructura depende de pocos brokers o hay puentes distribuidos?

### 5.2 Autores activos y diversidad
Top 10 autores concentran 28.5% de la actividad total (Gini autores=0.897).
- Como leerlo:
  - Motores locales: alta actividad en pocos submolts.
  - Viajeros: actividad distribuida y potencial puente cultural.
- Lo que no significa:
  - Actividad alta no equivale a influencia deliberativa real.
- Preguntas auditables:
  - Aumentan los viajeros en eventos globales o en periodos normales?

### 6.1 Pipeline 01-04 y trazabilidad
La lectura sociologica se apoya en una cadena auditable: ingesta -> normalizacion -> derivados -> visualizacion.
- Como leerlo:
  - Cada grafico debe trazar a un derivado concreto.
  - Sin trazabilidad, la interpretacion memetica se vuelve opinion no falsable.
- Lo que no significa:
  - Pipeline reproducible no elimina sesgos de origen; los hace observables.
- Preguntas auditables:
  - Cada claim publico tiene evidencia y archivo fuente verificable?

### 6.2 Contrato de metricas (claim matrix)
Una metrica sin contrato no es evidencia: requiere fuente, filtros, transformaciones, limites y pregunta respondida.
- Como leerlo:
  - Usar claim matrix para diferenciar dato observado de inferencia interpretativa.
- Lo que no significa:
  - El contrato no legitima cualquier conclusion; delimita alcance inferencial.
- Preguntas auditables:
  - Claim matrix disponible: si (reports/audit/claim_matrix.csv).
