import os
import io
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

# Fungsi Generator PDF
def generate_pdf(messages, doc_name=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, spaceAfter=12)
    meta_style = ParagraphStyle('MetaStyle', parent=styles['Normal'], fontSize=10, textColor="gray", spaceAfter=18)
    user_style = ParagraphStyle('UserStyle', parent=styles['Normal'], fontSize=10, leading=14, spaceAfter=8)
    ai_style = ParagraphStyle('AIStyle', parent=styles['Normal'], fontSize=10, leading=14, spaceAfter=14)

    story = []
    story.append(Paragraph("<b>Riwayat Diskusi Socratic Mentor</b>", title_style))
    
    if doc_name:
        story.append(Paragraph(f"Dokumen Referensi: {doc_name}", meta_style))
    else:
        story.append(Paragraph("Dokumen Referensi: Tidak ada", meta_style))

    for msg in messages:
        role = "<b>[Pengguna]:</b>" if msg["role"] == "user" else "<b>[Socratic Mentor]:</b>"
        clean_text = msg["content"].replace("\n", "<br/>")
        
        if msg["role"] == "user":
            story.append(Paragraph(f"{role}<br/>{clean_text}", user_style))
        else:
            story.append(Paragraph(f"{role}<br/>{clean_text}", ai_style))
        
        story.append(Spacer(1, 6))

    doc.build(story)
    buffer.seek(0)
    return buffer

st.title("🧠 Private AI Discussion Space")
st.caption("Mitra berpikir kritis, Socratic Mentor & Pembahas Materi Kuliah.")

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Pengaturan AI")
    enable_web_search = st.toggle("🔍 Aktifkan Web Search", value=True)
    st.caption("Memungkinkan AI mencari info terbaru di internet.")
    
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

    # --- FITUR SIMPAN & DOWNLOAD PDF ---
    st.header("💾 Simpan Catatan (PDF/TXT)")
    if st.session_state.messages:
        # 1. Tombol Download PDF
        pdf_data = generate_pdf(st.session_state.messages, st.session_state.doc_name)
        st.download_button(
            label="📄 Unduh Catatan (.pdf)",
            data=pdf_data,
            file_name="catatan_diskusi_ai.pdf",
            mime="application/pdf"
        )

        # 2. Tombol Download TXT (Opsional)
        chat_export = "=== RIWAYAT DISKUSI SOCRATIC MENTOR ===\n\n"
        for msg in st.session_state.messages:
            role = "Pengguna" if msg["role"] == "user" else "Socratic Mentor"
            chat_export += f"[{role}]:\n{msg['content']}\n\n" + ("-"*40) + "\n\n"

        st.download_button(
            label="📝 Unduh Teks (.txt)",
            data=chat_export,
            file_name="riwayat_diskusi_ai.txt",
            mime="text/plain"
        )
        
        if st.button("🗑️ Hapus Semua Riwayat"):
            st.session_state.messages = []
            st.rerun()
    else:
        st.caption("Belum ada percakapan untuk diunduh.")

# System Instruction
SYSTEM_INSTRUCTION = """
Kamu adalah mitra diskusi intelektual dan Socratic Mentor pribadi untuk pengguna.
Tugas utama kamu BUKAN sekadar memberikan jawaban langsung atau mengiyakan pendapat pengguna.

Prinsip Utama Berperilaku:
1. Kritis & Analitis: Selalu cari celah, bias, atau asumsi yang belum teruji dari argumen pengguna.
2. Socratic Method: Sering-seringlah mengajukan pertanyaan balik yang memicu pemikiran lebih dalam.
3. Konstruktif: Tunjukkan di mana letak ketidaktepatan logikanya.
4. Verifikasi Data: Gunakan akses pencarian web jika memerlukan data/berita/fakta terbaru.
5. Gunakan bahasa Indonesia yang santai tapi berbobot dan lugas.
"""

# Tampilkan riwayat chat di UI
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input Teks Chat
if prompt := st.chat_input("Tulis argumen, ide, atau pertanyaanmu..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    formatted_contents = []

    if st.session_state.doc_context:
        formatted_contents.append(
            f"[SISTEM: Pengguna mengunggah dokumen '{st.session_state.doc_name}'].\n"
            f"Isi Dokumen:\n{st.session_state.doc_context}\n"
            f"--- GUNAKAN DOKUMEN DI ATAS SEBAGAI ACUAN UTAMA ---"
        )

    for msg in st.session_state.messages:
        prefix = "User: " if msg["role"] == "user" else "Assistant: "
        formatted_contents.append(prefix + msg["content"])

    tools = []
    if enable_web_search:
        tools.append(types.Tool(google_search=types.GoogleSearch()))

    with st.chat_message("assistant"):
        with st.spinner("Sedang menganalisis..."):
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
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                st.rerun()
            except Exception as e:
                st.error(f"Gagal memproses respon: {str(e)}")
