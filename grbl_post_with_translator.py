#***************************************************************************
#*   (c) sliptonic (shopinthewoods@gmail.com) 2014                        *
#*                                                                         *
#*   This file is part of the FreeCAD CAx development system.              *
#*                                                                         *
#*   This program is free software; you can redistribute it and/or modify  *
#*   it under the terms of the GNU Lesser General Public License (LGPL)    *
#*   as published by the Free Software Foundation; either version 2 of     *
#*   the License, or (at your option) any later version.                   *
#*   for detail see the LICENCE text file.                                 *
#*                                                                         *
#*   FreeCAD is distributed in the hope that it will be useful,            *
#*   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
#*   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
#*   GNU Lesser General Public License for more details.                   *
#*                                                                         *
#*   You should have received a copy of the GNU Library General Public     *
#*   License along with FreeCAD; if not, write to the Free Software        *
#*   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
#*   USA                                                                   *
#*                                                                         *
#***************************************************************************/


TOOLTIP='''
Generate g-code from a Path that is compatible with the grbl controller.

import grbl_post
grbl_post.export(object,"/path/to/file.ncc")
'''

import FreeCAD
import PathScripts.PostUtils as PostUtils
import argparse
import datetime
import shlex


now = datetime.datetime.now()

parser = argparse.ArgumentParser(prog='grbl', add_help=False)
parser.add_argument('--header', action='store_true', help='output headers (default)')
parser.add_argument('--no-header', action='store_true', help='suppress header output')
parser.add_argument('--comments', action='store_true', help='output comment (default)')
parser.add_argument('--no-comments', action='store_true', help='suppress comment output')
parser.add_argument('--line-numbers', action='store_true', help='prefix with line numbers')
parser.add_argument('--no-line-numbers', action='store_true', help='don\'t prefix with line numbers (default)')
parser.add_argument('--show-editor', action='store_true', help='pop up editor before writing output (default)')
parser.add_argument('--no-show-editor', action='store_true', help='don\'t pop up editor before writing output')
parser.add_argument('--precision', default='3', help='number of digits of precision, default=3')
parser.add_argument('--preamble', help='set commands to be issued before the first command, default="G17\nG90"')
parser.add_argument('--postamble', help='set commands to be issued after the last command, default="M05\nG17 G90\n; M2"')
parser.add_argument('--translate_drill', action='store_true', help='translate drill cycles G81, G82 & G83 in G0/G1 movements (default)')
parser.add_argument('--no-translate_drill', action='store_true', help='don\'t translate drill cycles G81, G82 & G83 in G0/G1 movements')

TOOLTIP_ARGS=parser.format_help()

#These globals set common customization preferences
OUTPUT_COMMENTS = True
OUTPUT_HEADER = True
OUTPUT_LINE_NUMBERS = False
OUTPUT_TOOL_CHANGE = False
SHOW_EDITOR = True
MODAL = False #if true commands are suppressed if the same as previous line.
COMMAND_SPACE = " "
LINENR = 100 #line number starting value

TRANSLATE_DRILL_CYCLES = True # If true, G81, G82 & G83 are translated in G0/G1 moves
DRILL_RETRACT_MODE = 'G98'    # Default value of drill retractations (OLD_Z) other possible value is G99
OLD_X = None
OLD_Y = None
OLD_Z = None
MOTION_MODE = 'G90'

#These globals will be reflected in the Machine configuration of the project
UNITS = "G21"  #G21 for metric, G20 for us standard
MACHINE_NAME = "GRBL"
CORNER_MIN = {'x':0, 'y':0, 'z':0 }
CORNER_MAX = {'x':500, 'y':300, 'z':300 }
PRECISION = 3 # Default precision for metric (see http://linuxcnc.org/docs/2.7/html/gcode/overview.html#_g_code_best_practices)

RAPID_MOVES = ['G0', 'G00']

#Preamble text will appear at the beginning of the GCODE output file.
PREAMBLE = '''G17 G90
'''

#Postamble text will appear following the last operation.
POSTAMBLE = '''M5
G17 G90
M2
'''

