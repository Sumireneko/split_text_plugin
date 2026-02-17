# ======================================
# Krita text split plug-in v0.7
# ======================================
# Copyright (C) 2025 L.Sumireneko.M
# This program is free software: you can redistribute it and/or modify it under the 
# terms of the GNU General Public License as published by the Free Software Foundation,
# either version 3 of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.

# You should have received a copy of the GNU General Public License along with this program.
# If not, see <https://www.gnu.org/licenses/>. 


# v0.7 : Qt6 / Qt5 Compatible(alpha)

import xml.etree.ElementTree as ET
import re, math, time

import krita
from krita import *
from .qt_compat import qt_exec,QC
from .qt_compat import (
    QEvent, QColor, QPalette, 
    QDialog, QVBoxLayout, QSlider, QSpinBox, 
    QPushButton, QColorDialog, QMessageBox
)

def clone_without(element, remove_keys=("x", "y", "dy")):
    """
    Remove (x, y, dy) attribute,and the element make to cloning with recursive
    """
    new_el = ET.Element(element.tag)
    for k, v in element.attrib.items():
        if k not in remove_keys:
            new_el.set(k, v)
    new_el.text = element.text
    for child in element:
        cloned_child = clone_without(child, remove_keys)
        new_el.append(cloned_child)
        if child.tail:
            if cloned_child.tail:
                cloned_child.tail += child.tail
            else:
                cloned_child.tail = child.tail
    return new_el

def convert_to_pt(value, unit, base_font_size=12):
    """
    Conversion unit -> pt 
    - value: number
    - unit:  (pt, em, ex, %, lines, px, mm, cm, Q, in, pc)
    - base_font_size: default 12pt
    """
    #print(f"{value} : {unit}")
    if value is None or unit is None:
        raise ValueError("Value or unit cannot be None")

    if not isinstance(value, (int, float)):
        raise TypeError("Value must be a number")

    unit = str(unit).lower()  # Px -> px , PT ->pt  convert to lowercase

    conversion_rates = {
        "pt": 1,
        "em": base_font_size,
        "ex": base_font_size * 0.5,  # x-height
        "%": base_font_size / 100,
        "lines": base_font_size,
        "px": 1, #0.75,  # 1px = 0.75pt
        "mm": 2.83465,  # 1mm = 2.83465pt
        "cm": 28.3465,  # 1cm = 28.3465pt
        "q": 0.709,  # 1Q = 0.709pt
        "in": 72,  # 1in = 72pt
        "pc": 12,  # 1pc = 12pt
    }

    if unit in conversion_rates:
        return value * conversion_rates[unit]
    else:
        raise ValueError(f"Unsuppored unit: {unit}")


def convert_pt_to_unit(value, unit, base_font_size=12):
    """
    Conversion pt -> unit 
    - value: number
    - unit:  (pt, em, ex, %, lines, px, mm, cm, Q, in, pc)
    - base_font_size: default 12pt
    """

    if value is None or unit is None:
        raise ValueError("Value or unit cannot be None")

    if not isinstance(value, (int, float)):
        raise TypeError("Value must be a number")

    unit = str(unit).lower() 

    # fallback： value
    value = value if value >= 0 else 12.0

    conversion_rates = {
        "pt": 1,
        "em": 1 / safe_base_font_size,
        "ex": 2 / safe_base_font_size,  # x-height
        "%": 100 / safe_base_font_size,
        "lines": 1 / safe_base_font_size,
        "px": 1, # 1 / 0.75,  # 1pt = ca1.333px
        "mm": 1 / 2.83465,  # 1pt = ca0.3528mm
        "cm": 1 / 28.3465,  # 1pt = ca0.0353cm
        "q": 1 / 0.709,  # 1pt = ca1.41Q
        "in": 1 / 72,  # 1pt = ca0.0139in
        "pc": 1 / 12,  # 1pt = ca0.0833pc
    }

    if unit in conversion_rates:
        return value * conversion_rates[unit]
    else:
        raise ValueError(f"Undefined unit: {unit}")

