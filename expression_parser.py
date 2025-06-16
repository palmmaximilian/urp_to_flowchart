from lxml import etree

def resolve_variable_name_from_reference(ref_element):
    try:
        ref_path = ref_element.attrib.get("reference", "")
        target = ref_element.xpath(ref_path)
        if target and isinstance(target[0], etree._Element):
            return target[0].attrib.get("name", "?")
    except Exception:
        pass
    return "?"

def resolve_subprogram_name(reference: str, context_node):
    target = context_node.xpath(reference)
    if target:
        sub_node = target[0]
        return sub_node.attrib.get("name")
    return None

def parse_expression(expr_elem):
    parts = []

    if expr_elem is None:
        return "?"

    for child in expr_elem:
        tag = child.tag

        if tag == "ExpressionChar":
            parts.append(child.attrib.get("character", ""))
        elif tag == "ExpressionToken":
            parts.append(child.attrib.get("token", "").strip())
        elif tag == "ExpressionVariable":
            var_elem = child.find("*")  # could be ProgramVariable or InstallationVariable
            if var_elem is not None:
                name = var_elem.attrib.get("name")
                if name is None and "reference" in var_elem.attrib:
                    name = resolve_variable_name_from_reference(var_elem)
                parts.append(name or "?")
            else:
                parts.append("?")
        elif tag == "ExpressionGeomFeature":
            feature = child.find("feature")
            if feature is not None:
                parts.append(feature.attrib.get("referencedName", "?"))
            else:
                parts.append("?")
        else:
            parts.append("?")

    return "".join(parts).strip()