# These commands are ignored by commenting them out
SUPPRESS_COMMANDS = [ 'G98', 'G80' ]

#Pre operation text will be inserted before every operation
PRE_OPERATION = ''''''

#Post operation text will be inserted after every operation
POST_OPERATION = ''''''

#Tool Change commands will be inserted before a tool change
TOOL_CHANGE = ''''''


# to distinguish python built-in open function from the one declared below
if open.__module__ == '__builtin__':
    pythonopen = open


def processArguments(argstring):
    global OUTPUT_HEADER
    global OUTPUT_COMMENTS
    global OUTPUT_LINE_NUMBERS
    global SHOW_EDITOR
    global PRECISION
    global PREAMBLE
    global POSTAMBLE
    global TRANSLATE_DRILL_CYCLES

    try:
        args = parser.parse_args(shlex.split(argstring))
        if args.no_header:
            OUTPUT_HEADER = False
        if args.header:
            OUTPUT_HEADER = True
        if args.no_comments:
            OUTPUT_COMMENTS = False
        if args.comments:
            OUTPUT_COMMENTS = True
        if args.no_line_numbers:
            OUTPUT_LINE_NUMBERS = False
        if args.line_numbers:
            OUTPUT_LINE_NUMBERS = True
        if args.no_show_editor:
            SHOW_EDITOR = False
        if args.show_editor:
            SHOW_EDITOR = True
        print("Show editor = %d" % SHOW_EDITOR)
        PRECISION = args.precision
        if args.preamble is not None:
            PREAMBLE = args.preamble
        if args.postamble is not None:
            POSTAMBLE = args.postamble
        if args.no_translate_drill:
            TRANSLATE_DRILL_CYCLES = False
        if args.translate_drill:
            TRANSLATE_DRILL_CYCLES = True
        print("Translate drill cycles = %r" % TRANSLATE_DRILL_CYCLES)
    except:
        return False

    return True

# Pour debug... 
def dump(obj):
    for attr in dir(obj):
        print("obj.%s = %s" % (attr, getattr(obj, attr)))

def export(objectslist,filename,argstring):
    if not processArguments(argstring):
        return None

    global UNITS
    
    for obj in objectslist:
	
        # Debug...
		#print("\n" + "*"*70)
        #dump(obj)
        #print("*"*70 + "\n")
		
        if not hasattr(obj,"Path"):
            print "the object " + obj.Name + " is not a path. Please select only path and Compounds."
            return

    print "postprocessing..."
    gcode = ""

    # Machine object seems to be no more supported in FreeCAD/Path
    ### Find the machine.
    ### The user my have overridden post processor defaults in the GUI.  
    ### Make sure we're using the current values in the Machine Def.
    ##myMachine = None
    ##for pathobj in objectslist:
    ##    if hasattr(pathobj,"Group"): #We have a compound or project.
    ##        for p in pathobj.Group:
    ##            if p.Name == "Machine":
    ##                myMachine = p
    ##if myMachine is None:
    ##    print "No machine found in this project"
    ##else:
    ##    if myMachine.MachineUnits == "Metric":
    ##       UNITS = "G21"
    ##    else:
    ##       UNITS = "G20"

    # write header
    if OUTPUT_HEADER:
        gcode += linenumber() + "(Exported by FreeCAD)\n"
        gcode += linenumber() + "(Post Processor: " + __name__ +")\n"
        gcode += linenumber() + "(Output Time:"+str(now)+")\n"

    #Write the preamble
    if OUTPUT_COMMENTS: gcode += linenumber() + "(begin preamble)\n"
    for line in PREAMBLE.splitlines(True):
        gcode += linenumber() + line
    gcode += linenumber() + UNITS + "\n"

    for obj in objectslist:

        #do the pre_op
        if OUTPUT_COMMENTS: gcode += linenumber() + "(begin operation: " + obj.Label + ")\n"
        for line in PRE_OPERATION.splitlines(True):
            gcode += linenumber() + line

        gcode += parse(obj)

        #do the post_op
        if OUTPUT_COMMENTS: gcode += linenumber() + "(finish operation: " + obj.Label + ")\n"
        for line in POST_OPERATION.splitlines(True):
            gcode += linenumber() + line

    #do the post_amble

    if OUTPUT_COMMENTS: gcode += linenumber() + "(begin postamble)\n"
    for line in POSTAMBLE.splitlines(True):
        gcode += linenumber() + line

    if FreeCAD.GuiUp and SHOW_EDITOR:
        dia = PostUtils.GCodeEditorDialog()
        dia.editor.setText(gcode)
        result = dia.exec_()
        if result:
            final = dia.editor.toPlainText()
        else:
            final = gcode
    else:
        final = gcode

    print "done postprocessing."

    gfile = pythonopen(filename,"wb")
    gfile.write(gcode)
    gfile.close()


