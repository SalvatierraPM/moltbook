# Guia de interpretacion y explicacion sociológica

Este documento convierte métricas en lectura social auditable. La idea es pasar de "cuánto pasó" a "qué significa para la cultura de la red".

## 1) Actividad y cobertura del snapshot

### 1.1 Métricas globales (posts, comentarios, submolts, autores, runs, ventana temporal)
**Interpretacion extendida**  
No es metadata secundaria: es el marco de validez del observatorio. Define qué tan grande es el microscopio y qué tan grande es el objeto.

**Cómo leerlo (heuristicas concretas)**
- Ventana temporal corta: captura eventos. Ventana larga: captura habitos.
- Si sube el numero de submolts activos, sube el ancho cultural potencial.
- Mucho volumen con pocos autores: red más cercana a broadcasting que a conversación.
- Con multiples runs, revisar consistencia entre ejecuciones antes de inferir cambio cultural.

**Lo que NO significa**
- No es censo total; es snapshot bajo reglas de captura.
- No representa a "la humanidad"; representa un sistema especifico con sesgos explicitados.

**Pregunta auditable**
- Si repito el pipeline con el mismo snapshot, obtengo los mismos agregados?
- Si amplio o reduzco ventana temporal, qué patrones se sostienen?

### 1.2 Concentración: Top N submolts por volumen (curva acumulada / Gini)
**Interpretacion extendida**  
Responde si la red se comporta como "barrios" o como "mall": diversidad con peso real, o diversidad decorativa con concentración en pocos hubs.

**Cómo leerlo (lecturas condicionales)**
- Top 5 con porcion muy alta: oligopolio cultural de atención.
- Curva acumulada que sube rápido: hay muchas comunidades, pero pocas pesan.
- Gini creciente entre snapshots: centralización creciente del sistema.

**Mecanismos posibles**
- Diseno de feed/recomendación.
- Efecto reputacion (club historico).
- Barreras de entrada en comunidades pequenas.
- Atractores temáticos de alto volumen.

**Errores comunes**
- Volumen no equivale a calidad.
- Concentración no implica manipulación por si sola.

**Pregunta auditable**
- La concentración se mantiene al normalizar por tamaño de comunidad o al mirar solo comentarios?

### 1.3 Actividad por idioma (incluyendo filtros tipo ocultar inglés / ocultar general)
**Interpretacion extendida**  
Idioma es barrera cultural: dos grupos pueden compartir tema sin compartir memes o marcos.

**Cómo leerlo**
- Posts dominados por un idioma y comentarios mixtos: publicación global, debate local.
- Si al ocultar inglés cambia todo el mapa: sesgo fuerte de lingua franca.
- Idioma minoritario con alta densidad de comentarios: mayor cohesión comunitaria.

**Qué NO significa**
- No mide calidad argumental.
- No prueba comprension cruzada entre grupos.

**Pregunta auditable**
- Los marcos narrativos cruzan idioma por embeddings o quedan encapsulados?

## 2) Memética

### 2.1 Infraestructura vs narrativa (top infraestructura / top narrativa cultural)
**Interpretacion extendida**  
Separar lo que habilita hablar (infraestructura) de lo que decide hablarse (narrativa cultural).

**Lecturas concretas**
- Sube infraestructura: modo operacion (resolver, coordinar stack).
- Sube narrativa: modo significacion (identidad, filosofia, moral, promesa).
- Suben ambas: institucionalizacion cultural (jerga + mito).
- Baja narrativa y sube infraestructura: fase post-hype, más ejecución que predica.

**Errores comunes**
- Infraestructura no es "aburrida": define gatekeeping suave.
- Narrativa no es "humo": coordina conducta a escala.

**Pregunta auditable**
- Las piezas narrativas son transversales a submolts o locales?

### 2.2 Vida, burst y dispersion de n-grams (memes candidatos)
**Interpretacion extendida**  
Son tres exitos memeticos distintos:
1. Vida: persistencia (habito).
2. Burst: explosion (evento).
3. Dispersion: viaje (puente entre comunidades).

**Lecturas condicionales**
- Vida alta + burst bajo: norma estable.
- Burst alto + vida baja: episodio.
- Dispersion alta + frecuencia moderada: meme portatil.
- Frecuencia alta + dispersion baja: muletilla local.

**Texto anti-humo sugerido**
- Vida no equivale a verdad ni valor moral; equivale a estabilidad de repetición.
- Burst no equivale a importancia estructural; equivale a sensibilidad a eventos.

**Pregunta auditable**
- La dispersión está impulsada por 2-3 hubs o distribuida de forma orgánica?

## 3) Ontología del lenguaje

### 3.1 Actos de habla (pregunta, instruccion, afirmación, evaluacion, burla)
**Interpretacion extendida**  
Mide cómo coordina la red, no solo de qué tema habla.

**Lecturas concretas**
- Dominio de preguntas: exploración/aprendizaje.
- Dominio de instrucciones: modo tutorial e ingenieria.
- Dominio de afirmaciones fuertes: mayor doctrina/polarizacion.
- Dominio de evaluaciones/moralizacion: fase normativa.
- Dominio de burla/ironia: defensa identitaria y expulsion de outsiders.

**Qué NO significa**
- No clasifica inteligencia colectiva; clasifica estilo de coordinación.

**Pregunta auditable**
- Es transversal del sistema o cambia por submolt?

### 3.2 Marcadores epistémicos (certeza, duda, evidencia, condicionalidad)
**Interpretacion extendida**  
Mide cómo se negocia la verdad en la red.

