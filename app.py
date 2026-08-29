import os
import io
import re
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pypdf import PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# Load API Key (Lokal .env & Streamlit Secrets)
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key and "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]

if not api_key:
    st.error("API Key belum ditemukan! Periksa file .env atau Secrets.")
    st.stop()

client = genai.Client(api_key=api_key)

# Config Halaman
st.set_page_config(page_title="Private AI Workspace", page_icon="🧠", layout="centered")

# Inisialisasi Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "doc_context" not in st.session_state:
    st.session_state.doc_context = ""
if "doc_name" not in st.session_state:
    st.session_state.doc_name = None

# Fungsi Generator PDF Kustom dari Teks Response
def create_pdf_from_text(title, content_text):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, spaceAfter=14)
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=10, leading=15, spaceAfter=8)

    story = []
    story.append(Paragraph(f"<b>{title}</b>", title_style))
    story.append(Spacer(1, 10))

    # Bersihkan markdown formatting sederhana agar rapi di PDF
    cleaned_lines = content_text.split("\n")
    for line in cleaned_lines:
        if not line.strip():
            story.append(Spacer(1, 6))
            continue
        
        # Konversi markdown bold **teks** ke HTML <b>teks</b>
        formatted_line = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', line)
        story.append(Paragraph(formatted_line, body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer

st.title("🧠 Private AI Discussion Space")
st.caption("Mitra berpikir kritis, Socratic Mentor & Generator Dokumen PDF.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Pengaturan AI")
    
    st.divider()
    
    st.header("📚 Materi Kuliah / PDF")
    uploaded_file = st.file_uploader("Unggah PDF materi", type=["pdf"])
    
    if uploaded_file is not None and st.session_state.doc_name != uploaded_file.name:
        with st.spinner("Membaca PDF..."):
            reader = PdfReader(uploaded_file)
            extracted_text = ""
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
            
            st.session_state.doc_context = extracted_text[:20000]
            st.session_state.doc_name = uploaded_file.name
            st.success(f"Berhasil membaca: {uploaded_file.name}")
    
    if st.session_state.doc_name:
        st.info(f"📄 Dokumen aktif: **{st.session_state.doc_name}**")
        if st.button("❌ Hapus Dokumen"):
            st.session_state.doc_context = ""
            st.session_state.doc_name = None
            st.rerun()

    st.divider()
    
    if st.button("🗑️ Hapus Riwayat Chat"):
        st.session_state.messages = []
        st.rerun()

# System Instruction
SYSTEM_INSTRUCTION = """
Kamu adalah mitra diskusi intelektual, Socratic Mentor, dan konsultan penyusun dokumen struktur/laporan.
Jika pengguna meminta kamu membuatkan materi, struktur, ringkasan, atau modul dalam bentuk PDF, buatlah penjelasan yang rapi, terstruktur (gunakan bullet points/nomor/penjelasannya jelas).

Prinsip Utama Berperilaku:
1. Kritis & Analitis: Berikan struktur ide yang logis dan runtut.
2. Responsif terhadap permintaan format: Susun materi dengan heading dan poin yang jelas agar mudah dikonversi menjadi PDF.
3. Gunakan bahasa Indonesia yang lugas dan profesional.
"""

# Tampilkan riwayat chat di UI
for idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Jika ada PDF payload di pesan assistant, munculkan tombol download khusus
        if message["role"] == "assistant" and "pdf_data" in message:
            st.download_button(
                label="📥 Unduh Jawaban Ini (.pdf)",
                data=message["pdf_data"],
                file_name=f"Dokumen_Struktur_{idx}.pdf",
                mime="application/pdf",
                key=f"btn_pdf_{idx}"
            )

# Input Teks Chat
if prompt := st.chat_input("Contoh: Buatkan aku struktur materi kuliah manajemen..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    formatted_contents = []

    if st.session_state.doc_context:
        formatted_contents.append(
            f"[SISTEM: Konteks Dokumen '{st.session_state.doc_name}']:\n{st.session_state.doc_context}\n---"
        )

    for msg in st.session_state.messages:
        prefix = "User: " if msg["role"] == "user" else "Assistant: "
        formatted_contents.append(prefix + msg["content"])

    tools = []
    if enable_web_search:
        tools.append(types.Tool(google_search=types.GoogleSearch()))

    with st.chat_message("assistant"):
        with st.spinner("Sedang menyusun respon & PDF..."):
            try:
                response = client.models.generate_content(
                    model='gemini-3.6-flash',
                    contents="\n\n".join(formatted_contents),
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        temperature=0.7,
                        tools=tools if tools else None
                    )
                )
                
                ai_text = response.text
                st.markdown(ai_text)
                
                # Cek apakah user meminta PDF dalam prompt-nya
                user_wants_pdf = any(kw in prompt.lower() for kw in ["pdf", "struktur", "download", "file", "unduh", "buatkan dokumen"])
                
                msg_payload = {"role": "assistant", "content": ai_text}
                
                # Jika terdeteksi minta PDF/struktur, buatkan filenya secara otomatis
                if user_wants_pdf:
                    pdf_file = create_pdf_from_text("Dokumen Hasil Diskusi / Struktur Materi", ai_text)
                    msg_payload["pdf_data"] = pdf_file.getvalue()
                    
                    st.download_button(
                        label="📥 Unduh Jawaban Ini (.pdf)",
                        data=pdf_file.getvalue(),
                        file_name="Dokumen_Struktur.pdf",
                        mime="application/pdf",
                        key=f"btn_pdf_{len(st.session_state.messages)}"
                    )

                st.session_state.messages.append(msg_payload)
                
            except Exception as e:
                st.error(f"Gagal memproses respon: {str(e)}")