def linenumber():
    global LINENR
    if OUTPUT_LINE_NUMBERS == True:
        LINENR += 10
        return "N" + str(LINENR) + " "
        print(str(LINENR))
    return ""

def format_outstring(strTbl):
    global COMMAND_SPACE
    # construct the line for the final output
    s = ""
    for w in strTbl:
        s += w + COMMAND_SPACE
    s = s.strip()
    return s

def parse(pathobj):
    global DRILL_RETRACT_MODE
    global MOTION_MODE
    global OLD_X
    global OLD_Y
    global OLD_Z
    out = ""
    lastcommand = None
    precision_string = '.' + str(PRECISION) +'f'

    #params = ['X','Y','Z','A','B','I','J','K','F','S'] #This list control the order of parameters
    params = ['X','Y','Z','A','B','I','J','F','S','T','Q','R','L','P'] #linuxcnc doesn't want K properties on XY plane  Arcs need work.

    if hasattr(pathobj,"Group"): #We have a compound or project.
        if OUTPUT_COMMENTS: out += linenumber() + "(compound: " + pathobj.Label + ")\n"
        for p in pathobj.Group:
            out += parse(p)
        return out
    else: #parsing simple path

        if not hasattr(pathobj,"Path"): #groups might contain non-path things like stock.
            return out

        if OUTPUT_COMMENTS: out += linenumber() + "(Path: " + pathobj.Label + ")\n"

        for c in pathobj.Path.Commands:
            outstring = []
            command = c.Name
            ###print("Commande = [%s]" % c)

            outstring.append(command)
            # if modal: only print the command if it is not the same as the last one
            if MODAL == True:
                if command == lastcommand:
                    outstring.pop(0)

            # Now add the remaining parameters in order
            for param in params:
                if param in c.Parameters:
                    if param == 'F':
                        if command not in RAPID_MOVES:
                            outstring.append(param + format(c.Parameters['F'], '.2f'))
                    elif param == 'T':
                        outstring.append(param + str(c.Parameters['T']))
                    else:
                        outstring.append(param + format(c.Parameters[param], precision_string))

            # store the latest command
            lastcommand = command

            if command in ('G98', 'G99'):
                DRILL_RETRACT_MODE = command

            if command in ('G90', 'G91'):
                MOTION_MODE = command

            if TRANSLATE_DRILL_CYCLES:
                if command in ('G81', 'G82', 'G83'):
                    out += drill_translate(outstring, command, c.Parameters)
                    # Efface la ligne que l'on vient de translater
                    del(outstring[:])
                    outstring = []
                                
                # Memorise la position courante pour calcul des mouvements relatis et du plan de retrait
                for p in c.Parameters:
                    if p == 'X':
                        OLD_X = c.Parameters['X']
                    if p == 'Y':
                        OLD_Y = c.Parameters['Y']
                    if p == 'Z':
                        OLD_Z = c.Parameters['Z']

            # Check for Tool Change:
            if command == 'M6':
                if OUTPUT_COMMENTS: out += linenumber() + "(begin toolchange)\n"
                if not OUTPUT_TOOL_CHANGE:
                    outstring.insert(0, ";")
                else:
                    for line in TOOL_CHANGE.splitlines(True):
                        out += linenumber() + line

            if command == "message":
                if OUTPUT_COMMENTS == False:
                    out = []
                else:
                    outstring.pop(0) #remove the command

            if command in SUPPRESS_COMMANDS:
                outstring.insert(0, ";")

            #prepend a line number and append a newline
            if len(outstring) >= 1:
                out += linenumber() + format_outstring(outstring) + "\n"

        return out