**Lecturas condicionales**
- Sube certeza absoluta: más doctrina o estandar cerrado.
- Sube evidencia/condicionalidad: mayor auditabilidad argumentativa.
- Sube duda sin evidencia: ansiedad especulativa o hype sin modelo.

**Texto clave**
- Más "evidencia" no prueba que la evidencia sea buena; prueba que justificar es norma conversacional.

### 3.3 Co-ocurrencia de conceptos (pares)
**Interpretacion extendida**  
Revela paquetes narrativos: la red indica que conceptos "van juntos".

**Lecturas concretas**
- Pares muy estables: stack o ideologia consolidada.
- Pares en burst: evento o campana narrativa.
- Pares de un solo submolt: dialecto local.

**Error común**
- Co-ocurrencia no implica causalidad.

**Pregunta auditable**
- Qué pares cambian al excluir `general` o idioma dominante?

### 3.4 PCA 2D / mapa ontológico por submolt
**Interpretacion extendida**  
No representa geografia real; representa proximidad de estilos de coordinación.

**Lecturas condicionales**
- Cluster compacto: gramaticas similares.
- Outliers: submolts con otra logica o baja muestra.
- Reordenamientos fuertes entre snapshots: cambio cultural real o cambio de dataset/filtro.

**Texto recomendado**
- Los ejes no tienen significado humano directo; importa la proximidad relativa.
- Comunidades pequenas pueden ser inestables; aplicar minimo de actividad.

## 4) Transmisión (módulo delicado)

### 4.1 Resumen de embeddings (post-post / post->coment / cross-submolt)
**Interpretacion extendida**  
Mide eco semántico: propagacion por sentido, no solo por copia literal.

**Lecturas condicionales**
- Muchos matches + similitud alta: convergencia fuerte de marcos.
- Pocos matches + similitud alta: patrones potentes en nichos/hubs.
- Muchos matches + similitud moderada: ecos blandos de tema compartido.
- Cross-submolt alto: difusión transversal.
- Cross-submolt bajo: tribalizacion.

**Texto anti-malentendidos**
- Similitud no implica coordinación intencional.
- El módulo detecta convergencia, no plagio.

### 4.2 Sensibilidad por threshold
**Interpretacion extendida**  
Define cuan estricto eres para llamar "transmisión" a un match.

**Cómo leer la curva**
- Caida brusca al subir threshold: muchos matches ambiguos.
- Caida lenta: señal robusta bajo criterio estricto.
- Codo natural: paso de tema compartido a idea compartida.

**Texto de rigor**
- Publicar sensibilidad permite elegir tolerancia al falso positivo.
- Las muestras textuales validan cualitativamente cada rango.

### 4.3 TF-IDF vs embeddings (baseline)
**Interpretacion extendida**  
TF-IDF captura repetición lexical; embeddings capturan repetición semántica.

**Lecturas concretas**
- TF-IDF alto + embeddings alto: copia o slogan estable.
- TF-IDF bajo + embeddings alto: misma idea reescrita.
- TF-IDF alto + embeddings bajo: coincidencia de keywords con sentido distinto.

### 4.4 Tabla de muestras de transmisión
**Interpretacion extendida**  
Es el tribunal humano del módulo.

**Qué dejar explícito**
- Las muestras no son representativas; son auditables.
- Deben incluir texto y metadatos (submolt, fecha, idioma).

## 5) Red y autores

### 5.1 Centralidad (PageRank, betweenness, etc.)
**Interpretacion extendida**  
Mide estructura de circulación, no verdad ni calidad.

**Lecturas condicionales**
- Hubs dominantes + pocos brokers: alto agenda-setting.
- Muchos brokers medios: red más permeable.
- Reciprocidad baja: broadcasting/monologo.
- Reciprocidad alta: negociacion conversacional.

**Texto de proteccion metodologica**
- Centralidad no es moralidad; es topologia.
- Normalizar por volumen de autor para auditorias robustas.

### 5.2 Autores activos y diversidad
**Interpretacion extendida**  
Distingue motores locales (actividad concentrada) de viajeros (actividad distribuida).

**Lecturas concretas**
- Pocos viajeros: tendencia a tribalizacion.
- Picos de viajeros: eventos globales o controversias transversales.

## 6) Auditoría

### 6.1 Pipeline 01-04 (ingesta -> normalización -> derivados -> visualización)
**Interpretacion extendida**  
Es la constitucion del observatorio: no se pide confianza, se pide reproducibilidad.

**Qué explicar siempre**
- Cada etapa produce artefactos verificables.
- Cada gráfico debe enlazar a su derivado (CSV/JSON/Parquet).
- Sin trazabilidad, la interpretacion de sistemas memeticos se vuelve propaganda.

### 6.2 Contrato de métricas (claim matrix)
**Interpretacion extendida**  
Una métrica sin contrato no es evidencia.

**Contrato minimo**
- Fuente.
- Filtros.
- Transformaciones.
- Limitaciones.
- Pregunta que responde.

## Uso recomendado con reportes actuales
- Usar esta guia junto a `/Users/pabli/Desktop/Coding/Moltbook/reports/public_report.md`.
- Usar resumen ejecutivo de `/Users/pabli/Desktop/Coding/Moltbook/reports/interpretacion_sociologica.md` para público general.
- Respaldar cada afirmación con datasets de `/Users/pabli/Desktop/Coding/Moltbook/data/derived`.
