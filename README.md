# Copaco_PoC

## Overview

This Proof of Concept was developed for COPACO by Sigli. It is a Streamlit-based application designed to parse PDF invoices and orders, converting them into a standardized XML format. The application also offers the optional capability to merge data from secondary XML files.
## How to Run the App

1. **Install Requirements**  
   Ensure that all required libraries are installed, either manually or by running:
   ```bash
   pip install -r requirements.txt

2. **Navigate to the App Directory**  
   Change your directory to the location of the app:
   ```bash
   cd path/to/Copaco_PoC

3. **Run the App**  
   Execute the app with the following command:
   ```bash
   streamlit run main.py

4. **View the App**
   After running the command, a local server will start, and you can access the app in your web browser at the URL provided (usually http://localhost:8501/).

5. **Deploying to Azure**  
   To deploy the app to Azure, ensure that all changes are committed and push them to the master branch:
   ```bash
   git push origin master
