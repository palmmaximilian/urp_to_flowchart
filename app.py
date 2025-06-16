import streamlit as st
import gzip
from lxml import etree

from expression_parser import parse_expression, resolve_variable_name_from_reference, parse_node_structured
from drawio_exporter import generate_drawio_xml


st.set_page_config(page_title="URProgram Visualizer", layout="wide")
st.title("🤖 URProgram Visualizer")

variable_element_to_name = {}


def render_node_list(nodes, lines=None, line_counter=None, inside_init=False):
    if lines is None:
        lines = []
    if line_counter is None:
        line_counter = [1]  # Mutable line counter

    for node in nodes:
        if node is None:
            continue

        indent = "  " * node["depth"]
        line_text = f"{indent}- {node['type']}: {node['displaytext']}"

        if not inside_init:
            line_prefix = f"{line_counter[0]:>3} | "
            line_counter[0] += 1
        else:
            line_prefix = "    | "

        lines.append(line_prefix + line_text)

        # Recursively render children
        # but pass `inside_init=True` if current node is InitVariablesNode
        child_inside_init = inside_init or (node["type"] == "InitVariablesNode")
        render_node_list(node["children"], lines, line_counter, inside_init=child_inside_init)

    return lines




uploaded_file = st.file_uploader("Upload a .urp file", type=["urp"])

if uploaded_file:

    try:
        with gzip.open(uploaded_file, "rb") as f:
            raw_bytes = f.read()
        xml_text = raw_bytes.decode("utf-8", errors="ignore")
    except Exception as e:
        st.error(f"GZIP decompress failed: {e}")
        st.stop()

    start_tag = "<URProgram"
    end_tag = "</URProgram>"
    start_index = xml_text.find(start_tag)
    end_index = xml_text.find(end_tag)
    if start_index != -1 and end_index != -1:
        end_index += len(end_tag)
        xml_segment = xml_text[start_index:end_index]

        try:
            parser = etree.XMLParser(recover=True)
            root = etree.fromstring(xml_segment.encode("utf-8"), parser=parser)
            st.subheader("📜 Parsed Program Structure")
            variable_element_to_name.clear()
            structured_root = parse_node_structured(root, root)

           # Skip top-level URProgram
            top_children = structured_root["children"]

            all_lines = []
            line_counter = [1]  # shared mutable counter across sections

            for section in top_children:
                section_lines = render_node_list([section], line_counter=line_counter)
                all_lines.extend(section_lines)
                all_lines.append("")  # visual separation

            final_output = "\n".join(all_lines)
            st.code(final_output, language="text")
                    

            # drawio_data = generate_drawio_xml(structured_root)
            # st.download_button("💾 Download as draw.io XML", data=drawio_data, file_name="urprogram.drawio", mime="application/xml")


        except Exception as e:
            st.error(f"XML Parse Error: {e}")
    else:
        st.error("Could not find <URProgram> block in the file.")
