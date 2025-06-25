import os
import streamlit as st
from dotenv import load_dotenv
from anthropic import Anthropic
from utils.pdf_utils import pdf_to_images_and_text
from utils.xml_utils import read_xml_file


load_dotenv()
# api_key = os.getenv("ANTHROPIC_API_KEY")
api_key = st.secrets["API_KEY"]
client = Anthropic(api_key=api_key)

PROMPT = """
You are a powerful multimodal assistant with vision-language capabilities. Your goal is to:

1. **Parse the provided PDF** as an order/invoice document using BOTH:
   - The extracted text version (for accurate text content)
   - The image version (for layout and visual verification)
2. **Analyze the email text** that accompanies the PDF for additional information and context.
3. **Transform everything** into a single, well-formed XML that follows this exact schema:

**IMPORTANT**: 
- You must respond with ONLY the XML content. No explanations, no introductions, no markdown formatting - just pure XML starting with <?xml and ending with </XML_order>.
- When extracting product descriptions and technical details, cross-reference the text extraction with the visual image to ensure accuracy.
- If the text extraction and image show different values, prefer the one that makes more logical sense for technical products.

<?xml version="1.0" standalone="yes"?>
<XML_order documentsource="AIPDF" external_document_id="…"
           supplier="…">
  <orderheader sender_id="…"
               customer_ordernumber="…"
               orderdate="…"
               completedelivery="…"
               requested_deliverydate="…"
               recipientsreference="…">
    <Customer>
      <customerid>…</customerid>
    </Customer>
    <ShipTo>
      <adress>
        <name1>…</name1>
        <name2>…</name2>            <!-- optional -->
        <street>…</street>
        <postalcode>…</postalcode>
        <city>…</city>
        <country>…</country>
      </adress>
    </ShipTo>
    <ordertext>
      <textqualifier>ATT</textqualifier>
      <text>…</text>
    </ordertext>
    <ordertext>
      <textqualifier>CFD</textqualifier>
      <text>…</text>
    </ordertext>
  </orderheader>

  (For each line item:)
  <orderline>
    <linenumber>…</linenumber>
    <item_id tag="MF">…</item_id>
    <quantity unit="ST">…</quantity>
    <deliverydate>…</deliverydate>
    <price currency="EUR">…</price>
    <item_description>…</item_description>
    <!-- Optional: if special bid exists -->
    <orderlinetext>
      <textqualifier>BID</textqualifier>
      <text>…</text>
    </orderlinetext>
    <!-- Include if this is a dropship order or end-user info is available -->
    <orderline_info>
      <end-user_orderline_info>
        <end-user_orderline_name1>…</end-user_orderline_name1>
        <end-user_orderline_street>…</end-user_orderline_street>
        <end-user_orderline_postalcode>…</end-user_orderline_postalcode>
        <end-user_orderline_city>…</end-user_orderline_city>
        <end-user_orderline_country>…</end-user_orderline_country>
      </end-user_orderline_info>
    </orderline_info>
  </orderline>
</XML_order>

**Detailed instructions:**

1. **Extract "documentsource," "external_document_id," and "supplier"**  
   - These three attributes live on the root `<XML_order>`.  
   - **documentsource**: Always set to "AIPDF"
   - **external_document_id** and **customer_ordernumber**:  
     - Look for the order number in the PDF (often labeled as "Bestelnummer:", "Order number:", "P0031006" format)
     - Also check the email subject line for order numbers
     - Use the complete order number including any suffixes (e.g., `12345 6789-A`)
     - Use the same value for both `external_document_id` and `customer_ordernumber`
   - **supplier**:  
     - Check if Copaco country is mentioned in PDF or email
     - If Copaco The Netherlands/Nederland: use "COPACO"
     - If Copaco Belgium/België or "Copaco NV": use "6010"
     - If country not specified: use "NVT"

2. **Build the `<orderheader>` block**  
   - `sender_id`:  
     - ALWAYS set to "XXXXXXXXXX" (exactly 10 X characters)
     - This is a fixed value - do not look for or extract any other value
   - `customer_ordernumber`:  
     - Same as `external_document_id`
   - `orderdate`:  
     - Look for "Besteldatum:", "Order date:" in PDF
     - Convert to `DD-MM-YYYY` format
     - If not found: leave empty `orderdate=""`
   - `completedelivery`:  
     - Check for "Deliver Complete" checkbox or indicator
     - Map to "Y" or "N"
     - If not present: leave empty `completedelivery=""`
   - `requested_deliverydate`:  
     - Look for general delivery date (not line-specific)
     - Labels: "Leverdatum:", "Requested delivery date:"
     - Convert to `DD-MM-YYYY`
     - If not found: use "NVT"
   - `recipientsreference`:  
     - Look for "Referentie:", "Reference:" in PDF or email
     - Extract the COMPLETE reference including all parts
     - If reference contains "/" or multiple parts (e.g., "V0025488 / #PO594"), include EVERYTHING
     - Do NOT extract only the part after the slash
     - "Own use" is a valid reference - include it as-is if found
     - Also check for "T.a.v.: Name / RefCode" format in shipping address
     - If not found: leave empty

3. **Customer block**  
   - `<customerid>`: 
     - Look for customer ID/client number in PDF or email
     - May be a longer number (e.g., 10 digits like "0000001062")
     - If not found, leave empty

4. **ShipTo block**  
   - **CRITICAL**: Look for shipping address specifically marked as:
     - "Afleveradres:", "Shipping address:", "Leveringsadres:"
     - This can NEVER be Copaco's address
   - Extract:
     - `<name1>`: Company name or end customer name if dropship
     - `<name2>`: Contact person if present (e.g., from "T.a.v.:")
     - `<street>`: 
       - Parse from address EXACTLY as written
       - **IMPORTANT**: Preserve all accented characters correctly (è, é, ë, ï, etc.)
       - For example: "Sacrèstraat" NOT "Sacréstraat"
       - Cross-reference text extraction with visual image for correct accents
     - `<postalcode>`, `<city>`: Parse from address
     - `<country>`: Use 2-letter ISO code (deduce if not stated)

5. **Order text blocks**  
   - Always include both blocks, even if empty:
     1. `<textqualifier>ATT</textqualifier>`: 
        - Look for "Betreft", "Attachment", email filename references
        - If none found, leave `<text></text>` empty
     2. `<textqualifier>CFD</textqualifier>`: 
        - Look for CFD reference if exists
        - If none found, leave `<text></text>` empty
   - Note: These are DIFFERENT from BID - always include ATT and CFD blocks

6. **Order lines**  
   - Create `<orderline>` for each product (not fees/taxes)
   - **SKIP lines containing**:
     - "Thuiskopieheffing" (copying levy)
     - "Shipping costs" / "Verzendkosten"
     - "Transport" / "Cost for transport"
   - For each valid line:
     - `<linenumber>`: Sequential number (1, 2, 3...)
     - `<item_id tag="MF">`: 
       - Look for the product code in the "Code" column
       - Prioritize EAN code if present
       - Otherwise use SKU/Manufacturer code
       - MUST NOT contain spaces
       - Usually alphanumeric combination
     - `<quantity unit="ST">`: 
       - Look in the "Aantal" or "Quantity" column
       - Round to whole number
       - Search SPECIFICALLY in PDF
     - `<deliverydate>`: 
       - Use line-specific date if available
       - Otherwise use general delivery date from header
       - Format: `DD-MM-YYYY`
     - `<price currency="EUR">`: 
       - Use the unit price from "Prijs" or "Price" column (NOT the total/Bedrag)
       - Convert comma to dot (2.267,60 → 2267.60)
       - Search SPECIFICALLY in PDF
       - If not found: use "NVT"
     - `<item_description>`: 
       - Copy the product description EXACTLY as shown in the PDF
       - Pay special attention to technical specifications and model numbers
       - Common patterns include: manufacturer name, specifications (like "100G", "48P"), model codes
       - EXCLUDE supplementary info like "Based on:", "versie", version numbers that appear on separate lines
       - Only include the main product description line
       - Be especially careful with numbers and technical terms - double-check accuracy
       - Replace all `"` with `&quot;`
       - Do NOT add or modify any part of the description
     - **Special bid** (always include for each order line):
       ```xml
       <orderlinetext>
         <textqualifier>BID</textqualifier>
         <text>[bid_number or "NVT"]</text>
       </orderlinetext>
       ```
       - ONLY look for these EXACT keywords: "BID" or "PGO" (case insensitive)
       - Do NOT treat "BIDREF" as a bid - it is NOT a bid
       - The bid number usually follows these keywords
       - If "BID" or "PGO" found, use the actual bid number
       - If NEITHER "BID" nor "PGO" found, use "NVT" as the value
       - This block must be included for EVERY order line
       - Note: Special bid is always at order line level
     - **End-user info** (CRITICAL - only include if different from ShipTo):
       ```xml
       <orderline_info>
         <end-user_orderline_info>
           <end-user_orderline_name1>[end_customer_name]</end-user_orderline_name1>
           <end-user_orderline_street>[shipping_street]</end-user_orderline_street>
           <end-user_orderline_postalcode>[shipping_postalcode]</end-user_orderline_postalcode>
           <end-user_orderline_city>[shipping_city]</end-user_orderline_city>
           <end-user_orderline_country>[shipping_country]</end-user_orderline_country>
         </end-user_orderline_info>
       </orderline_info>
       ```
       - **CRITICAL**: Only include this block if end-user address is DIFFERENT from ShipTo address
       - If end-user address is the SAME as ShipTo address: OMIT this entire block
       - If no separate end-user information exists: OMIT this entire block
       - This is typically used for dropship scenarios where goods go to a different end customer
       - Note: Element names use underscores, not hyphens

7. **Additional checks from email**  
   - **Payment terms**: Look for payment conditions (e.g., "payment within X days")
   - **End customer**: For dropship orders, identify if different from reseller
   - **Special instructions**: Any shipping notes or special requirements

8. **Output Requirements**  
   - Single `<XML_order>…</XML_order>` block
   - No extra namespaces or comments
   - All dates in `DD-MM-YYYY` format
   - Empty tags allowed but not omitted
   - Well-formed XML with proper escaping

9. **Processing steps**  
   1. Parse PDF for all order data
   2. Analyze email text for additional context
   3. Cross-reference and validate information
   4. Apply all business rules (client number length, skip shipping lines, etc.)
   5. Output ONLY the final XML

**CRITICAL OUTPUT INSTRUCTION**: 
- You MUST output ONLY the XML content starting with <?xml and ending with </XML_order>
- DO NOT include any explanatory text before or after the XML
- DO NOT include phrases like "Looking at this PDF..." or "Let me extract..."
- DO NOT wrap the XML in markdown code blocks or backticks
- The response must be valid XML that can be directly parsed

**Key validations**:
- Reseller is NEVER Copaco
- Client number MUST be 4-6 digits or "NVT"
- Shipping address NEVER Copaco's address
- Unit prices use dots, not commas
- Quantities are whole numbers
- Part numbers have NO spaces
- Product descriptions must be extracted EXACTLY as shown - no modifications or interpretations
- Skip transport/shipping lines when creating orderlines
- End-user info ONLY included if different from ShipTo address - NEVER duplicate the same address

**Visual parsing tips**:
- Read carefully character by character for technical product descriptions
- Numbers like "100G" should not be confused with "6300F"
- Model codes often contain combinations of letters and numbers
- If text appears unclear, prefer the most logical technical specification
- **Accented characters**: Pay special attention to preserve correct accents (è vs é, ë vs e)
  - Common Dutch/Belgian street names often contain accents
  - Cross-check both text extraction and visual image for accurate accents
  - When in doubt, use the visual image to verify the correct accent mark
"""


