from xml.sax.saxutils import escape

# Layout constants
VERTICAL_SPACING = 120
HORIZONTAL_SPACING = 250
NODE_WIDTH = 180
NODE_HEIGHT = 70
SECTION_SPACING = 300
COLLAPSED_GROUP_HEIGHT = 40

# Style constants
MAIN_PROGRAM_STYLE = "ellipse;fillColor=#d5e8d4;strokeColor=#82b366;fontStyle=1"
SUBROUTINE_STYLE = "ellipse;fillColor=#dae8fc;strokeColor=#6c8ebf"
DECISION_STYLE = "rhombus;fillColor=#f8cecc;strokeColor=#b85450"
ACTION_STYLE = "rounded=1;fillColor=#fff2cc;strokeColor=#d6b656"
GROUP_STYLE = "rounded=1;fillColor=#f5f5f5;strokeColor=#666666;dashed=1"
MOVEMENT_STYLE = "rounded=0;fillColor=#e1d5e7;strokeColor=#9673a6"

SHAPE_MAP = {
    "URProgram": "rectangle;fillColor=#f5f5f5;strokeColor=#666666;fontStyle=1;fontSize=16",
    "MainProgram": MAIN_PROGRAM_STYLE,
    "SpecialSequence": MAIN_PROGRAM_STYLE,
    "SubProgram": SUBROUTINE_STYLE,
    "CallSubProgram": SUBROUTINE_STYLE,
    "If": DECISION_STYLE,
    "Loop": DECISION_STYLE,
    "Switch": DECISION_STYLE,
    "Else": DECISION_STYLE,
    "Case": "rectangle;fillColor=#f8cecc;strokeColor=#b85450",
    "Move": MOVEMENT_STYLE,
    "Waypoint": MOVEMENT_STYLE + ";whiteSpace=wrap;html=1;align=left",
    "Script": ACTION_STYLE,
    "Assignment": ACTION_STYLE,
    "Set": ACTION_STYLE,
    "SetPayload": ACTION_STYLE,
    "Wait": ACTION_STYLE,
    "Comment": "note;fillColor=#fff2cc;strokeColor=#d6b656",
    "Folder": GROUP_STYLE,
    "Thread": GROUP_STYLE + ";fillColor=#d4e1f5",
    "Contributed": "rounded=1;fillColor=#d4e1f5;strokeColor=#6c8ebf",
    "InitVariablesNode": "rectangle;fillColor=#f5f5f5;strokeColor=#666666",
    "InitVariable": ACTION_STYLE
}

def safe_xml(s):
    """Escape & clean XML attribute strings."""
    if s is None:
        return ""
    return escape(str(s).replace("\n", " ").replace("\r", ""), {'"': '&quot;'})

