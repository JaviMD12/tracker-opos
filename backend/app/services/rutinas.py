"""Catalogo de rutinas del Plan Pro, una por cada prueba fisica.

Contenido estructural de referencia: los textos y la bibliografia son
placeholders razonables (basados en literatura real de fuerza y
acondicionamiento) pensados para validar el flujo Free -> Pro. Antes de
publicar en produccion deben revisarse por un preparador fisico y sustituirse
por citas exactas (edicion, año, paginas).
"""

RUTINAS_PRO = {
    "dominadas": {
        "titulo": "Dominadas Estrictas: Fuerza Neural y Sobrecarga Excéntrica",
        "descripcion_cientifica": "La dominada estricta es un ejercicio de cadena cinética cerrada que evalúa la fuerza relativa del hemicuerpo superior[cite: 1110]. El paradigma de la fase excéntrica y las contracciones de alargamiento juegan un papel fundamental[cite: 1125]. El entrenamiento de alta frecuencia refuerza el engrama motor sin fatiga central, un concepto conocido como 'engrasar el surco'[cite: 1132].",
        "entrenamiento_semanal": [
            {
                "fase": "Fase 1: Activación y Reducción del Déficit Bilateral",
                "intensidad": "Media",
                "volumen": "3 series x 8-10 reps",
                "detalle": "Jalón unilateral y Ghost Rows para reducir el déficit bilateral[cite: 1135].",
                "fundamento": "El déficit bilateral hace que la fuerza sumada de ambos brazos por separado supere la fuerza aplicada de forma bilateral; el trabajo unilateral mejora el reclutamiento neuromuscular de cada lado antes de exigir el gesto completo.",
            },
            {
                "fase": "Fase 2: Sobrecarga Excéntrica (Tempo Negatives)",
                "intensidad": "Alta",
                "volumen": "3-6 series x 3-5 reps",
                "detalle": "Dominadas excéntricas con 5-7 segundos de descenso controlado y 10s de separación entre repeticiones[cite: 1135].",
                "fundamento": "El músculo genera más tensión mecánica en fase excéntrica que en concéntrica con menor coste metabólico, lo que permite sobrecargar el patrón de tracción aunque todavía no se puedan completar dominadas estrictas.",
            },
            {
                "fase": "Fase 3: Frecuencia Neural Submáxima",
                "intensidad": "Media (60-70% esfuerzo)",
                "volumen": "4-5 días/semana x 1-3 reps",
                "detalle": "Dominadas estrictas submáximas sin llegar al fallo, para reforzar el engrama motor ('engrasar el surco')[cite: 1135].",
                "fundamento": "Repetir el gesto motor con alta frecuencia y baja fatiga refuerza las vías neurales específicas del movimiento (aprendizaje motor) sin acumular fatiga central que comprometa la siguiente sesión.",
            },
        ],
        "bibliografia": "Estudios de electromiografía de superficie (EMG)[cite: 1114]; Principios de hipertrofia excéntrica y daño sarcomérico[cite: 1127].",
    },
    "sprint_100m": {
        "titulo": "Sprint 100m: Perfil F-V y Potencia Aláctica",
        "descripcion_cientifica": "La velocidad máxima se alcanza aplicando fuerzas masivas contra el suelo en tiempos de contacto inferiores a 0.09 segundos[cite: 1145]. Para optimizar el perfil Fuerza-Velocidad (F-V), la ciencia actual prescribe el uso de Sprints Resistidos con cargas pesadas[cite: 1148, 1168].",
        "entrenamiento_semanal": [
            {
                "fase": "Aceleración: Sprints Resistidos Pesados (RST)",
                "intensidad": "Alta (25-50% Vdec)",
                "volumen": "4-6 series x 15-30m",
                "detalle": "Cargas que generen un 25-50% de decremento de velocidad (Vdec)[cite: 1169, 1176].",
                "fundamento": "El sprint resistido obliga a aplicar mayor fuerza horizontal contra el suelo en cada apoyo, el mismo vector dominante en la fase de aceleración, mejorando la producción de fuerza específica sin alterar la mecánica de carrera.",
            },
            {
                "fase": "Velocidad Máxima: Sprints Lanzados (Flying Sprints)",
                "intensidad": "Máxima (>98%)",
                "volumen": "3-5 series",
                "detalle": "Carrera de impulso previa seguida de una zona de vuelo de 10-30m a máxima velocidad[cite: 1176].",
                "fundamento": "Entrar ya lanzado a la zona de máxima velocidad expone al sistema neuromuscular a la frecuencia y amplitud de zancada reales de la velocidad punta, el estímulo clave para mejorar el techo de velocidad.",
            },
            {
                "fase": "Resistencia a la Velocidad (Speed Endurance)",
                "intensidad": "Submáxima (90-95%)",
                "volumen": "3-6 series x 60-100m",
                "detalle": "Con 2-4 minutos de descanso completo entre repeticiones[cite: 1176].",
                "fundamento": "Mantener el 90-95% de la velocidad durante más metros entrena la capacidad de tamponar el ácido láctico y sostener la técnica bajo fatiga, lo que determina el tiempo final más que la velocidad punta aislada.",
            },
        ],
        "bibliografia": "Investigaciones biomecánicas de Ralph Mann y Peter Weyand[cite: 1144]; Modelado del perfil F-V por J.B. Morin y P. Samozino[cite: 1149].",
    },
    "carrera_1500m": {
        "titulo": "1500m: Economía de Carrera y Potencia Aeróbica",
        "descripcion_cientifica": "El 1500m es una prueba híbrida con una demanda oxidativa del 77% al 86%[cite: 1185]. Para optimizar la Economía de Carrera (RE), se implementa Entrenamiento Concurrente de Fuerza Máxima (MST), lo que ahorra glucógeno sin hipertrofia[cite: 1189, 1194].",
        "entrenamiento_semanal": [
            {
                "fase": "Fuerza Concurrente (MST)",
                "intensidad": "Alta (>85% 1RM)",
                "volumen": "4 series x 4-5 reps",
                "detalle": "Media sentadilla y peso muerto para aumentar la rigidez tendinosa y mejorar la economía de carrera[cite: 1190, 1205].",
                "fundamento": "El entrenamiento de fuerza máxima aumenta la rigidez músculo-tendinosa, lo que mejora el ciclo estiramiento-acortamiento y reduce el coste energético de cada zancada sin necesidad de añadir volumen aeróbico.",
            },
            {
                "fase": "Potencia Aeróbica (Método Eurofit 15:15)",
                "intensidad": "120% de la Velocidad Aeróbica Máxima (MAS)",
                "volumen": "2-3 series x 5-10 min",
                "detalle": "15 segundos corriendo al 120% de la MAS, 15 segundos de descanso pasivo[cite: 1202, 1205].",
                "fundamento": "Trabajar por encima del 100% de la MAS en intervalos cortos permite acumular más tiempo total a intensidades que elevan el VO2max que una carrera continua al mismo ritmo, gracias a la recuperación parcial entre picos.",
            },
            {
                "fase": "Capacidad Aeróbica (Grids)",
                "intensidad": "Alterna 100% / 70% MAS",
                "volumen": "Cuadrículas continuas de 8-10 min",
                "detalle": "Bloques continuos alternando 100% y 70% de la MAS[cite: 1205].",
                "fundamento": "Alternar intensidades sin parar mantiene elevada la demanda cardiovascular durante más tiempo, ampliando la base aeróbica sobre la que se apoyan las series de mayor intensidad.",
            },
        ],
        "bibliografia": "Investigación seminal de Storen et al. (2008) sobre fuerza en corredores[cite: 1190]; Protocolos HIIT de Veronique Billat y Martin Buchheit[cite: 1201].",
    },
    "natacion_100m": {
        "titulo": "Natación 100m: Eficiencia Propulsiva y USRPT",
        "descripcion_cientifica": "La hidrodinámica dictamina que la eficiencia propulsiva es crítica[cite: 1210]. El paradigma moderno rechaza el kilometraje vacío y adopta el Ultra-Short Race-Pace Training (USRPT), entrenando estrictamente al ritmo objetivo de la competición[cite: 1236, 1239].",
        "entrenamiento_semanal": [
            {
                "fase": "Acondicionamiento USRPT",
                "intensidad": "Ritmo objetivo de 100m (race-pace)",
                "volumen": "20-30 reps x 25m",
                "detalle": "Descanso pasivo riguroso de 15-20 segundos entre repeticiones[cite: 1245].",
                "fundamento": "Nadar exactamente al ritmo objetivo de competición entrena el sistema neuromuscular y metabólico en las condiciones reales de la prueba, en vez de adaptaciones genéricas de resistencia que no siempre transfieren al ritmo de carrera.",
            },
            {
                "fase": "Regulación de Fallo (Failure Rule)",
                "intensidad": "Ritmo objetivo estricto",
                "volumen": "Series completas con control de tiempo",
                "detalle": "Si se excede el tiempo objetivo, se detiene la serie por 1 repetición; un segundo fallo cancela el set[cite: 1245].",
                "fundamento": "Detener la serie al fallar el ritmo evita que el nadador practique un patrón de fatiga o una técnica degradada, justo lo que se quiere eliminar de la prueba real.",
            },
            {
                "fase": "Transiciones y Viraje",
                "intensidad": "Máxima",
                "volumen": "5-8 llegadas",
                "detalle": "Virajes a máxima intensidad simulando hipoxia (sin respirar)[cite: 1245].",
                "fundamento": "El viraje y la salida son los únicos momentos donde se puede ganar velocidad sin gasto energético muscular adicional (impulso en la pared), por lo que su optimización tiene un retorno desproporcionado en una prueba tan corta.",
            },
        ],
        "bibliografia": "Sistema MAD (Measuring Active Drag) de Huub M. Toussaint[cite: 1221]; Protocolo USRPT de Brent Rushall[cite: 1236].",
    },
}


