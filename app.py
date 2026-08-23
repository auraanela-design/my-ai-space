import os
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pypdf import PdfReader

# Load API Key (Mendukung lokal .env dan Streamlit Cloud Secrets)
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key and "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]

if not api_key:
    st.error("API Key belum ditemukan! Periksa file .env (lokal) atau Secrets (Streamlit Cloud).")
    st.stop()

client = genai.Client(api_key=api_key)

# Inisialisasi Session State untuk Dokumen
if "doc_context" not in st.session_state:
    st.session_state.doc_context = ""
if "doc_name" not in st.session_state:
    st.session_state.doc_name = None

# --- PANEL SAMPING (SIDEBAR) ---
with st.sidebar:
    st.header("⚙️ Pengaturan AI")
    # Tombol Toggle Web Search
    enable_web_search = st.toggle("🔍 Aktifkan Web Search", value=True)
    st.caption("Jika aktif, AI bisa mencari info/data terbaru di internet secara otomatis.")
    
    st.divider()
    
    # Upload File PDF
    st.header("📚 Materi Kuliah / Dokumen")
    uploaded_file = st.file_uploader("Unggah PDF untuk dibahas", type=["pdf"])
    
    if uploaded_file is not None:
        if st.session_state.doc_name != uploaded_file.name:
            with st.spinner("Membaca dan memproses PDF..."):
                reader = PdfReader(uploaded_file)
                extracted_text = ""
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        extracted_text += text + "\n"
                
                st.session_state.doc_context = extracted_text
                st.session_state.doc_name = uploaded_file.name
                st.success(f"Berhasil membaca: {uploaded_file.name}")
    
    if st.session_state.doc_name:
        st.info(f"📄 Dokumen aktif: **{st.session_state.doc_name}**")
        if st.button("❌ Hapus Dokumen"):
            st.session_state.doc_context = ""
            st.session_state.doc_name = None
            st.rerun()

# System Instruction dengan dukungan Konteks Dokumen
SYSTEM_INSTRUCTION = """
Kamu adalah mitra diskusi intelektual dan Socratic Mentor pribadi untuk pengguna.
Tugas utama kamu BUKAN sekadar memberikan jawaban langsung atau mengiyakan pendapat pengguna.

Prinsip Utama Berperilaku:
1. Kritis & Analitis: Selalu cari celah, bias, atau asumsi yang belum teruji dari argumen pengguna.
2. Socratic Method: Sering-seringlah mengajukan pertanyaan balik yang memicu pemikiran lebih dalam.
3. Konstruktif: Jangan asal menyalahkan, tapi tunjukkan di mana letak ketidaktepatan logikanya.
4. Jangan Mengekor: Jika pengguna salah atau logikanya lemah, jangan pernah berpura-pura setuju.
5. Pembahasan Dokumen: Jika pengguna mengunggah dokumen/materi kuliah, gunakan referensi teks dokumen tersebut untuk menguji pemahaman pengguna, mengkritisi kesimpulan mereka, atau mendiskusikan materi secara mendalam.
6. Gunakan bahasa Indonesia yang santai tapi berbobot dan lugas.
"""

# Menyimpan riwayat obrolan di sesi Streamlit
if "messages" not in st.session_state:
    st.session_state.messages = []

# Menampilkan riwayat obrolan yang sudah ada
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input teks dari pengguna
if prompt := st.chat_input("Tulis argumen, ide, atau pertanyaanmu di sini..."):
    # Tampilkan pesan pengguna di UI
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Format history untuk dikirim ke Gemini API
    contents = []
    
    # Jika ada dokumen PDF yang diunggah, masukkan konteksnya di bagian awal obrolan
    if st.session_state.doc_context:
        doc_prompt = (
            f"--- KONTEKS DOKUMEN / MATERI KULIAH ({st.session_state.doc_name}) ---\n"
            f"{st.session_state.doc_context[:30000]}\n"  # Batasi teks agar optimal
            f"----------------------------------------------------\n"
            f"Gunakan dokumen di atas sebagai rujukan utama saat menjawab atau menguji logika pengguna."
        )
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=doc_prompt)]
            )
        )
        contents.append(
            types.Content(
                role="model",
                parts=[types.Part.from_text(text=f"Saya telah membaca dokumen '{st.session_state.doc_name}'. Silakan ajukan pertanyaan atau pemahamanmu terkait materi ini untuk kita diskusikan.")]
            )
        )

    # Masukkan riwayat pesan
    for msg in st.session_state.messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(
            types.Content(
                role=role,
                parts=[types.Part.from_text(text=msg["content"])]
            )
        )

    # Konfigurasi Tools (Google Search Grounding)
    tools = []
    if enable_web_search:
        tools.append(types.Tool(google_search=types.GoogleSearch()))

    # Menghasilkan respon AI
    with st.chat_message("assistant"):
        with st.spinner("Sedang menganalisis materi & argumenmu..."):
            response = client.models.generate_content(
                model='gemini-1.5-flash',
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.7,
                    tools=tools
                )
            )
            st.markdown(response.text)
    
    # Simpan respon AI ke riwayat
