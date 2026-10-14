import streamlit as st
from google import genai
from google.genai import types
import json
import time
import pypdf

st.set_page_config(page_title="Examen Interactivo de Biología Pro", page_icon="🧬", layout="centered")

st.title("🧬 Tutor Interactivo de Evaluación Secuencial")
st.write("Sube tus temas, evalúate paso a paso, lleva tu puntuación, controla tu tiempo y repasa tus fallos al final.")

# --- API KEY PRECONFIGURADA ---
API_KEY_PREDEFINIDA = "AQ.Ab8RN6LJHyZUEr9D2h9oCUdCdGvOkDrdeT-Cmq3Q95L-8KrZwA"

# Inicializar estados de la sesión
if "step" not in st.session_state:
    st.session_state.step = 1
if "contenido_temario" not in st.session_state:
    st.session_state.contenido_temario = None
if "puntuacion" not in st.session_state:
    st.session_state.puntuacion = 0
if "tiempo_inicio" not in st.session_state:
    st.session_state.tiempo_inicio = None
if "errores" not in st.session_state:
    st.session_state.errores = []

# Inicializar cliente automáticamente con tu clave
client = genai.Client(api_key=API_KEY_PREDEFINIDA)

# 1. Subida y lectura directa de texto (Evita la Files API y el error 401)
if st.session_state.contenido_temario is None:
    st.info("🔑 API Key cargada automáticamente. Sube tu temario para comenzar.")
    uploaded_file = st.file_uploader("Sube tu archivo de temario (PDF o TXT)", type=["pdf", "txt"])
    
    if uploaded_file is not None:
        with st.spinner("Leyendo y procesando documento..."):
            try:
                if uploaded_file.name.endswith(".txt"):
                    st.session_state.contenido_temario = uploaded_file.getvalue().decode("utf-8")
                else:
                    reader = pypdf.PdfReader(uploaded_file)
                    texto_extraido = ""
                    for page in reader.pages:
                        texto_extraido += page.extract_text() + "\n"
                    st.session_state.contenido_temario = texto_extraido
                
                st.success("¡Documento procesado correctamente!")
                st.rerun()
            except Exception as e:
                st.error(f"Error al leer el archivo: {e}")