def parse_css_property(root, key, default_value=12.0, default_unit="pt"):
    """
    The helper function, general-purpose CSS property and unit getter 

    Parameters:
        root: node(it has attrib dictionary）
        key: property name (Ex: "font-size", "line-height")
        default_value: (Ex: 12.0)
        default_unit:  (Ex: "pt")
    
    Returns:
        Tuple (value, unit) float,string(all lower cases)f
    """
    value, unit = None, None

    # get from attrib directly(for no unit)
    if key in root.attrib:
        try:
            value = float(root.attrib[key])
        except ValueError:
            value = default_value

    # Extract by regular expression from style attribute
    if value is None and "style" in root.attrib:
        # For example "font-size: 14px" or "line-height: 1.2em"
        pattern = rf'{key}:\s*([\d.]+)([a-zA-Z%]+)?'
        m = re.search(pattern, root.attrib["style"])
        if m:
            try:
                value = float(m.group(1))
            except ValueError:
                value = default_value
            # Use default_unit
            unit = m.group(2) if m.group(2) is not None else default_unit

    # Fallback routine: if value <= 0 or None,then set default_value to it
    # Remove unnessesary white spaces and change to lower case）
    if value is None or value <= 0:
        value = default_value
    unit = (unit or default_unit).strip().lower()

    return value, unit

def split_txt(shape):
    # get SVG data and debug 
    svg_data = shape.toSvg()
    #print("original:")
    #print(svg_data)
    
    # get absolute transformation 
    absolute_transform = shape.absoluteTransformation()
    abst_mat = qtransform_to_svg_transform(absolute_transform)
    #print("Absolute transform:", abst_mat)

    # each <text> elements use local coordinate(0 0) 
    transform_attr = abst_mat  # Ex: "matrix(1.0 0.0 0.0 1.0 tx ty)"
    
    # Use transform attribute so (0,0)
    base_x = 0
    base_y = 0
    
    # In XML perser, make SVG data(<text> element)
    try:
        root = ET.fromstring(svg_data)
    except ET.ParseError as e:
        print("XML Parse Error:", e)
        return ""
    
    # remove x, y, font-size  and keep others form original <text> element
    preserved_attribs = {}
    preserved_attribs = dict(root.attrib)

    font_size = None
    font_unit = None
    line_shift = None
    line_shift_unit = None

    font_size, font_unit = parse_css_property(root, "font-size", 12.0, "pt")
    #print("font-size =", font_size, ", font_unit =", font_unit)  # → 16, "pt"

    line_shift, line_shift_unit = parse_css_property(root, "line-height", font_size, "pt")
    #print("line-height =", line_shift, ", line-height unit =", line_shift_unit)  # → 12.0, "pt"

    # if vertical text, add  writing-mode to style attribute(if already it extist)

    if preserved_attribs.get("writing-mode") is None:
        preserved_attribs["writing-mode"] = "horizontal-tb"
    writing_mode = preserved_attribs["writing-mode"]


    if font_unit != "pt":
        #print("font_unit_process:")
        font_size = convert_to_pt(font_size, font_unit, base_font_size=font_size)
 
    if line_shift_unit != "pt":
        #print("line_shift_unit_process:")
        line_shift = convert_to_pt(line_shift, line_shift_unit, base_font_size=font_size or 12.0)


    # Generate new <text> element per each line (or each <tspan> segments)
    new_text_elements = []
    if writing_mode == "horizontal-tb":
        cumulative_offset = 0.0  # y direction  
    else:
        cumulative_offset = 0.0  # x direction

    # If exist plain text at <text>,generate each line by split with line break
    if root.text and root.text.strip():
        lines = [line.strip() for line in root.text.strip().splitlines() if line.strip()]
        for line in lines:
            cumulative_offset += line_shift#font_size
            new_text_node = ET.Element("text", {
                "transform": transform_attr,
                "font-size": str(line_shift)#font_size
            })
            for k, v in preserved_attribs.items():
                new_text_node.set(k, v)
            if writing_mode == "horizontal-tb":
                new_text_node.set("x", str(base_x))
                new_text_node.set("y", str(cumulative_offset))
            else:
                new_text_node.set("x", str(cumulative_offset* (-1 if writing_mode == "vertical-rl" else 1)   ))
                new_text_node.set("y", str(base_y))
            new_text_node.text = line
            new_text_elements.append(new_text_node)
    
    # The chilren elements <tspan>
    for child in root:
        if child.tag != "tspan":
            continue
        # Get the value from dy attribute itself,if not font size.
        dy_val = child.attrib.get("dy")
        try:
            increment = float(dy_val) if dy_val is not None else font_size
        except Exception:
            increment = font_size
        cumulative_offset += increment
        
        new_text_node = ET.Element("text", {
            "transform": transform_attr,
            "font-size": str(font_size)
        })
        for k, v in preserved_attribs.items():
            new_text_node.set(k, v)
        if writing_mode == "horizontal-tb":
            new_text_node.set("x", str(base_x))
            new_text_node.set("y", str(cumulative_offset))
        else:
            new_text_node.set("x", str(cumulative_offset * (-1 if writing_mode == "vertical-rl" else 1)  ))
            new_text_node.set("y", str(base_y))
        
        # Remove unused attribute of <tspan> element, and it makes clone
        new_tspan = clone_without(child, remove_keys=("x", "y", "dy"))
        #print("----Dump -----")
        #ET.dump(new_text_node) 
        #print("----↑ rawdata -----")
        if new_tspan.text:
            new_tspan.text = new_tspan.text.rstrip("\n")  # At first for parent text

        for tspan in new_tspan.findall(".//tspan"):
            if tspan.text:
                tspan.text = tspan.text.rstrip("\n")  # for nested <tspan> text
        
            if tspan.tail:
                tspan.tail = tspan.tail.rstrip("\n")  # remove tail(tag after) line brake 

        #ET.dump(new_text_node)
        #print("----↑ tspan.restrip -----")

        #print("-----------")
        new_text_node.append(new_tspan)
        #print(f"child.tail : {repr(child.tail)}")
        if child.tail and child.tail.strip():
            extra_tspan = ET.Element("tspan")
            extra_tspan.text = child.tail.strip()
            new_text_node.append(extra_tspan)
        
        new_text_elements.append(new_text_node)
    
    # return contents as each <text> elements
    result_parts = [ET.tostring(elem, encoding="unicode") for elem in new_text_elements]
    result = "\n".join(result_parts)


    if result.endswith('\n'):
        #print("LineBreak Detect")
        result = result.rstrip('\n')  # remove it

    return result

