# ======================================
# Krita text split plug-in v0.4
# ======================================
# Copyright (C) 2024 L.Sumireneko.M
# This program is free software: you can redistribute it and/or modify it under the 
# terms of the GNU General Public License as published by the Free Software Foundation,
# either version 3 of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.

# You should have received a copy of the GNU General Public License along with this program.
# If not, see <https://www.gnu.org/licenses/>. 

from krita import *
from PyQt5.QtWidgets import *
from PyQt5.Qt import *
from PyQt5.QtGui import *
from PyQt5 import QtCore
import re,math,time

def split_text_exe():

    app = Krita.instance()
    doc = app.activeDocument()
    lay = doc.activeNode()
    root = doc.rootNode()
    if lay.type() == 'vectorlayer':
        app.action('InteractionTool').trigger()# Select shape tool
        shapes = lay.shapes()
        #print(" "+str(len(shapes))+" shapes found in this active VectorLayer")
        
        selected_shapes = []
        #print("-- ↑ Front -- ") 
        
        # Get All shape info
        # Range = len()-1 .... 0 
        for i in range(len(shapes)-1,-1,-1):
            sp = shapes[i]
            #print(f'* Shape({i}), Name: {sp.name()}  ,Type: {sp.type()} , isSelected?: {sp.isSelected()} , ID :{sp} ')
            # Get the selected shape
            if sp.isSelected() == True:
                selected_shapes.append(sp)
        #print("-- ↓ Back -- ")
        
        #print(" ")
        #print(f" {len(selected_shapes)} / {len(shapes)} shapes selected")

        # get documentsize px → pt
        wpt = doc.width()*0.72
        hpt = doc.height()*0.72

        # Detail of the selected shapes
        add_shapes=[]
        org_shapes=[]
        sel_ids=[]
        for j in range(len(selected_shapes)-1,-1,-1):
            s = selected_shapes[j]
            type = s.type()
            if type != 'KoSvgTextShapeID':continue
            org_shapes.append(s)
            s.update()
            xy=s.position().toPoint()
            base_y=xy.y()
            base_x=xy.x()
            #print("Pos",str(xy.y()))
            stxt = s.toSvg()
            tx_comp = stxt.split('<tspan ')
            # 0:<text , 1 ...2... tspan , last </text>
            new_base=base_style=""
            for n in range(0, len(tx_comp)):
                # print(tx_comp[n])
                dy=0;fi=st=new_text=""
                # text
                if n == 0:
                    new_base=tx_comp[n]
                    new_base=new_base[:-1]# delete last string for add attibute
                    base_style=re.search(r'(style=".*?")',tx_comp[n])
                    if base_style:
                        base_style=base_style.group(1);
                        new_base=new_base.replace(base_style,'')
                        base_style=base_style[:-1] # delete last string for add style
                    pass
                # tspan 
                d_srch = re.search(r'dy="(.*?)"',tx_comp[n])
                f_srch = re.search(r'(fill=".*?")',tx_comp[n])
                s_srch = re.search(r'style="(.*?)"',tx_comp[n])
                t_srch = re.search(r'>(.*?)<',tx_comp[n])
                if d_srch:dy=float(d_srch.group(1));#print("*Detect*",d_srch.group(1))
                if f_srch:fi=f_srch.group(1);#print("*Detect*",f_srch.group(1))
                if s_srch:st=s_srch.group(1);#print("*Detect*",s_srch.group(1))
                if t_srch:new_text=t_srch.group(1);#print("*Detect*",t_srch.group(1))
                base_y=float(base_y)+float(dy)


                newSVG = new_base+f' transform="translate({base_x},{base_y})" '+base_style+st+'" '+fi+'><tspan x="0">'+new_text+'</tspan></text>'
                #print(" ------------------ ")
                #print(newSVG)
                add_shapes.append(newSVG)

            #print(" ------------------ ")
            #print(f'* Shape({j}), Type:{type} , \n '+s.toSvg())

        # Add split texts and delete original texts 
        app.action('InteractionTool').trigger()
        if len(add_shapes) > 0:
            for s in org_shapes:s.remove()
            for l in add_shapes:
                lay.addShapesFromSvg(f'<svg width="{wpt}pt" height="{hpt}pt" viewBox="0 0 {wpt} {hpt}">{l}</svg>')

            # Re-Selection
            """
            updated_shapes = lay.shapes()
            message(str(sel_ids))
            for j in updated_shapes:
                if j.type() != 'KoSvgTextShapeID':continue
                shape = j.toSvg()
                i_srch = re.search(r'id\s?=\s?"(.*?)"',shape)
                if i_srch:
                    id=i_srch.group(1);
                    message(id)
                    if id in sel_ids:
                        j.select()
            """
            notice_autoclose_dialog('The Text were splited')

# ====================
# Utilities
# ====================

def message(mes):
    mb = QMessageBox()
    mb.setText(str(mes))
    mb.setWindowTitle('Message')
    mb.setStandardButtons(QMessageBox.Ok)
    ret = mb.exec()
    if ret == QMessageBox.Ok:
        pass # OK clicked


# create dialog  and show it
def notice_autoclose_dialog(message):
    app = Krita.instance()
    qwin = app.activeWindow().qwindow()
    qq = qwin.size()
    wpos = math.ceil(qq.width() * 0.45)
    hpos = math.ceil(qq.height() * 0.45)
    
    noticeDialog = QDialog() 
    noticeDialog.setWindowFlags(QtCore.Qt.FramelessWindowHint)
    label = QLabel(message)
    hboxd = QHBoxLayout()
    hboxd.addWidget(label)
    noticeDialog.setLayout(hboxd)
    noticeDialog.setWindowTitle("Title") 
    
    print(qwin.x(),wpos,hpos)
    noticeDialog.move(qwin.x()+wpos,qwin.y()+hpos)
    QtCore.QTimer.singleShot(1500, noticeDialog.close)
    noticeDialog.exec_() # show



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
        action.triggered.connect(split_text_exe)

        pass