TECNICAS_ESTUDIO_PRO = {
    "recuerdo_activo": {
        "nombre": "Recuerdo Activo (Active Recall)",
        "concepto_cientifico": (
            "Recuperar informacion desde la memoria fortalece la huella mnesica mucho mas "
            "que releer o subrayar (efecto de testeo o 'testing effect'). Es el esfuerzo de "
            "recuperacion, no la exposicion pasiva al texto, lo que consolida el aprendizaje "
            "a largo plazo."
        ),
        "paso_a_paso": [
            "Cierra el manual o los apuntes antes de intentar recordar.",
            "Escribe o di en voz alta todo lo que recuerdes sobre el tema, sin mirar el material.",
            "Compara lo recordado con el texto original y marca los huecos.",
            "Repite el ejercicio solo sobre esos huecos, no sobre todo el tema otra vez.",
        ],
        "ejemplo_aplicado": (
            "Tras leer el tema de la Ley de Gestion de Emergencias de Andalucia, cierra el PDF "
            "y escribe en una hoja en blanco todos los plazos y organos competentes que "
            "recuerdes (por ejemplo, quien declara la emergencia y en que plazo se activa el "
            "Plan Territorial). Corrige despues con el texto legal y repite solo los plazos "
            "que fallaste."
        ),
    },
    "repeticion_espaciada": {
        "nombre": "Repeticion Espaciada (Spaced Repetition)",
        "concepto_cientifico": (
            "La curva del olvido de Ebbinghaus muestra que la informacion se pierde rapido "
            "tras el primer estudio. Repasar justo antes de olvidarla, en intervalos "
            "crecientes, consolida la memoria a largo plazo con mucho menos tiempo total que "
            "repasar todo por igual."
        ),
        "paso_a_paso": [
            "Programa el primer repaso de un tema a las 24 horas de estudiarlo.",
            "Si lo recuerdas bien, dobla el intervalo hasta el siguiente repaso (3 dias, 7 dias, 15 dias...).",
            "Si fallas un repaso, vuelve a un intervalo corto (1 dia) solo para ese contenido.",
            "Usa un sistema de tarjetas (fisico o app) para no depender de la memoria para saber que toca repasar.",
        ],
        "ejemplo_aplicado": (
            "Crea una tarjeta por cada parametro hidraulico clave (caudal, presion, perdida de "
            "carga por friccion). Repasalas a las 24h, luego a los 3 y a los 7 dias; los "
            "parametros que confundas mas (por ejemplo, la formula de Hazen-Williams) vuelven "
            "a intervalo corto hasta que los domines."
        ),
    },
    "tecnica_feynman": {
        "nombre": "Técnica Feynman",
        "concepto_cientifico": (
            "Explicar un concepto con palabras sencillas, como si se enseñara a alguien sin "
            "conocimientos previos, obliga a detectar las lagunas de comprension que pasan "
            "desapercibidas cuando solo reconoces el concepto al leerlo (ilusion de "
            "competencia)."
        ),
        "paso_a_paso": [
            "Elige un concepto y escribe su explicacion como si se la contaras a alguien de 12 años.",
            "Evita la jerga tecnica; si la usas, tienes que explicarla tambien en palabras simples.",
            "Cuando te atasques o uses una palabra que no sabes justificar, marca ese punto como laguna.",
            "Vuelve al material original solo para cerrar esa laguna, y reescribe la explicacion.",
        ],
        "ejemplo_aplicado": (
            "Intenta explicar por que el agua apaga un incendio de clase A sin usar la palabra "
            "'refrigeracion': tendras que describir que el agua absorbe calor al evaporarse y "
            "baja la temperatura del combustible por debajo del punto de ignicion. Si no "
            "consigues explicarlo sin el termino tecnico, es que aun no dominas el concepto de "
            "transmision de calor."
        ),
    },
    "practica_intercalada": {
        "nombre": "Práctica Intercalada (Interleaving)",
        "concepto_cientifico": (
            "Alternar distintos tipos de contenido en una misma sesion, en vez de practicar en "
            "bloques del mismo tema, obliga al cerebro a identificar que estrategia aplicar en "
            "cada caso. Esto mejora la capacidad de discriminacion y la transferencia a "
            "examenes con preguntas mezcladas."
        ),
        "paso_a_paso": [
            "Divide la sesion de estudio en bloques cortos de temas distintos (legislacion, fisica del fuego, primeros auxilios...).",
            "Alterna entre ellos cada 20-30 minutos en vez de agotar un tema entero antes de pasar al siguiente.",
            "Al hacer tests, mezcla preguntas de varios temas en vez de encadenar 20 preguntas del mismo bloque.",
            "Acepta que la sesion se sienta 'menos fluida': esa dificultad deseable es la que genera el aprendizaje real.",
        ],
        "ejemplo_aplicado": (
            "En una sesion de 90 minutos, dedica 30 min a plazos de la Ley de Gestion de "
            "Emergencias de Andalucia, 30 min a calculo de perdida de carga en mangueras y 30 "
            "min a fases del fuego. Esto entrena la misma habilidad que necesitaras en el "
            "examen real: reconocer de que tema es cada pregunta sin que vengan ordenadas por "
            "bloques."
        ),
    },
}
