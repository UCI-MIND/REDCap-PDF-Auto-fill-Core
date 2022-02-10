# Contains functions and helpers to obtain and interact with REDCap API data.

import json
import requests

################################################################
#### Metadata behavior
################################################################

def _request_metadata(secrets_dict: dict) -> str:
    '''Makes a REDCap API call for a REDCap project's metadata.
    Returns the text of the API response.
    '''
    metadata_request = {
        'token': secrets_dict['api_key'],
        'content': 'metadata',
        'format': 'json',
    }
    r = requests.post(secrets_dict['url'],data=metadata_request)
    #print('>>> Metadata request HTTP Status: ' + str(r.status_code))
    return r.text

def get_metadata(secrets_dict: dict) -> list[dict]:
    '''Returns a list of dictionaries that contain metadata for a REDCap project's fields.
    '''
    raw_metadata_string = _request_metadata(secrets_dict)
    md = json.loads(raw_metadata_string)
    if type(md) == dict and md['error']:
        print(f"REDCap API returned an error while fetching metadata: {md['error']}")
        exit(1)
    return md

def _extract_field(md: list[dict], which_field: str) -> list[str]:
    '''Parses REDCap metadata and returns a list of variable names of the desired field type.
    Originally intended for use with radio buttons (which_field='radio') and checkboxes (which_field='checkbox').
    '''
    result = []
    for field in md:
        if field['field_type'] == which_field:
            result.append(field['field_name'])
    return result

def get_radio_buttons_checkboxes(md: list[dict]) -> tuple[list[str], list[str]]:
    '''Returns a 2-tuple of lists: the first a list of radio button fields, and the second a list of checkbox fields
    (as defined in REDCap metadata dictionary md).
    '''
    return (_extract_field(md, 'radio'), _extract_field(md, 'checkbox'))

def get_fields_and_types(md: list[dict]) -> dict[str:str]:
    '''Returns a dictionary mapping REDCap field names to their REDCap-defined types.
    '''
    result = dict()
    for field in md:
        result[field['field_name']] = field['field_type']
    return result

def get_multiple_choice_text(md: list[dict]) -> dict[str:dict]:
    '''Returns a dictionary mapping multiple-choice REDCap variable names to
    a dict of options mapping each option's raw value to its display text.
    Example:
        REDCap radio button named 'radio_buttons_1' with values:
            1, Option A
            2, Option B
        This function will create a dict like so:
            texts = {'radio_buttons_1': {'1': 'Option A', '2': 'Option B'}}
            texts['radio_buttons_1']['1'] == 'Option A'     # True
    '''
    texts = dict()
    for field in md:
        # First verify if field is a multiple-choice field
        if ('select_choices_or_calculations' in field and \
                type(field) == dict and \
                field['select_choices_or_calculations']):
            # REDCap API returns multiple choice options in the format
            #   "{raw_value}, {display_text} | {raw_value}, {display_text} | ... "
            # Create the dict that maps raw_value to display_text:
            sub_dict = dict()
            choices = field['select_choices_or_calculations'].split(' | ')
            # Sometimes REDCap skips the spaces between the vertical bar '|' separating choices....
            if len(choices) == 1:
                choices = field['select_choices_or_calculations'].split('|')
            for option in choices:
                option_fragments = option.strip().split(', ')
                # option_fragments[0] is raw_value, everything else is display_text (which could have a ', ' in it)
                sub_dict[option_fragments[0]] = ', '.join(option_fragments[1:])
            texts[field['field_name']] = sub_dict
    return texts

################################################################
#### Records behavior
################################################################

def _request_record(secrets_dict: dict, redcap_unique_identifier: str, record_id) -> str:
    '''Makes a REDCap API call for a single record from a REDCap project.
    Returns the text of the API response.
    '''
    record_request = {
        'token': secrets_dict['api_key'],
        'content': "record",
        'format': "json",
        'type': "flat",
        'filterLogic': f"[{redcap_unique_identifier}] = '{record_id}'"
    }
    r = requests.post(secrets_dict['url'],data=record_request)
    #print('>>> Record request HTTP Status: ' + str(r.status_code))
    return r.text

def get_record(secrets_dict: dict, redcap_unique_identifier: str, record_id: str) -> dict:
    '''Returns a dictionary that contains data of a single REDCap record,
    identified by the value of record_id in redcap_unique_identifier.
    '''
    raw_record_data = _request_record(secrets_dict, redcap_unique_identifier, record_id)
    record = json.loads(raw_record_data)
    if type(record) == dict and record['error']:
        print(f"REDCap API returned an error while fetching record {record_id}: {record['error']}")
        exit(1)
    if type(record) == list :
        if len(record) < 1:
            # REDCap API returns '[]' if no results return from filterLogic despite a 200 OK HTTP code.
            # filterLogic generates a *list* of records matching that logic.
            # If filterLogic is incorrect or too strict, there's nothing to return, and that generated list is empty.
            raise LookupError(f"No records found where '{redcap_unique_identifier}' = {record_id}")
        elif len(record) > 1:
            raise LookupError(f"Multiple records found where '{redcap_unique_identifier}' = {record_id} (expected only 1)")
        return record[0]
    return record
