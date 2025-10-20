from flask import Flask, render_template, request, jsonify, send_file, url_for
from plantcv.parallel import WorkflowConfig
from datetime import datetime
import pytz
import json
import io
import os


list_attrs = ["filename_metadata", "metadata_terms", "groupby"]
dict_attrs = ["job_extra_directives", "metadata_filters", "metadata_regex", "other_args"]
int_attrs = ["cores", "n_workers"]
bool_attrs = ["include_all_subdirs", "checkpoint", "verbose", "append", "cleanup"]


def parse_app_input(key, value, list_attrs, dict_attrs, int_attrs, bool_attrs):
    """Parse input from html form for WorkflowConfig attribute setting

    Parameters
    ----------
    key         = str, attribute name for WorkflowConfig object
    value       = str, input for WorkflowConfig object as returned from html form
    list_attrs  = list, list of which attributes become lists in WorkflowConfig
    dict_attrs  = list, list of which attributes become dicts in WorkflowConfig
    int_attrs   = list, list of which attributes become ints in WorkflowConfig
    bool_attrs  = list, list of which attributes become bools in WorkflowConfig

    Returns
    -------
    key         = str, unmodified attribute name, returned only for clarity
    out         = variable type, value to be assigned to key attribute in WorkflowConfig
    """
    # convert nulls to None for any datatype
    if value == "null":
        return key, None
    # if non-null then parse
    # determine if a field is str/int/bool/dict/list and format accordingly
    if key in list_attrs:
        if not bool(len(value)):
            out = []
        else:
            out = [val.strip() for val in value.split(",")]
    elif key in dict_attrs:
        if not bool(len(value)):
            out = {}
        else:
            out = dict([item.split(":") for item in [strdict.strip() for strdict in value.split(",")]])
    elif key in int_attrs:
        out = int(value)
    elif key in bool_attrs:
        out = value.lower() == "true"
    else:  # str attributes
        out = value
    return key, out

def handle_input_datetimes(tz_selection, start_date, end_date, timestamp_format):
    """Parse time related inputs from calendar menus
    Parameters
    ----------
    tz_selection     = str, a pytz timezone
    start_date       = str, start date as formatted by html datetime-local ('%Y-%m-%dT%H:%M')
    end_date         = str, start date as formatted by html datetime-local ('%Y-%m-%dT%H:%M')
    timestamp_format = str, target timestamp format

    Returns
    -------
    start_date      = str, start date adjusted to time zone selection in timestamp_format
    end_date        = str, end date adjusted to time zone selection in timestamp_format
    """
    if start_date != "null":
        tzstamp = datetime.strptime(start_date, "%Y-%m-%dT%H:%M")
        start_date = str(pytz.timezone(tz_selection).localize(tzstamp).strftime(timestamp_format))
    if end_date != "null":
        tzstamp = datetime.strptime(end_date, "%Y-%m-%dT%H:%M")
        end_date = str(pytz.timezone(tz_selection).localize(tzstamp).strftime(timestamp_format))
    return start_date, end_date

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    timezones = pytz.common_timezones
    default_tz = request.headers.get('X-Timezone') or 'UTC'
    timezones.insert(0, default_tz)

    if request.method == 'POST':
        # Collect all form data into a dictionary
        data = request.form.to_dict()
        # Convert dictionary to JSON and create downloadable file
        config = WorkflowConfig()
        object.__setattr__(config, "verbose", False)
        json_data = json.loads(json.dumps(data, indent=4))
        # before going to for loop this should handle timestamps/time formatting
        new_start_date, new_end_date = handle_input_datetimes(
            json_data.get("tz_selection"),
            json_data.get("start_date"),
            json_data.get("end_date"),
            json_data.get("timestampformat")
        )
        json_data["start_date"] = new_start_date
        json_data["end_date"] = new_end_date

        for key, value in json_data.items():
            key, out = parse_app_input(key, value,
                                       list_attrs, dict_attrs,
                                       int_attrs, bool_attrs)
            if key not in ["n_workers", "cores", "memory",
                           "disk", "log_directory", "local_directory",
                           "job_extra_directives"]:
                object.__setattr__(config, key, out)
            else:
                config.cluster_config[key] = out
        # auto set metadata terms if they are missing
        config._metadata_terms = config.metadata_term_definition()
        # dump content for writing
        content = vars(config)
        # normally this happens in config.save_config, here we do it manually
        content = {k.strip("_"): v for k, v in content.items()}

        return send_file(
            io.BytesIO(json.dumps(content, indent=4).encode()),
            mimetype='application/json',
            as_attachment=True,
            download_name='config.json'
        )
    # Render HTML form for GET requests
    return render_template("config_app_template.html",
                           tz_formats=timezones)

if __name__ == '__main__':
    app.run(debug=True)