def qtransform_to_svg_transform(transform):
    return f"matrix({transform.m11()} {transform.m12()} {transform.m21()} {transform.m22()} {transform.m31()} {transform.m32()})"

# -------
# main
# -------

def main():
    app = Krita.instance()
    doc = app.activeDocument()
    view = app.activeWindow().activeView()
    selected_vector_layer = view.selectedNodes()
    
    
    # Set corrected scaling. 1pt = 72 dpi
    wpt = doc.width()*0.72
    hpt = doc.height()*0.72
    svg_scale = f' width="{wpt}pt" height="{hpt}pt" viewBox="0 0 {wpt} {hpt}" '
    
    output_shapes = []
    rm_shapes = []
    target_layer = None
    # Get selected shapes and apply path effect to the shapes
    for node in selected_vector_layer:
        if node.type() == "vectorlayer":
            shapes = node.shapes()
            target_layer = node
            for shape in shapes:
                if shape.isSelected():
                    # main (get an output_element string)
                    #print()
                    output_elements = split_txt(shape)

                    #print(output_elements)
                    rm_shapes.append(shape)
                    # When adding to Krita vector layer, you don't need to describes the DTD or XMLNS parts.
                    output_shapes.append("<svg "+svg_scale+">"+output_elements+"</svg>")


    app.action('InteractionTool').trigger()
    #print()
    if len(output_shapes) > 0:
        # Add shapes to the layer 
        for s in rm_shapes:s.remove()
        for s in output_shapes:
            target_layer.addShapesFromSvg(s)
        
    notice_autoclose_dialog('The Text were splited')

# ====================
# Utilities
# ====================

def message(mes):
    mb = QMessageBox()
    mb.setText(str(mes))
    mb.setWindowTitle('Message')
    mb.setStandardButtons(QC.StdBtn.Ok) 
    
    ret = qt_exec(mb) 

    if ret == QC.StdBtn.Ok:
        pass # OK clicked


# create dialog  and show it
def notice_autoclose_dialog(message_text):
    app = Krita.instance()
    qwin = app.activeWindow().qwindow()
    qq = qwin.size()
    
    wpos = math.ceil(qq.width() * 0.45)
    hpos = math.ceil(qq.height() * 0.45)

    noticeDialog = QDialog()

    noticeDialog.setWindowFlags(QC.Window.FramelessWindowHint)

    label = QLabel(message_text)
    hboxd = QHBoxLayout()
    hboxd.addWidget(label)
    noticeDialog.setLayout(hboxd)
    noticeDialog.setWindowTitle("Title")

    noticeDialog.move(qwin.x() + wpos, qwin.y() + hpos)
    
    # Close window
    QtCore.QTimer.singleShot(1500, noticeDialog.close)

    qt_exec(noticeDialog)



# ====================
# Main class
# ====================

class split_text(Extension):

    def __init__(self, parent):
        # This is initialising the parent, always important when subclassing.
        super().__init__(parent)

    def setup(self):
        #This runs only once when app is installed
        pass

    def createActions(self, window):

        action = window.createAction("split_text", "Split the multi line text", "tools/scripts")
        action.triggered.connect(main)

        pass


Krita.instance().addExtension(split_text(Krita.instance()))