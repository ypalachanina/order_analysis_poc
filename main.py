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
    st.title("📄 PDF & XML Processor")
    st.markdown("Upload your PDF file and optionally an XML file to process them together.")
    with st.expander("ℹ️ How to use this app"):
        st.markdown("""
        **Steps to process your files:**

        1. **Upload PDF File** (Required): Click on the PDF upload area and select your PDF file
        2. **Upload XML File** (Optional): If you have an XML file to process alongside the PDF, upload it in the second area
        3. **Process Files**: Click the "Process Files" button to start LLM processing
        4. **View Results**: Once processing is complete, you can view the generated XML content
        5. **Download**: Use the download button to save the processed XML file to your computer

        **Notes:**
        - Only PDF files are accepted for the main upload
        - XML files are optional and should be valid XML format
        - Processing time may vary depending on file size and complexity
        
        **⚠️ The output is entirely based on the content of the files you upload.**
        
        The LLM will attempt to generate XML that matches the required format, but accurate results depend on the presence of relevant data in your PDF and (optional) XML files.
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
        help="Upload the PDF file you want to process"
    )

    if pdf_file is not None:
        st.session_state.pdf_filename = pdf_file.name.removesuffix(".pdf")
        st.sidebar.success(f"✅ PDF uploaded: {pdf_file.name}")

    st.sidebar.subheader("📎 XML File (Optional)")
    xml_file = st.sidebar.file_uploader(
        "Choose an XML file",
        type=['xml'],
        help="Optionally upload an XML file to process alongside the PDF"
    )

    if xml_file is not None:
        st.sidebar.success(f"✅ XML uploaded: {xml_file.name}")

    process_disabled = pdf_file is None

    if st.button(
            "🚀 Process Files",
            disabled=process_disabled,
            help="Process the uploaded PDF and XML files using LLM" if not process_disabled else "Upload a PDF file first"
    ):
        if pdf_file is not None:
            with st.spinner("Processing files with LLM... This may take a moment."):
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_pdf:
                        tmp_pdf.write(pdf_file.getvalue())
                        pdf_path = tmp_pdf.name

                    xml_path = None
                    if xml_file is not None:
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.xml') as tmp_xml:
                            tmp_xml.write(xml_file.getvalue())
                            xml_path = tmp_xml.name

                    final_xml = process(pdf_path, xml_path)

                    st.session_state.processed_xml = final_xml
                    st.session_state.processing_complete = True

                    os.unlink(pdf_path)
                    if xml_path:
                        os.unlink(xml_path)

                    st.success("✅ LLM processing completed successfully!")

                except Exception as e:
                    st.error(f"❌ Error during LLM processing: {str(e)}")
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