def drill_translate(outstring, cmd, params):
    global DRILL_RETRACT_MODE
    global MOTION_MODE
    global OLD_X
    global OLD_Y
    global OLD_Z

    # Console debug
    print("Translating command %s" % format_outstring(outstring))

    strFormat = '.' + str(PRECISION) +'f'
    
    if OUTPUT_COMMENTS: # Comment the original command
        outstring[0] = '(' + outstring[0]   
        outstring[-1] = outstring[-1] + ')'
        trBuff = linenumber() + format_outstring(outstring) + "\n"
    else:
        trBuff = ""

    # Conversion du cycle
    # Pour l'instant, on gere uniquement les cycles dans le plan XY (G17) 
    # les autres plans ZX (G18) et YZ (G19) ne sont pas traites : Calculs sur Z uniquement.
    
    if MOTION_MODE == 'G90': # Deplacements en coordonnees absolues
        drill_X = params['X']
        drill_Y = params['Y']
        drill_Z = params['Z']
        RETRACT_Z = params['R']
    else: # G91 Deplacements relatifs
        drill_X = OLD_X + params['X']
        drill_Y = OLD_Y + params['Y']
        drill_Z = OLD_Z + params['Z']
        RETRACT_Z = params['R'] + OLD_Z
    
    if DRILL_RETRACT_MODE == 'G98' and OLD_Z >= RETRACT_Z:
        RETRACT_Z = OLD_Z

    # Recupere les valeurs des autres parametres
    drill_Speed = params['F']
    if cmd == 'G83':
        drill_Step = params['Q']
    elif cmd == 'G82':
        drill_DwellTime = params['P']

    if MOTION_MODE == 'G91':
        trBuff += linenumber() + "G90" + "\n" # Force des deplacements en coordonnees absolues pendant les cycles

    # Mouvement(s) preliminaire(s))
    if OLD_Z < RETRACT_Z:
        trBuff += linenumber() + 'G0 Z' + format(RETRACT_Z, strFormat) + "\n"
    trBuff += linenumber() + 'G0 X' + format(drill_X, strFormat) + ' Y' + format(drill_Y, strFormat) + "\n"
    if OLD_Z > RETRACT_Z:
        trBuff += linenumber() + 'G0 Z' + format(OLD_Z, strFormat) + "\n"

    # Mouvement de percage
    if cmd in ('G81', 'G82'):
        trBuff += linenumber() + 'G1 Z' + format(drill_Z, strFormat) + ' F' + format(drill_Speed, '.2f') + "\n"
        # Temporisation eventuelle
        if cmd == 'G82':
            trBuff += linenumber() + 'G4 P' + str(drill_DwellTime) + "\n"
        # Sortie de percage
        trBuff += linenumber() + 'G0 Z' + format(RETRACT_Z, strFormat) + "\n"
    else: # 'G83'
        next_Stop_Z = RETRACT_Z - drill_Step
        while 1:
            if next_Stop_Z > drill_Z:
                trBuff += linenumber() + 'G1 Z' + format(next_Stop_Z, strFormat) + ' F' + format(drill_Speed, '.2f') + "\n"
                trBuff += linenumber() + 'G0 Z' + format(RETRACT_Z, strFormat) + "\n"
                next_Stop_Z -= drill_Step
            else:
                trBuff += linenumber() + 'G1 Z' + format(drill_Z, strFormat) + ' F' + format(drill_Speed, '.2f') + "\n"
                trBuff += linenumber() + 'G0 Z' + format(RETRACT_Z, strFormat) + "\n"
                break

    if MOTION_MODE == 'G91':
        trBuff += linenumber() + 'G91' # Restore le mode de deplacement relatif

    return trBuff

print __name__ + " gcode postprocessor loaded."
