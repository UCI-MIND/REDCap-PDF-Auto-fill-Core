# Contains functions and helpers to manipulate PDFs and the data that will go into one.
# Modified version of https://akdux.com/python/2020/10/31/python-fill-pdf-files.html by Andrew Krcatovich

import pdfrw
import argparse
import json

import redcap_helpers

from pathlib import Path
from datetime import datetime

SECRETS_FILE = Path("secrets.json")

# Constants used for digging through PDFs
ANNOT_KEY = '/Annots'
ANNOT_FIELD_KEY = '/T'
ANNOT_VAL_KEY = '/V'
ANNOT_RECT_KEY = '/Rect'
SUBTYPE_KEY = '/Subtype'
WIDGET_SUBTYPE_KEY = '/Widget'
PARENT_KEY = '/Parent'
APPEARANCE_KEY = '/AP'
D_KEY = '/D'

parser = argparse.ArgumentParser(description="REDCap PDF Auto-fill Core")
parser.add_argument("-id", "--identifier", required=True, help="Unique ID of a REDCap record to fill out a template PDF")
parser.add_argument("-v", "--record-variable", nargs='?', default='record_id', const='record_id', help="Name of the REDCap variable that uniquely identifies each record (default: record_id)")
parser.add_argument("-i", "--input-pdf", required=True, help="Path to an empty template .pdf file that will contain the data from a REDCap record")
parser.add_argument("-o", "--output-pdf", help="Path to a new .pdf file that will be created and filled in with data from a REDCap record")

################################################################
################################################################

def get_cmd_line_input(inp: argparse.Namespace) -> tuple[str, str, Path, Path]:
    if not inp.input_pdf.endswith(".pdf"):
        raise ValueError("Template PDF must have a '.pdf' extension: " + inp.input_pdf)
    
    input_pdf_path = Path(inp.input_pdf)

    if not input_pdf_path.exists():
        raise FileNotFoundError(f"Template PDF does not exist: {inp.input_pdf}")
    
    if not inp.output_pdf:
        # User did not specify an output location
        default_output_pdf = f"./output/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{input_pdf_path.stem}_{inp.identifier}.pdf"
        print("No output PDF file specified; writing filled PDF to:", default_output_pdf)
        output_pdf_path = Path(default_output_pdf)
    else:
        if not inp.output_pdf.endswith(".pdf"):
            # Don't stop the script, just display a warning
            print("Warning: Output PDF does not have a '.pdf' extension: " + inp.output_pdf)
            print("         Auto-filling will continue to function, but you may have trouble opening the output PDF.")
        output_pdf_path = Path(inp.output_pdf)

    if input_pdf_path == output_pdf_path:
        raise FileExistsError(f"Template PDF and output PDF must be different: {inp.input_pdf}")

    input_pack = (inp.identifier, inp.record_variable, input_pdf_path, output_pdf_path)
    print(f"Inputs: Record:\t\t{input_pack[0]}\n\tREDCap var:\t{input_pack[1]}\n\tTemplate PDF:\t{input_pack[2]}\n\tOutput PDF:\t{input_pack[3]}")
    return input_pack

def load_secrets(json_file_path: str) -> dict:
    '''Returns a dictionary of the .json file located at json_file_path.
    Specialized to check if keys 'api_key' and 'url' are not empty.
    '''
    result = dict()
    with open(json_file_path, "r") as f:
        result = json.load(f)
    if result['api_key'] and result['url']:
        return result
    raise ValueError("Failed to load secrets.json - did you fill in your REDCap project's API key and URL?")

def get_pdf_fields(input_pdf_path: Path) -> list[str]:
    '''Returns a list of field names in the PDF file specifed by input_pdf_path, listed in order of appearance.
    '''
    template_pdf = pdfrw.PdfReader(input_pdf_path)
    result = []
    for page in template_pdf.pages:
        annotations = page[ANNOT_KEY]
        if annotations is None:
            continue
        for annotation in annotations:
            if annotation[SUBTYPE_KEY] == WIDGET_SUBTYPE_KEY:
                if annotation[ANNOT_FIELD_KEY]:                 ### Isolated fields ("has a '/T' field")
                    key = annotation[ANNOT_FIELD_KEY][1:-1]
                    if '___' in key:                            # Checkboxes have a default '___' separator after the field name
                        key = key.split('___')[0]
                    if key not in result:
                        result.append(key)
                elif annotation[PARENT_KEY][ANNOT_FIELD_KEY]:   ### Grouped fields ("has a '/Parent' > '/T' field")
                    group = annotation[PARENT_KEY][ANNOT_FIELD_KEY][1:-1]
                    if '___' in group:
                        group = group.split('___')[0]
                    if group not in result:
                        result.append(group)
    return result