def generate_drawio_xml(root_node):
    node_elements = []
    edge_elements = []
    group_elements = []
    counter = {"id": 1}

    def next_id():
        counter["id"] += 1
        return str(counter["id"])

    def create_node(node, x, y, width=NODE_WIDTH, height=NODE_HEIGHT, style=None):
        node_id = next_id()
        node_type = node["type"]
        display_text = node.get("displaytext", "")
        
        # Special handling for different node types
        if node_type == "Move":
            label = f'Move: {display_text}'
            if "children" in node and any(child["type"] == "Waypoint" for child in node["children"]):
                waypoints = [f'• {child["displaytext"]}' for child in node["children"] if child["type"] == "Waypoint"]
                label += f'\n{"".join(waypoints)}'
                height = max(NODE_HEIGHT, 30 + (20 * len(waypoints)))
        elif node_type in ["SubProgram", "CallSubProgram"]:
            label = f'Sub: {display_text}'
        elif node_type == "Folder":
            label = f'Group: {display_text}'
        else:
            label = f'{node_type}: {display_text}'

        style = style or SHAPE_MAP.get(node_type, "rectangle")
        label = safe_xml(label)

        node_xml = f'''
            <mxCell id="{node_id}" value="{label}" style="{style};whiteSpace=wrap;html=1;" vertex="1" parent="1">
              <mxGeometry x="{x}" y="{y}" width="{width}" height="{height}" as="geometry"/>
            </mxCell>
        '''
        node_elements.append(node_xml.strip())
        return node_id

    def connect(src_id, tgt_id, style=""):
        edge_id = next_id()
        edge_style = f"edgeStyle=orthogonalEdgeStyle;rounded=0;{style}"
        edge_xml = f'''
            <mxCell id="{edge_id}" style="{edge_style}" edge="1" parent="1" source="{src_id}" target="{tgt_id}">
              <mxGeometry relative="1" as="geometry"/>
            </mxCell>
        '''
        edge_elements.append(edge_xml.strip())

    def create_group(x, y, width, height, label, parent_id="1"):
        group_id = next_id()
        group_xml = f'''
            <mxCell id="{group_id}" value="{safe_xml(label)}" style="swimlane;whiteSpace=wrap;html=1;" vertex="1" parent="{parent_id}">
              <mxGeometry x="{x}" y="{y}" width="{width}" height="{height}" as="geometry"/>
            </mxCell>
        '''
        group_elements.append(group_xml.strip())
        return group_id

    def layout_section(node, start_x, start_y, parent_id=None):
        if node["type"] in ["Folder", "Thread"]:
            # Create a group for folders/threads
            group_id = create_group(start_x, start_y, NODE_WIDTH * 2, SECTION_SPACING, node["displaytext"])
            current_y = start_y + 40
            first_child_id = None
            last_child_id = None
            
            for child in node.get("children", []):
                child_id = layout_node_tree(child, start_x + 20, current_y, group_id)
                if not first_child_id:
                    first_child_id = child_id
                if last_child_id:
                    connect(last_child_id, child_id)
                last_child_id = child_id
                current_y += VERTICAL_SPACING
            
            return group_id
        else:
            return layout_node_tree(node, start_x, start_y, parent_id)

    def layout_node_tree(node, x, y, parent_id="1"):
        this_id = create_node(node, x, y)
        
        # Handle special cases
        if node["type"] == "If":
            # Layout If-Then-Else structure
            then_branch = next((c for c in node["children"] if c["type"] != "Else"), None)
            else_branch = next((c for c in node["children"] if c["type"] == "Else"), None)
            
            if then_branch:
                then_id = layout_node_tree(then_branch, x + HORIZONTAL_SPACING, y)
                connect(this_id, then_id, "exitX=0.5;exitY=1;entryX=0;entryY=0;dashed=0;label=Yes")
            
            if else_branch:
                else_id = layout_node_tree(else_branch, x - HORIZONTAL_SPACING, y)
                connect(this_id, else_id, "exitX=0;exitY=0.5;entryX=0.5;entryY=1;dashed=0;label=No")
                
            return this_id
        
        # Default layout for other nodes
        children = node.get("children", [])
        if children:
            first_child_id = None
            last_child_id = None
            current_y = y + VERTICAL_SPACING
            
            for child in children:
                child_id = layout_node_tree(child, x, current_y, parent_id)
                if not first_child_id:
                    first_child_id = child_id
                    connect(this_id, child_id)
                if last_child_id:
                    connect(last_child_id, child_id)
                last_child_id = child_id
                current_y += VERTICAL_SPACING
                
        return this_id

    # Start layout with program title
    program_title_id = create_node(
        {"type": "URProgram", "displaytext": root_node["displaytext"]},
        0, 0, NODE_WIDTH * 2, NODE_HEIGHT * 1.5
    )
    
    # Layout main sections vertically
    current_y = NODE_HEIGHT * 2
    last_section_id = None
    
    for child in root_node.get("children", []):
        section_id = layout_section(child, 0, current_y)
        if last_section_id:
            connect(last_section_id, section_id)
        last_section_id = section_id
        current_y += SECTION_SPACING

    drawio_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net">
  <diagram name="URProgram" id="1">
    <mxGraphModel dx="1500" dy="1500" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="850" pageHeight="1100">
      <root>
        <mxCell id="0"/>
        <mxCell id="1" parent="0"/>
        {"".join(group_elements)}
        {"".join(node_elements)}
        {"".join(edge_elements)}
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>'''
    return drawio_xml