else:
    # Barra lateral con estadísticas en tiempo real
    with st.sidebar:
        st.subheader("📊 Panel de Progreso")
        st.metric(label="Puntuación Actual", value=f"{st.session_state.puntuacion} aciertos")
        st.metric(label="Preguntas para Repasar", value=f"{len(st.session_state.errores)} errores")
        st.markdown("---")
        if st.button("🔄 Reiniciar / Cambiar temario"):
            st.session_state.clear()
            st.rerun()

    # Función auxiliar optimizada para enviar fragmentos clave de forma rápida
    def generar_preguntas_json(prompt_texto, num_preguntas):
        schema = {
            "type": "ARRAY",
            "description": "Lista de preguntas de examen",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "pregunta": {"type": "STRING", "description": "Enunciado de la pregunta"},
                    "opciones": {
                        "type": "ARRAY", 
                        "items": {"type": "STRING"},
                        "description": "Exactamente 4 opciones de respuesta"
                    },
                    "respuesta_correcta": {"type": "STRING", "description": "La opción exacta que es correcta"},
                    "explicacion": {"type": "STRING", "description": "Explicación breve de por qué es correcta"}
                },
                "required": ["pregunta", "opciones", "respuesta_correcta", "explicacion"]
            }
        }
        
        # Tomamos una porción optimizada del texto para que la respuesta sea instantánea
        texto_recortado = st.session_state.contenido_temario[:8000]
        
        prompt_completo = (
            f"Basándote en este contenido:\n{texto_recortado}\n\n"
            f"{prompt_texto} Genera exactamente {num_preguntas} preguntas."
        )
        
        for intento in range(2):
            try:
                response = client.models.generate_content(
                    model='gemini-3.5-flash-lite',
                    contents=prompt_completo,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=schema,
                        temperature=0.2
                    )
                )
                return json.loads(response.text)
            except Exception as e:
                if "503" in str(e) and intento < 1:
                    time.sleep(1)
                else:
                    st.error(f"Error al generar contenido: {e}")
                    return None
        return None

    num_preg = st.slider("Número de preguntas por fase de test:", min_value=3, max_value=8, value=4)

    # ==========================================
    # FASE 1: TEST MEDIO INTERACTIVO
    # ==========================================
    if st.session_state.step == 1:
        st.subheader("Fase 1: Test de Nivel Medio (Interactivo)")
        
        if "preguntas_medio" not in st.session_state:
            if st.button("🚀 Generar Test Medio Interactivo"):
                with st.spinner("Generando preguntas de nivel medio..."):
                    prompt = "Genera preguntas tipo test de nivel medio."
                    st.session_state.preguntas_medio = generar_preguntas_json(prompt, num_preg)
                    st.session_state.tiempo_inicio = time.time()
                    st.rerun()
        else:
            if st.session_state.tiempo_inicio:
                segundos = int(time.time() - st.session_state.tiempo_inicio)
                st.caption(f"⏱️ Tiempo transcurrido en esta fase: `{segundos} segundos`")

            preguntas = st.session_state.preguntas_medio
            if preguntas:
                for i, q in enumerate(preguntas):
                    st.markdown(f"**Pregunta {i+1}:** {q['pregunta']}")
                    
                    radio_key = f"medio_q_{i}"
                    seleccion = st.radio("Elige una opción:", q['opciones'], key=radio_key)
                    
                    estado_key = f"checked_medio_{i}"
                    if estado_key not in st.session_state:
                        st.session_state[estado_key] = False

                    if not st.session_state[estado_key]:
                        if st.button(f"Comprobar Pregunta {i+1}", key=f"btn_medio_{i}"):
                            st.session_state[estado_key] = True
                            if seleccion == q['respuesta_correcta']:
                                st.session_state.puntuacion += 1
                                st.success(f"¡Correcto! 🎉 {q['explicacion']}")
                            else:
                                st.error(f"Incorrecto. ❌ La respuesta correcta era: **{q['respuesta_correcta']}**.\n\n*Explicación:* {q['explicacion']}")
                                if q not in st.session_state.errores:
                                    st.session_state.errores.append(q)
                            st.rerun()
                    else:
                        if seleccion == q['respuesta_correcta']:
                            st.success(f"✔️ Ya respondida correctamente. {q['explicacion']}")
                        else:
                            st.error(f"❌ Respondida incorrectamente. La correcta era: **{q['respuesta_correcta']}**.")
                    st.markdown("---")
                
                if st.button("➡️ Avanzar al Test Difícil"):
                    st.session_state.step = 2
                    st.session_state.tiempo_inicio = time.time()
                    st.rerun()

    # ==========================================
    # FASE 2: TEST DIFÍCIL INTERACTIVO
    # ==========================================
    elif st.session_state.step == 2:
        st.subheader("Fase 2: Test de Nivel Difícil (Sin repetir conceptos)")
        
        if "preguntas_dificil" not in st.session_state:
            if st.button("🚀 Generar Test Difícil Interactivo"):
                with st.spinner("Generando preguntas de nivel avanzado sin repetir..."):
                    prompt = "Genera preguntas tipo test de nivel difícil, enfocadas en conceptos avanzados diferentes a los anteriores."
                    st.session_state.preguntas_dificil = generar_preguntas_json(prompt, num_preg)
                    st.rerun()
        else:
            if st.session_state.tiempo_inicio:
                segundos = int(time.time() - st.session_state.tiempo_inicio)
                st.caption(f"⏱️ Tiempo transcurrido en esta fase: `{segundos} segundos`")

            preguntas = st.session_state.preguntas_dificil
            if preguntas:
                for i, q in enumerate(preguntas):
                    st.markdown(f"**Pregunta Difícil {i+1}:** {q['pregunta']}")
                    radio_key = f"dificil_q_{i}"
                    seleccion = st.radio("Elige una opción:", q['opciones'], key=radio_key)
                    
                    estado_key = f"checked_dificil_{i}"
                    if estado_key not in st.session_state:
                        st.session_state[estado_key] = False

                    if not st.session_state[estado_key]:
                        if st.button(f"Comprobar Difícil {i+1}", key=f"btn_dificil_{i}"):
                            st.session_state[estado_key] = True
                            if seleccion == q['respuesta_correcta']:
                                st.session_state.puntuacion += 2
                                st.success(f"¡Excelente! 🎉 {q['explicacion']}")
                            else:
                                st.error(f"Incorrecto. ❌ La respuesta correcta era: **{q['respuesta_correcta']}**.\n\n*Explicación:* {q['explicacion']}")
                                if q not in st.session_state.errores:
                                    st.session_state.errores.append(q)
                            st.rerun()
                    else:
                        if seleccion == q['respuesta_correcta']:
                            st.success(f"✔️ Ya respondida correctamente. {q['explicacion']}")
                        else:
                            st.error(f"❌ Respondida incorrectamente. La correcta era: **{q['respuesta_correcta']}**.")
                    st.markdown("---")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("⬅️ Volver al Test Medio"):
                        st.session_state.step = 1
                        st.rerun()
                with col2:
                    if st.button("➡️ Pasar a Preguntas Cortas"):
                        st.session_state.step = 3
                        st.session_state.tiempo_inicio = time.time()
                        st.rerun()

    # ==========================================
    # FASE 3: PREGUNTAS CORTAS
    # ==========================================
    elif st.session_state.step == 3:
        st.subheader("Fase 3: Preguntas Cortas y Definiciones (Máx. 4 líneas)")
        
        if "preguntas_cortas" not in st.session_state:
            if st.button("🚀 Generar Preguntas Cortas"):
                prompt = (
                    "Genera preguntas cortas de definir o explicar conceptos clave del documento. "
                    "Proporciona una respuesta modelo muy breve que ocupe máximo 4 líneas."
                )
                schema_cortas = {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "pregunta": {"type": "STRING"},
                            "respuesta_modelo": {"type": "STRING", "description": "Respuesta breve de máximo 4 líneas"}
                        },
                        "required": ["pregunta", "respuesta_modelo"]
                    }
                }
                with st.spinner("Generando preguntas abiertas..."):
                    try:
                        prompt_completo = (
                            f"Basándote en el contenido:\n\n{st.session_state.contenido_temario[:8000]}\n\n"
                            f"{prompt}"
                        )
                        response = client.models.generate_content(
                            model='gemini-3.5-flash-lite',
                            contents=prompt_completo,
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json",
                                response_schema=schema_cortas,
                                temperature=0.2
                            )
                        )
                        st.session_state.preguntas_cortas = json.loads(response.text)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        else:
            if st.session_state.tiempo_inicio:
                segundos = int(time.time() - st.session_state.tiempo_inicio)
                st.caption(f"⏱️ Tiempo transcurrido en esta fase: `{segundos} segundos`")

            preguntas = st.session_state.preguntas_cortas
            if preguntas:
                for i, q in enumerate(preguntas):
                    st.markdown(f"**Pregunta Abierta {i+1}:** {q['pregunta']}")
                    st.text_area(f"Tu respuesta para la pregunta {i+1}:", key=f"resp_corta_{i}", placeholder="Escribe aquí tu definición en pocas líneas...")
                    
                    if st.button(f"Ver respuesta modelo {i+1}", key=f"btn_corta_{i}"):
                        st.info(f"💡 **Respuesta modelo (máx. 4 líneas):**\n\n{q['respuesta_modelo']}")
                    st.markdown("---")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("⬅️ Volver al Test Difícil"):
                        st.session_state.step = 2
                        st.rerun()
                with col2:
                    if st.button("➡️ Pasar al Test de Errores"):
                        st.session_state.step = 4
                        st.rerun()

    # ==========================================
    # FASE 4: TEST DE REPASO DE ERRORES
    # ==========================================
    elif st.session_state.step == 4:
        st.subheader("Fase 4: 🎯 Test de Repaso de Errores")
        
        if len(st.session_state.errores) == 0:
            st.success("🎉 ¡Increíble! No has cometido ningún error en los tests anteriores. ¡Tienes un pleno absoluto!")
        else:
            st.write(f"Aquí tienes las **{len(st.session_state.errores)} preguntas** que fallaste anteriormente:")
            
            for i, q in enumerate(st.session_state.errores):
                st.markdown(f"**Pregunta Fallada {i+1}:** {q['pregunta']}")
                
                radio_key = f"error_q_{i}"
                seleccion = st.radio("Elige una opción:", q['opciones'], key=radio_key)
                
                estado_key = f"checked_error_{i}"
                if estado_key not in st.session_state:
                    st.session_state[estado_key] = False

                if not st.session_state[estado_key]:
                    if st.button(f"Comprobar Repaso {i+1}", key=f"btn_error_{i}"):
                        st.session_state[estado_key] = True
                        if seleccion == q['respuesta_correcta']:
                            st.success(f"¡Muy bien rectificado! 🎉 {q['explicacion']}")
                        else:
                            st.error(f"Vaya, otra vez incorrecto. ❌ La respuesta correcta es: **{q['respuesta_correcta']}**.\n\n*Explicación:* {q['explicacion']}")
                        st.rerun()
                else:
                    if seleccion == q['respuesta_correcta']:
                        st.success(f"✔️ Corregido correctamente. {q['explicacion']}")
                    else:
                        st.error(f"❌ Fallado de nuevo. La correcta era: **{q['respuesta_correcta']}**.")
                st.markdown("---")
        
        if st.button("⬅️ Volver a Preguntas Cortas"):
            st.session_state.step = 3
            st.rerun()