
import pandas as pd
import random
import verovio
import streamlit as st
import streamlit.components.v1 as components
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent
import base64
from io import StringIO


st.set_page_config(page_title="Rhythm Pattern Generator")
st.title("Rhythm Pattern Generator")

if "seed" not in st.session_state:
    st.session_state.seed = 0

if st.button("Generate a New Pattern"):
    st.session_state.seed += 1

# --- Time signature / note length lookup ---
TIME_SIG_NOTES = {
    ("3/4",  "8th notes"):  6,
    ("3/4",  "16th notes"): 12,
    ("4/4",  "8th notes"):  8,
    ("4/4",  "16th notes"): 16,
    ("6/8",  "8th notes"):  6,
    ("6/8",  "16th notes"): 12,
    ("12/8", "8th notes"):  12,
    ("12/8", "16th notes"): 24,
}

BEAM_GROUP = {
    "3/4":  2,
    "4/4":  2,
    "6/8":  3,
    "12/8": 3,
}

NOTE_TYPE = {
    "8th notes":  "eighth",
    "16th notes": "16th",
}

# --- Inputs ---
with st.container():
    st.subheader("Settings")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        time_sig = st.selectbox("Time Signature", ["3/4", "4/4", "6/8", "12/8"], index=3)
    with col2:
        note_len = st.selectbox("Note Length", ["8th notes", "16th notes"])
    with col3:
        notes_per_measure = TIME_SIG_NOTES[(time_sig, note_len)]
        strokes = st.slider("Number of Strokes in the Pattern", min_value=0, max_value=notes_per_measure, value=min(notes_per_measure // 2, notes_per_measure))
        strokes = min(strokes, notes_per_measure)
    with col4:
        N = st.number_input("Number of Combinations", min_value=1, max_value=100, value=10, step=1)

# --- Logic ---
def generate_combination(strokes, total):
    combination = [1] * strokes + [0] * (total - strokes)
    random.shuffle(combination)
    return combination

out = []
random.seed(st.session_state.seed)
for i in range(N):
    X = generate_combination(strokes, notes_per_measure)
    out.append(X)
out = pd.DataFrame(out)

def df_to_musicxml_string(df, time_sig, note_len, notes_per_measure):
    beats, beat_type = time_sig.split("/")
    beam_group = BEAM_GROUP[time_sig]
    note_type = NOTE_TYPE[note_len]

    score = Element("score-partwise", version="4.0")

    part_list = SubElement(score, "part-list")
    score_part = SubElement(part_list, "score-part", id="P1")
    part_name = SubElement(score_part, "part-name")

    part = SubElement(score, "part", id="P1")

    for measure_num, row in df.iterrows():
        measure = SubElement(part, "measure", number=str(measure_num + 1))

        # Force system break every 4 measures
        if measure_num > 0 and measure_num % 4 == 0:
            SubElement(measure, "print", attrib={"new-system": "yes"})

        if measure_num == 0:
            attributes = SubElement(measure, "attributes")
            divisions = SubElement(attributes, "divisions")
            divisions.text = "1"
            key = SubElement(attributes, "key")
            fifths = SubElement(key, "fifths")
            fifths.text = "0"
            time = SubElement(attributes, "time")
            beats_el = SubElement(time, "beats")
            beats_el.text = beats
            beat_type_el = SubElement(time, "beat-type")
            beat_type_el.text = beat_type
            clef = SubElement(attributes, "clef")
            sign = SubElement(clef, "sign")
            sign.text = "percussion"

        # Pre-compute beam tags
        row_vals = list(row)
        beam_tags = [None] * notes_per_measure
        num_groups = notes_per_measure // beam_group
        for g in range(num_groups):
            group_idx = [g * beam_group + k for k in range(beam_group)]
            note_idx = [i for i in group_idx if row_vals[i] == 1]
            if len(note_idx) >= 2:
                beam_tags[note_idx[0]] = "begin"
                beam_tags[note_idx[-1]] = "end"
                for i in note_idx[1:-1]:
                    beam_tags[i] = "continue"

        for i, val in enumerate(row_vals):
            note = SubElement(measure, "note")
            if val == 0:
                SubElement(note, "rest")
            else:
                pitch = SubElement(note, "pitch")
                step = SubElement(pitch, "step")
                step.text = "C"
                octave = SubElement(pitch, "octave")
                octave.text = "5"
            duration = SubElement(note, "duration")
            duration.text = "1"
            note_type_el = SubElement(note, "type")
            note_type_el.text = note_type

            if beam_tags[i] is not None:
                beam = SubElement(note, "beam", number="1")
                beam.text = beam_tags[i]

    indent(score)
    tree = ElementTree(score)
    s = StringIO()
    tree.write(s, encoding="unicode", xml_declaration=True)
    return s.getvalue()

# --- Render SVG ---
xml_string = df_to_musicxml_string(out, time_sig, note_len, notes_per_measure)

def render_svg(xml_string):
    import os
    tk = verovio.toolkit()
    verovio_path = os.path.dirname(verovio.__file__)
    tk.setResourcePath(os.path.join(verovio_path, "data"))
    tk.setOptions({
        "pageWidth": 2159,
        "pageHeight": 2794,
        "scale": 40
    })
    tk.loadData(xml_string)
    return tk.renderToSVG(1)

svg = render_svg(xml_string)

# --- Output ---
st.subheader("Generated Score")

components.html(f"""
<style>
#toolbar {{
    padding: 10px 0;
}}

#score-container {{
    background: white;
    padding: 10px;
}}

/* Constrain SVG width */
#score-wrapper svg {{
    width: 100% !important;
    height: auto !important;
    display: block;
}}

/* Scrollable preview */
#score-wrapper {{
    max-height: 700px;
    overflow: auto;
    border: 1px solid #ddd;
    padding: 10px;
}}

/* PRINT: only show score */
@media print {{
    body * {{
        visibility: hidden;
    }}

    #score-container, #score-container * {{
        visibility: visible;
    }}

    #score-container {{
        position: absolute;
        left: 0;
        top: 0;
        width: 100%;
    }}

    /* Ensure SVG fits printable width */
    #score-wrapper svg {{
        width: 100% !important;
        height: auto !important;
    }}

    @page {{
        size: letter portrait;
        margin: 0.5in;
    }}
}}

button {{
    padding: 10px 16px;
    font-size: 16px;
    cursor: pointer;
}}
</style>

<div id="toolbar">
    <button onclick="window.print()">
        Export to PDF (Print)
    </button>
</div>

<div id="score-container">
    <div id="score-wrapper">
        {svg}
    </div>
</div>
""", height=900)

b64_svg = base64.b64encode(svg.encode()).decode()
st.html(f'<img src="data:image/svg+xml;base64,{b64_svg}" style="width:100%;" />')