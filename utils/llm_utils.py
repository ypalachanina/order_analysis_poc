import os
from dotenv import load_dotenv
from anthropic import Anthropic
from utils.pdf_utils import pdf_to_images
from utils.xml_utils import read_xml_file


load_dotenv()
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


PROMPT = """
You are a powerful multimodal assistant with vision-language capabilities. Your goal is to:

1. **Parse the provided PDF** as an order/invoice document.
2. **Optionally**: If a secondary internal XML file (with a different formatting/field-naming) is supplied at the same time, also parse that and merge any overlapping or complementary information.
3. **Transform everything** into a single, well-formed XML that follows this exact schema:

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
    <!-- Optional: if the secondary XML provides "orderline_info", include that subblock exactly as shown: -->
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

**Detailed instructions (modified to fix previous mapping errors):**

1. **Extract "documentsource," "external_document_id," and "supplier"**  
   - These three attributes live on the root `<XML_order>`.  
   - **external_document_id** and **customer_ordernumber**:  
     - Look for the line beginning with “Bestelnummer:” in the PDF.  
     - Use the entire string that follows “Bestelnummer:” (e.g. `12345 6789-A`) for both `external_document_id` and `customer_ordernumber`.  
     - Do NOT split by space or hyphen: include the full suffix (e.g. `–R`).  
   - **supplier**:  
     - Look for the heading “Inkooporder voor:” (usually immediately above or beside the buyer name).  
     - If it is related to Copaco, always write it as COPACO with capital letters.

2. **Build the `<orderheader>` block**  
   - `sender_id`:  
     - Look for labels such as “Sender ID,” “ERP Code,” or “Vendor code.”  
     - If the PDF does not explicitly list one, leave `sender_id=""`.  
   - `customer_ordernumber`:  
     - As noted above, use the same value as `external_document_id` (the full “Bestelnummer” string).  
   - `orderdate`:  
     - Look for labels such as “Besteldatum:” (e.g. `16-05-25`) and convert to `DD-MM-YYYY`.
     - If the PDF does not explicitly list one, leave `orderdate=""`.   
   - `completedelivery`:  
     - If the PDF has a checkbox or text “Deliver Complete” with a Y/N marker, map that to either `"Y"` or `"N"`.  
     - If not explicitly present, set `completedelivery=""`.  
   - `requested_deliverydate`:  
     - Find “Leverdatum:” or “Requested delivery date:” and convert to `DD-MM-YYYY`.  
     - (E.g. PDF shows `19-05-25` → output `19-05-2025`.)  
   - `recipientsreference`:  
     - Look in the “Afleveradres:” block for a “T.a.v.: <Name> / <RefCode>” line.  
     - After the slash (`/`), extract the numeric reference (e.g. `01443196`).  
     - If no slash-based reference exists, leave `recipientsreference=""`.

3. **Customer block**  
   - Always output `<Customer><customerid>…</customerid></Customer>`.  
   - If the PDF lists a “Customer ID,” “Account #,” or “Sold-To ID” (for example, a numeric code under the company header), use that value.  
   - If there is no clear “Customer ID” label, leave `<customerid></customerid>` empty.

4. **ShipTo block**  
   - Under `<ShipTo><adress>…</adress></ShipTo>`, extract as follows:  
     - `<name1>`: find the “Afleveradres:” label and take the next line as the company name (e.g. `Baas Groep BV`).  
     - `<name2>` (optional): if the PDF has “T.a.v.: <ContactName>” before a slash, put `<ContactName>` here (e.g. `Bart Maatman`). If no “T.a.v.” line, leave `<name2></name2>`.  
     - `<street>`, `<postalcode>`, `<city>`, `<country>`:  
       - From the address block under “Afleveradres,” parse each component exactly.  
       - If the country is not mentioned, find out what it is based on the address. Note down the country in the 2-letter ISO 3166-1 format.
     - **Example** (from PDF):  
       ```
       Afleveradres:
         Baas Groep BV
         T.a.v.: Bart Maatman / 01443196
         Essebaan 71
         2908 LJ Capelle aan den IJssel
         NL
       ```
       - → `<name1>Baas Groep BV</name1>`  
       - → `<name2>Bart Maatman</name2>`  
       - → `<street>Essebaan 71</street>`  
       - → `<postalcode>2908 LJ</postalcode>`  
       - → `<city>Capelle aan den IJssel</city>`  
       - → `<country>NL</country>`

5. **Order text qualifiers**  
   - Always produce exactly two `<ordertext>` elements:  
     1. `<textqualifier>ATT</textqualifier>`  
        - Look for any “Betreft” or “Attachment” reference in the PDF.  
        - If no “Betreft” or explicit attachment name exists, leave the `<text></text>` empty.  
     2. `<textqualifier>CFD</textqualifier>`  
        - Look for any “CFD” reference in the PDF.  
        - If no “CFD” exists, leave the `<text></text>` empty.  

6. **Order lines**  
   - For each line item in the PDF that is **not** a purely-fee/tax line, produce one `<orderline>` block.  
   - **Skip** any line whose part number or description includes the word “Thuiskopieheffing” (this is a copying levy fee, not a ship-to product).  
   - Inside each `<orderline>`:  
     - `<linenumber>`: Use the visible sequence number in the PDF for that product (1, 2, 3… counting only non-fee lines).  
     - `<item_id tag="MF">`: Take the “Your art. code” or “Part #” exactly (e.g. `A37XGET#ABH` or `CN31`).  
     - `<quantity unit="ST">`: Use the “Aantal”/“Qty” field. Always put `unit="ST"`.  
     - `<deliverydate>`: Use the “Leverdatum” for that line
     - `<price currency="EUR">`: Use the unit price (e.g. `765,14` → `765.14`).  
       - If the PDF shows a price with a comma, replace with a dot.  
       - Do not include the line-total; only the unit price.  
     - `<item_description>`: Copy the textual description (e.g. `HP ProBook 460 G11 / 16" WUXGA U5 16GB RAM 512GB SSD W11Pro`).  
       - **Important**: Replace every double-quote (`"`) with `&quot;` so it is well-formed XML.  
     - **BID info**:  
       - If the PDF has a “Betreft OPG <value>” line, create an `<orderlinetext>` subblock:  
         ```xml
         <orderlinetext>
           <textqualifier>BID</textqualifier>
           <text><value></text>
         </orderlinetext>
         ```  
         - Use the same `<value>` (e.g. `46116464`) under every `<orderlinetext>` for all non-fee lines.  
       - If there is no “Betreft” line, omit the `<orderlinetext>` block entirely.

7. **Merging with Secondary XML (if present)**  
   - If the request also attaches a differently formatted XML file (for example, tagged `<PurchaseOrder>` or some custom schema), parse it and look for any of these fields: “Order Number,” “Customer ID,” “Ship-To Info,” “Line Items,” etc.  
   - If a field is found both in PDF and in the secondary XML, prefer the PDF’s value (unless it is blank/empty).  
   - If a field is only in the secondary XML (e.g. `sender_id` or a full company code), inject it into the corresponding place in the new structure.  
   - For line-item matching, use either the `<linenumber>` or the part number (`item_id`) to align PDF-extracted lines with secondary-XML `<line>` entries.  
   - If the secondary XML provides a `<Customer><customerid>` value, use that instead of leaving the PDF-based `<customerid>` empty.

8. **Output Requirements**  
   - Produce exactly one `<XML_order>…</XML_order>` block.  
   - Do **not** add any extra namespaces, processing instructions, or comments.  
   - Preserve the ordering: root attributes first, then `<orderheader>`, then `<Customer>`, then `<ShipTo>`, then both `<ordertext>` blocks, then each `<orderline>` (including any `<orderlinetext>`).  
   - Ensure every opened tag is closed, use double quotes around every attribute, and all dates are in `DD-MM-YYYY` format.  
   - If a particular field cannot be extracted from **either** the PDF or the secondary XML, leave it empty (e.g. `orderdate=""` or `<street></street>`), but do not omit the tag or attribute itself.  

9. **Final Instruction**  
   - First, run your VLM parsing routine on the PDF to extract all fields according to the rules above.  
   - Then, if an internal XML file is provided, parse it and merge any extra fields.  
   - Output **only** the final `<XML_order>…</XML_order>` document (nothing else, no explanatory text).  
   - Make sure to strictly follow the tag names, attribute names, and order shown.

"""


def process(pdf_path, xml_path=None):
    pdf_images = pdf_to_images(pdf_path)
    query = [{"type": "text", "text": "Please analyze the attached PDF pages"}]
    for i, img_base64 in enumerate(pdf_images):
        query.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": img_base64
            }
        })
    if xml_path:
        xml_content = read_xml_file(xml_path)
        query.append({"type": "text", "text": f"\n\nAdditionally, here is the secondary XML file to merge:\n\n{xml_content}\n\nPlease merge any relevant information from this XML into the final output according to the schema rules. Output only the final <XML_order> document."})
    else:
        query.append({"type": "text", "text": " according to the schema rules. Output only the final <XML_order> document."})
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