def convert_checkboxes_and_radio_buttons(r: dict, md: list[dict]) -> dict:
    '''Prepares an API-provided record to contain data that can be written to a PDF.
    * Checkbox key/value pairs are changed from
        '{checkbox_name}': '0' or '{checkbox_name}': '1'
      to
        '{checkbox_name}': False or '{checkbox_name}': True
    * Radio button key/value pairs are changed from
        '{radio_button_variable}': '{choice}'
      to
        '{radio_button_variable}': {
            'choice': True
        }
    '''
    radio_buttons,checkboxes = redcap_helpers.get_radio_buttons_checkboxes(md)

    RADIO_BUTTON_CHOICE_SUFFIX = "__rchoice"    # Default "__rchoice"

    num_checkboxes_edited = 0
    num_radio_buttons_edited = 0
    new_dict_of_radio_values = dict()

    for redcap_variable in r:
        # Checkboxes are represented in the API by '{fieldname}___{choice}': '{0 or 1}'
        # Example:  In the API, you get this: 'cb_1___3': '1'
        #           'cb_1'  =   variable/field name                 ("Checkbox 1")
        #           '___'   =   auto-generated separator
        #           '3'     =   choice                              ("Choice 3")
        #           '1'     =   '1' if checked, '0' if unchecked    (choice 3 is checked)
        checkbox_token_check = redcap_variable.split('___')
        redcap_value = r[redcap_variable]
        # Checkboxes:
        if len(checkbox_token_check) > 1 and checkbox_token_check[0] in checkboxes:
            # If the split() worked, then the resultant list would have 2 or more elements and redcap_variable is a checkbox
            r[redcap_variable] = redcap_value == '1'    # Change str to bool
            num_checkboxes_edited += 1
        # Radio buttons (split() should do nothing if it couldn't find the separator string):
        elif redcap_variable in radio_buttons:
            r[redcap_variable] = {redcap_value: True}   # redcap_value is the *raw value* of the radio button that was picked (not the display text)
            num_radio_buttons_edited += 1
            if redcap_value != "":
                # Also add the choice of radio button as an additional text value (named with a suffix defined above, so name the field in the PDF accordingly)
                # Some PDFs have text fields that are represented in REDCap as radio buttons; this behavior bridges these 2 formats
                # NOTE: this only adds the radio button *choice* as an additional text value, not the text that accompanies it
                new_dict_of_radio_values[redcap_variable + RADIO_BUTTON_CHOICE_SUFFIX] = redcap_value
    r.update(new_dict_of_radio_values)
    # print(f">>> Edited fields: {num_checkboxes_edited} checkboxes, {num_radio_buttons_edited} radio buttons ({len(new_dict_of_radio_values)} additional text fields added)")
    return r

def convert_dropdowns_to_strings(r: dict, md: list[dict]) -> dict:
    '''Returns a formatted version of record r where any dropdown variables have their value overwritten with
    their accompanying display text (instead of their raw value).
    '''
    # Had trouble with overriding PDF dropdowns - instead, REDCap dropdowns can be written to plain text boxes in template PDFs.
    # Page 445? https://www.adobe.com/content/dam/acom/en/devnet/pdf/pdfs/PDF32000_2008.pdf
    proj_multi_choice_text = redcap_helpers.get_multiple_choice_text(md)
    for field in md:
        if field['field_type'] == 'dropdown':
            dropdown_var_name = field['field_name']
            if r[dropdown_var_name] != "":
                r[dropdown_var_name] = proj_multi_choice_text[dropdown_var_name][r[dropdown_var_name]]
    return r

def collapse_radio_groups(r: dict, md: list[dict]) -> dict:
    '''Returns a formatted version of record r where all radio button groups contain only 1 True value.
    {"radio_button_group": {
            "choice_1": True
        }
    }
    Intended to simplify the process of determining which radio button to select.
    '''
    num_of_collapsed_radio_groups = 0

    # Old method of searching in the record instead of the metadata dict:
    # groups = [i for i in r if type(r[i]) == dict]     # Any dictionaries *in the data dictionary* are radio buttons

    # Now, trust the metadata dict instead:
    groups = [field['field_name'] for field in md if field['field_type'] == 'radio']

    def _contains_only_one_true(iterable) -> bool:
        '''Returns whether or not 'iterable' contains only a single True value.
        Thank you Jon Clements and Antti Haapala! https://stackoverflow.com/a/16801605
        '''
        i = iter(iterable)
        return any(i) and not any(i)

    for radio_group in groups:
        vals = r[radio_group].values()
        if any(not isinstance(x, bool) for x in vals):
            raise TypeError(f"Radio button groups should only contain boolean values: {r[radio_group]}")
        if not _contains_only_one_true(vals):
            raise ValueError(f"Radio button groups should contain exactly 1 True value: {r[radio_group]}")
        if len(r[radio_group]) > 1:
            # Remove all k/v pairs from r[radio_group], leaving only the field that is True:
            for k in r[radio_group]:
                if r[radio_group][k]:
                    # If a "True" is found in r[radio_group], assign r[radio_group] a new dictionary that only contains {key:True}
                    r[radio_group] = dict([(k, r[radio_group][k])])
                    num_of_collapsed_radio_groups += 1
                    break
    # print(f">>> Collapsed {num_of_collapsed_radio_groups} radio button fields")
    return r

