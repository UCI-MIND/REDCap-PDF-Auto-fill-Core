# REDCap PDF Auto-fill Core

Automatically populates fields within a given template PDF with data from a single record in a REDCap project.

Supports REDCap text fields, dropdowns, checkboxes, and radio buttons.

Developed and tested with Python 3.9.10, although this should work with all versions of **Python >= 3.9**.

Please note the license terms in `LICENSE.txt` - this tool is not guaranteed to be compatible with your own REDCap projects "out of the box"; some tinkering may be required. UCI MIND lacks the resources to maintain or add features to this tool, although we may push critical updates as necessary.

# Before use

* Ensure that your template PDF contains fillable form fields in the first place. One method to check this is to open your PDF in a modern web browser of your choice and see if you can click checkboxes, buttons, and/or enter text.
  * Verify PDF field names using software such as Adobe Acrobat. PDF field names must *exactly* match how the fields appear in the REDCap API (for example, checkboxes are named like "`checkboxname___#`").
* Edit `secrets.json` and add a valid API key and URL to your REDCap instance. Visit your project's "API" and "API Playground" pages for details.
* When running this script, it is recommended to create a virtual environment to keep packages isolated on your system:
```
cd {into this repository's folder}

# Create a Python virtual environment (only need to do this once):
python -m venv .venv

# Activate the virtual environment:
.\.venv\Scripts\Activate.ps1
# No file extension needed on other platforms
# Windows: .ps1 for PowerShell or .bat for Command Prompt

# If using PowerShell and "running scripts is disabled on this system", need to
# enable running external scripts. Open PowerShell as admin and use this command:
#     set-executionpolicy remotesigned
# (only need to do this once)

# While in the virtual env, install packages (only need to do this once):
python -m pip install -r requirements.txt

# Run the script, develop, debug, etc. (see below for details):
python main.py ...

# Deactivate when done
deactivate
```

For testing purposes, a sample REDCap project has been provided (also containing some sample data) as well as a sample PDF file made specifically for this project.
  * To import this REDCap project to your REDCap instance, create a new REDCap project like you usually would, but select "Upload a REDCap project XML file (CDISC ODM format)" and locate the .xml file in this repository named `PDFAutofillSampleProject.REDCap.xml`.
  * It is recommended to study the relationship between the **names** and **types** of the sample project's REDCap variables, the keys/values in the prepared Python dictionary, and the PDF fields/types in `sample_pdf.pdf`.

# Usage

Use in a command-line (brackets indicate optional arguments):
```
main.py [-h] -id IDENTIFIER [-v [RECORD_VARIABLE]] -i INPUT_PDF [-o OUTPUT_PDF]
```

Table of valid command-line arguments:
| Argument | Shorthand | Required? | Description |
| :------: | :-------: | :-------: | :---------- |
| `--help` | `-h` |  | Display a help message and exit. |
| `--identifier` | `-id` | ✅ | Unique ID of a REDCap record to fill out a template PDF. |
| `--record-variable` | `-v` |  | Name of the REDCap variable that uniquely identifies each record. Default value: `record_id` |
| `--input-pdf` | `-i` | ✅ | Path to an empty template .pdf file to fill in. |
| `--output-pdf` | `-o` |  | Path to a new .pdf file that will essentially be a copy of `--input-pdf`, but filled with data from the REDCap record identified with `--identifier` and `--record-variable`. Default value:<br />`/output/{time_of_script_execution}_{input_pdf_name}_{record}.pdf` |

Example:
```
python main.py -id 1 -v participant_id -i C:/Users/Public/Documents/form_a5.pdf -o C:/Users/Public/Desktop/form_a5_output.pdf
```

Here, the script will search for a REDCap record with a value of '1' in the REDCap variable 'participant_id'. The input form is located at `C:/Users/Public/Documents/form_a5.pdf`, and the resultant filled-in PDF will be written to `C:/Users/Public/Desktop/form_a5_output.pdf`.

# Resources

https://www.adobe.com/content/dam/acom/en/devnet/pdf/pdfs/PDF32000_2008.pdf

https://www.w3.org/TR/WCAG20-TECHS/pdf.html

# Funding

To support our work and ensure future opportunities for development, please acknowledge the software and funding.
The project was funded by The University of California, Irvine's Institute for Memory Impairments and Neurological Disorders (UCI MIND) grant, P30AG066519.