def parse_node_structured(node, root, depth=0):
    if node.tag == "SuppressedNode" or node.tag == "suppressedNode":
        is_suppressed = True

        # Case 1: Classic nested suppression: <SuppressedNode><RealNode>...</RealNode></SuppressedNode>
        if len(node) == 1 and node[0].tag != "children":
            node = node[0]

            # let the normal logic parse it, mark suppressed later
        else:
            # Case 2: Folder-like suppressedNode with multiple children
            return {
                "type": "Suppressed",
                "displaytext": "[commented out]",
                "depth": depth,
                "children": [
                    parsed for child in node.findall("./children/*")
                    if (parsed := parse_node_structured(child, node, depth + 1)) is not None
                ]
            }



    tag = node.tag
    name = node.attrib.get("name", "")
    motion_type = node.attrib.get("motionType", "")
    displaytext = ""
    children = []

    if tag == "Assignment":
        var_elem = node.find(".//variable")
        if var_elem is not None:
            var_name = var_elem.attrib.get("name")
            if var_name is None and "reference" in var_elem.attrib:
                var_name = resolve_variable_name_from_reference(var_elem)
        else:
            var_name = "?"

        expr_elem = node.find(".//expression")
        expr_val = "?"
        if expr_elem is not None:
            parts = []
            for child in expr_elem:
                if child.tag == "ExpressionChar":
                    parts.append(child.attrib.get("character", ""))
                elif child.tag == "ExpressionToken":
                    parts.append(child.attrib.get("token", "").strip())
                elif child.tag == "ExpressionVariable":
                    var_node = next(iter(child), None)  # ProgramVariable, InstallationVariable, etc.
                    if var_node is not None:
                        name = var_node.attrib.get("name")
                        if name is None and "reference" in var_node.attrib:
                            name = resolve_variable_name_from_reference(var_node)
                        parts.append(name or "?")
                    else:
                        parts.append("?")
                elif child.tag == "ExpressionGeomFeature":
                    feature_elem = child.find(".//feature")
                    if feature_elem is not None:
                        ref_name = feature_elem.attrib.get("referencedName", "?")
                        parts.append(ref_name)
                    else:
                        parts.append("?")
                else:
                    parts.append("?")  # fallback
            expr_val = "".join(parts).strip()

        displaytext = f"{var_name} = {expr_val}"



    elif tag == "InitVariablesNode":
        displaytext = "Initialize Variables"
        for var in node.findall(".//variable"):
            var_name = var.attrib.get("name", "?")
            expr_chars = var.findall(".//ExpressionChar")
            expr_val = "".join(c.attrib.get("character", "") for c in expr_chars)
            children.append({
                "type": "InitVariable",
                "name": var_name,
                "motion_type": "",
                "displaytext": f"{var_name} = {expr_val}",
                "depth": depth + 1,
                "children": []
            })

    elif tag == "CallSubProgram":
        sub_elem = node.find(".//subprogram")
        if sub_elem is not None:
            sub_name = sub_elem.attrib.get("name")
            if sub_name:
                displaytext = f"{sub_name}"
            else:
                ref = sub_elem.attrib.get("reference", "")
                resolved_name = resolve_subprogram_name(ref, sub_elem)
                displaytext = resolved_name if resolved_name else f"(ref): {ref}"
        else:
            displaytext = "[Missing <subprogram>]"

    elif tag == "SubProgram":
        ref = node.attrib.get("reference")
        if ref:
            resolved = node.xpath(ref)
            if resolved:
                target = resolved[0]
                name = target.attrib.get("name", "[anonymous]")
                displaytext = name
                children = [
                    parsed for child in target.findall("./children/*")
                    if (parsed := parse_node_structured(child, root, depth + 1)) is not None
                ]
            else:
                displaytext = f"(unresolved): {ref}"
                children = []
        else:
            name = node.attrib.get("name", "[anonymous]")
            displaytext = name
            children = [
                parsed for child in node.findall("./children/*")
                if (parsed := parse_node_structured(child, root, depth + 1)) is not None
            ]


    elif tag == "Move":
        displaytext = f"{motion_type}"

    elif tag == "Script":
        script_type = node.attrib.get("type", "")
        if script_type == "File":
            file_elem = node.find("file")
            file_path = file_elem.text.strip() if file_elem is not None and file_elem.text else "?"
            displaytext = file_path
        elif script_type == "Line":
            expr_elem = node.find(".//expression")
            expr_parts = []

            if expr_elem is not None:
                for child in expr_elem:
                    if child.tag == "ExpressionChar":
                        expr_parts.append(child.attrib.get("character", ""))
                    elif child.tag == "ExpressionVariable":
                        progvar = child.find(".//ProgramVariable")
                        if progvar is not None:
                            var_name = resolve_variable_name_from_reference(progvar)
                            expr_parts.append(var_name)
                        else:
                            expr_parts.append("?")
                    else:
                        expr_parts.append("?")
            expr_val = "".join(expr_parts)
            displaytext = expr_val
        else:
            displaytext = f"[Unknown type: {script_type}]"

    elif tag == "If":
        if_type = node.attrib.get("type", "If")
        if if_type == "Else":
            tag = "Else"
            displaytext = "Else"
        else:
            expr_elem = node.find(".//expression")
            displaytext = parse_expression(expr_elem)



    elif tag == "Loop":
        loop_type = node.attrib.get("type", "While")
        
        if loop_type == "Counting":
            count = node.attrib.get("count", "?")
            displaytext = f"{count} Times"
        else:
            token_elem = node.find(".//ExpressionToken")
            token = token_elem.attrib.get("token", "").strip() if token_elem is not None else ""
            progvar_elem = node.find(".//ProgramVariable")
            var_name = resolve_variable_name_from_reference(progvar_elem) if progvar_elem is not None else "?"
            displaytext = f"{loop_type} ({token} {var_name})".strip()


    elif tag == "Wait":
        wait_type = node.attrib.get("type", "Condition")
        if wait_type == "Sleep":
            wait_time_elem = node.find("waitTime")
            wait_time = wait_time_elem.text.strip() if wait_time_elem is not None and wait_time_elem.text else "?"
            displaytext = f"{wait_time}s"
        else:
            expr_elem = node.find(".//expression")
            token_elem = expr_elem.find(".//ExpressionToken") if expr_elem is not None else None
            expr_chars = expr_elem.findall(".//ExpressionChar") if expr_elem is not None else []
            token = token_elem.attrib.get("token", "").strip() if token_elem is not None else ""
            suffix = "".join(c.attrib.get("character", "") for c in expr_chars)
            displaytext = token + suffix if token or suffix else "?"

    elif tag == "SetPayload":
        displaytext = node.attrib.get("workpieceName", "?")

    elif tag == "Comment":
        displaytext = node.attrib.get("comment", "?")

    elif tag == "MainProgram":
        displaytext = "Main Program"

    elif tag == "SpecialSequence":
        displaytext = "Before Start Sequence"

    elif tag == "Contributed":
        strategy_type = node.attrib.get("strategyProgramNodeType", "?")
        developer = node.attrib.get("strategyURCapDeveloper", "")
        displaytext = f"{strategy_type}" + (f" ({developer})" if developer else "")
    elif tag == "gui.program.direction.MoveDirectionNode":
        tag="Direction"
        direction = node.attrib.get("selectedDirection", "?")
        displaytext = f"{direction}"

    elif tag == "Until":
        distance_elem = node.find("Distance")
        if distance_elem is not None and distance_elem.text:
            try:
                distance_m = float(distance_elem.text.strip())
                displaytext = f"{int(distance_m * 1000)}mm"
            except ValueError:
                displaytext = "Distance: [Invalid value]"
        else:
            displaytext = "Distance: ?"

    elif tag == "Switch":
        expr_elem = node.find(".//expression")
        progvar = expr_elem.find(".//ProgramVariable") if expr_elem is not None else None
        if progvar is not None:
            var_name = progvar.attrib.get("name")
            if var_name is None and "reference" in progvar.attrib:
                var_name = resolve_variable_name_from_reference(progvar)
        else:
            var_name = "?"
        displaytext = f"{var_name}"
    elif tag == "Case":
        value = node.attrib.get("caseValue", "?")
        displaytext = value



    elif tag == "Set":
        set_type = node.attrib.get("type", "")
        
        if set_type == "NoAction":
            tcp_elem = node.find("tcp")
            tcp_name = "?"
            if tcp_elem is not None:
                if "referencedName" in tcp_elem.attrib:
                    tcp_name = tcp_elem.attrib["referencedName"]
                elif "reference" in tcp_elem.attrib:
                    ref = tcp_elem.attrib["reference"]
                    try:
                        resolved = tcp_elem.xpath(ref)
                        if resolved:
                            tcp_name = resolved[0].attrib.get("referencedName", "?")
                    except Exception as e:
                        tcp_name = f"(XPath error: {e})"
            displaytext = f"Set TCP: {tcp_name}"

        elif set_type == "DigitalOutput":
            pin_elem = node.find("pin")
            val_elem = node.find("digitalValue")

            pin_name = "?"
            if pin_elem is not None:
                if "referencedName" in pin_elem.attrib:
                    pin_name = pin_elem.attrib["referencedName"]
                elif "reference" in pin_elem.attrib:
                    ref = pin_elem.attrib["reference"]
                    try:
                        resolved = pin_elem.xpath(ref)
                        if resolved:
                            pin_name = resolved[0].attrib.get("referencedName", "?")
                    except Exception as e:
                        pin_name = f"(XPath error: {e})"

            value = val_elem.text.strip() if val_elem is not None and val_elem.text else "?"
            displaytext = f"{pin_name} = {value}"




    elif tag == "Timer":
        action = node.attrib.get("action", "?")
        var_elem = node.find(".//variable")
        if var_elem is not None:
            timer_name = var_elem.attrib.get("name")
            if timer_name is None and "reference" in var_elem.attrib:
                timer_name = resolve_variable_name_from_reference(var_elem)
            if timer_name is None:
                timer_name = "?"
        else:
            timer_name = "?"
        displaytext = f"{action} Timer: {timer_name}"
    elif tag == "Popup":
        message = node.attrib.get("message", "?")
        displaytext = message

    else:
        displaytext = name or ""

    if tag != "InitVariablesNode" and not children:
        children = [
            parsed for child in node.findall("./children/*")
            if (parsed := parse_node_structured(child, root, depth + 1)) is not None
        ]


    return {
        "type": tag,
        "displaytext": displaytext,
        "depth": depth,
        "children": children
    }