def prepare_for_fill(record: dict, md: list[dict]) -> dict:
    r = convert_checkboxes_and_radio_buttons(record, md)
    r = convert_dropdowns_to_strings(r, md)
    r = collapse_radio_groups(r, md)
    return r

def fill_pdf(input_pdf_path: Path, output_pdf_path: Path, data_dict: dict) -> None:
    '''Main function to handle filling in PDF fields.
    Uses data_dict to populate fields from the template in input_pdf_path, writing the filled-in PDF to output_pdf_path.
    '''
    template_pdf = pdfrw.PdfReader(input_pdf_path)
    for page in template_pdf.pages:
        annotations = page[ANNOT_KEY]
        if annotations is None:
            continue
        for annotation in annotations:
            if annotation[SUBTYPE_KEY] == WIDGET_SUBTYPE_KEY:
                if annotation[ANNOT_FIELD_KEY]:                 ### Isolated fields (has a '/T' key)
                    key = annotation[ANNOT_FIELD_KEY][1:-1]
                    if key in data_dict.keys():
                        if type(data_dict[key]) == bool:        # Checkboxes
                            if data_dict[key] == True:
                                annotation.update(pdfrw.PdfDict(
                                    AS=pdfrw.PdfName('Yes'), V=pdfrw.PdfName('Yes'))
                                )
                            else:
                                annotation.update(pdfrw.PdfDict(
                                    AS=pdfrw.PdfName('Off'), V=pdfrw.PdfName('Off'))
                                )
                        else:                                   # Text field
                            annotation.update(pdfrw.PdfDict(
                                AP='', V=data_dict[key])
                            )
                
                elif annotation[PARENT_KEY][ANNOT_FIELD_KEY]:   ### Grouped fields (has a '/Parent' -> '/T' key)
                    group = annotation[PARENT_KEY][ANNOT_FIELD_KEY][1:-1]
                    if group in data_dict.keys():
                        if type(data_dict[group]) == dict and len(data_dict[group]) != 0:       # Radio buttons
                            selected_radio_button = pdfrw.PdfName(list(data_dict[group].keys())[0])
                            if(selected_radio_button in annotation[APPEARANCE_KEY][D_KEY].keys()):
                                # Page 441 of:
                                # https://www.adobe.com/content/dam/acom/en/devnet/pdf/pdfs/PDF32000_2008.pdf
                                annotation[PARENT_KEY].update(pdfrw.PdfDict(
                                    V=selected_radio_button)
                                )
                                annotation.update(pdfrw.PdfDict(
                                    AS=selected_radio_button)
                                )
                        elif type(data_dict[group]) == bool:            # Linked checkboxes (across multiple pages?)
                            if data_dict[group] == True:
                                annotation.update(pdfrw.PdfDict(
                                    AS=pdfrw.PdfName('Yes'), V=pdfrw.PdfName('Yes'))
                                )
                            else:
                                annotation.update(pdfrw.PdfDict(
                                    AS=pdfrw.PdfName('Off'), V=pdfrw.PdfName('Off'))
                                )
                        else:                                           # Linked text fields (across multiple pages?)
                            annotation[PARENT_KEY].update(pdfrw.PdfDict(
                                AP='', V=data_dict[group])
                            )
    
    if not output_pdf_path.parent.exists():
        print(f"    Location of output PDF '{output_pdf_path}' doesn't exist; creating: {output_pdf_path.parent}")
        output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    
    template_pdf.Root.AcroForm.update(pdfrw.PdfDict(NeedAppearances=pdfrw.PdfObject('true')))
    pdfrw.PdfWriter().write(output_pdf_path, template_pdf)
    return

################################################################
################################################################

if __name__ == '__main__':
    RECORD,REDCAP_UNIQUE_IDENTIFIER,PDF_TEMPLATE,OUTPUT = get_cmd_line_input(parser.parse_args())
    print()

    secrets = load_secrets(SECRETS_FILE)
    print("Loaded secrets file")

    proj_metadata = redcap_helpers.get_metadata(secrets)
    print("Got project metadata")
    # print(redcap_helpers.get_fields_and_types(proj_metadata))

    # proj_multiple_choice_text = redcap_helpers.get_multiple_choice_text(proj_metadata)
    # print(proj_multiple_choice_text)

    record = redcap_helpers.get_record(secrets, REDCAP_UNIQUE_IDENTIFIER, RECORD)
    print(f"Got record {RECORD} (identified by '{REDCAP_UNIQUE_IDENTIFIER}')")

    prepared_data_dict = prepare_for_fill(record, proj_metadata)
    print("Prepared Python dictionary:", prepared_data_dict)

    print("Using PDF template:  " + str(PDF_TEMPLATE))
    fill_pdf(PDF_TEMPLATE, OUTPUT, prepared_data_dict)
    print("PDF written to:      " + str(OUTPUT))
    print("Done!")
