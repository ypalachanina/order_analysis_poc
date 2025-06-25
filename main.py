import streamlit as st
import tempfile
import os
from utils.streamlit_utils import load_local_image
from utils.llm_utils import process
from utils.xml_utils import validate_xml


def run_app():
    # copaco_url = "https://media.licdn.com/dms/image/v2/C4E0BAQGGuwM2e3st9Q/company-logo_200_200/company-logo_200_200/0/1631348100751?e=2147483647&v=beta&t=s6bk_3ocd1ivBhtPJq71M2WqM7rdrFItEmb_-BkXlRs"
    copaco_path = "icons/copaco.jpg"
    st.set_page_config(page_title="COPACO PoC", page_icon=load_local_image(copaco_path))
    st.title("📄 PDF & Email Processor")
    st.markdown("Upload your PDF file and optionally provide the email text to process them together.")
    with st.expander("ℹ️ How to use this app"):
        st.markdown("""
        **Steps to process your order:**

        1. **Upload PDF File** (Required): Click on the PDF upload area and select your order PDF file
        2. **Add Email Text** (Optional): Copy and paste the email text that accompanied the PDF order
        3. **Process Order**: Click the "Process Order" button to start processing
        4. **View Results**: Once processing is complete, you can view the generated XML content
        5. **Download**: Use the download button to save the processed XML file to your computer

        **⚠️ The output quality depends entirely on the content of your PDF and email text.**

        The system will generate XML in the required format, but accurate results depend on the presence of relevant data in your PDF and e-mail text.
        """)

    st.markdown("""
        <style>
        .bottom-right-image {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 999;
            max-width: 150px;
            opacity: 0.8;
        }
        </style>
        """, unsafe_allow_html=True)

    # sigli_url = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRCijvoF1p4iwmvrfKDuCslmJyYs5-EEfZ_dw&s"
    sigli_path = "icons/sigli.png"
    data_uri = load_local_image(sigli_path)

    if data_uri:
        st.markdown(f"""
        <div class="bottom-right-image">
            <img src="{data_uri}" style="width: 100%;">
        </div>
        """, unsafe_allow_html=True)

    if 'processed_xml' not in st.session_state:
        st.session_state.processed_xml = None
    if 'processing_complete' not in st.session_state:
        st.session_state.processing_complete = False
    if 'pdf_filename' not in st.session_state:
        st.session_state.pdf_filename = None

    st.sidebar.subheader("📎 PDF File (Required)")
    pdf_file = st.sidebar.file_uploader(
        "Choose a PDF file",
        type=['pdf'],
        help="Upload the PDF order file you want to process"
    )

    if pdf_file is not None:
        st.session_state.pdf_filename = pdf_file.name.removesuffix(".pdf")
        st.sidebar.success(f"✅ PDF uploaded: {pdf_file.name}")

    st.sidebar.subheader("📧 Email Text (Optional)")
    email_text = st.sidebar.text_area(
        "Paste email content here",
        height=200,
        placeholder="Example:\nFW: Inkooporder P0031006 / Own use //16971720\n\nBeste Copaco,\n\nHierbij onze order...\n\nKlantnummer: 111507\nReferentie: Own use",
        help="Copy and paste the email text that accompanied this PDF order."
    )

    if email_text and email_text.strip():
        st.sidebar.success(f"✅ Email text provided")

    process_disabled = pdf_file is None

    if st.button(
            "🚀 Process Order",
            disabled=process_disabled,
            help="Process the uploaded PDF and email text" if not process_disabled else "Upload a PDF file first"
    ):
        if pdf_file is not None:
            with st.spinner("Processing order... This may take a moment."):
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_pdf:
                        tmp_pdf.write(pdf_file.getvalue())
                        pdf_path = tmp_pdf.name

                    email_content = email_text.strip() if email_text else None
                    final_xml = process(pdf_path, email_content)

                    st.session_state.processed_xml = final_xml
                    st.session_state.processing_complete = True

                    os.unlink(pdf_path)

                    st.success("✅ Order processing completed successfully!")

                except Exception as e:
                    st.error(f"❌ Error during order processing: {str(e)}")
                    st.session_state.processing_complete = False

    if st.session_state.processing_complete:
        if st.session_state.processed_xml:
            is_valid = validate_xml(st.session_state.processed_xml)
            if is_valid:
                st.success("✅ Generated XML is valid!")
            else:
                st.warning("⚠️ Warning: Generated XML may not be well-formed")

        st.subheader("📄 Generated XML Output")
        with st.expander("View XML Content", expanded=False):
            st.text_area(
                "XML Output",
                value=st.session_state.processed_xml,
                height=300,
                label_visibility="collapsed"
            )

        st.subheader("💾 Download Results")
        download_file_name = f"{st.session_state.pdf_filename}_processed.xml"
        st.download_button(
            label="📥 Download XML File",
            data=st.session_state.processed_xml,
            file_name=download_file_name,
            mime="application/xml",
            help="Download the processed XML file"
        )


if __name__ == "__main__":
    run_app()