def process(pdf_path, email_text=None):
    pdf_images, pdf_text = pdf_to_images_and_text(pdf_path)

    query = [{
        "type": "text",
        "text": "Please analyze the attached PDF. I'm providing it in two formats for better accuracy:\n1. As extracted text\n2. As images (visual representation)\n\nUse both sources to ensure accurate data extraction, especially for product descriptions and technical specifications."
    }, {
        "type": "text",
        "text": f"\n\n=== PDF TEXT CONTENT ===\n{pdf_text}\n=== END PDF TEXT ==="
    }, {
        "type": "text",
        "text": "\n\nNow here are the PDF pages as images:"
    }]

    for i, img_base64 in enumerate(pdf_images):
        query.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": img_base64
            }
        })

    if email_text:
        query.append({
            "type": "text",
            "text": f"\n\nAdditionally, here is the email text that accompanied this PDF order:\n\n{email_text}\n\nPlease analyze the email text for additional context and information (such as client numbers, references, special instructions, etc.) and incorporate relevant details into the final output according to the schema rules. Use both the PDF content (text and images) and email text to generate the most accurate XML. Output only the final <XML_order> document."
        })
    else:
        query.append({
            "type": "text",
            "text": " according to the schema rules. Note: No email text was provided, so extract all information from the PDF only (using both text and image representations). Output only the final <XML_order> document."
        })

    messages = [{"role": "user", "content": query}]

    response = client.messages.create(
        model="claude-sonnet-4-20250514",  # Using Claude 3.5 Sonnet for vision capabilities
        max_tokens=4000,
        temperature=0.0,
        system=PROMPT,
        messages=messages
    )

    xml_output = response.content[0].text
    return xml_output
