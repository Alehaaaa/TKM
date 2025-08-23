

'''

    TheKeyMachine - Animation Toolset for Maya Animators                                           
                                                                                                                                              
                                                                                                                                              
    This file is part of TheKeyMachine, an open source software for Autodesk Maya licensed under the GNU General Public License v3.0 (GPL-3.0).                                           
    You are free to use, modify, and distribute this code under the terms of the GPL-3.0 license.                                              
    By using this code, you agree to keep it open source and share any modifications.                                                          
    This code is provided "as is," without any warranty. For the full license text, visit https://www.gnu.org/licenses/gpl-3.0.html

    thekeymachine.xyz / x@thekeymachine.xyz                                                                                                                                        
                                                                                                                                              
    Developed by: Rodrigo Torres / rodritorres.com                                                                                             
    Modified by: Alehaaaa / alehaaaa.github.io                                                                                                 
                                                                                                                                             




	EDITING THIS FILE INCORRECTLY CAN LEAD TO A CRITICAL ERROR IN THEKEYMACHINE,
	PLEASE CONSULT THE HELP PAGE TO UNDERSTAND HOW TO MODIFY THIS FILE CORRECTLY

	https://thekeymachine.gitbook.io/base/the-toolbar/custom-menus





	With this tool, you can create a custom menu that will be accessible from TheKeyMachine's toolbar.
	To add entries to the menu, you need to edit the different blocks you'll see below.
	Here's a brief description of how to do it:
	
	1)	name:		The menu item name. If name is "separator" the entry will be a separator line.
	2)	image:		** See images note bellow
	3)	is_python:	'True' if you are using a python script or 'False' if you are using mel script.
	4)	command:	Paste or write your code here. 
	5)	tool_order:	Enter the exact same name here that you put in the blocks. Put the order you want. 


	Images:
	You can use any Maya internal icon or the following internal TheKeyMachine images:

	green_dot.png
	blue_dot.png
	red_dot.png
	yellow_dot.png
	grey_dot.png


'''

# menu order __________________________________________________________________________________________


tool_order = ["Demo tool 01", "separator", "Demo tool 02", "", "", "", "", "", "", ""]


# t01 _________________________________________________________________________________________________



t01_name = "Demo tool 01"
t01_image = "yellow_dot.png"
t01_is_python = True
t01_command = '''

import maya.cmds as cmds
cmds.warning("Demo tool 01 code executed")

'''




# t02 _________________________________________________________________________________________________



t02_name = "Demo tool 02"
t02_image = "blue_dot.png"
t02_is_python = True
t02_command ='''

import maya.cmds as cmds
cmds.warning("Demo tool 02 code executed")

'''




# t03 _________________________________________________________________________________________________



t03_name = "separator"
t03_image = ""
t03_is_python = True
t03_command = '''


'''




# t04 _________________________________________________________________________________________________



t04_name = ""
t04_image = ""
t04_is_python = True
t04_command = '''



'''




# t05 _________________________________________________________________________________________________



t05_name = ""
t05_image = ""
t05_is_python = True
t05_command = '''

'''





# t06 _________________________________________________________________________________________________

t06_name = ""
t06_image = ""
t06_is_python = False
t06_command = '''

'''




# t07 _________________________________________________________________________________________________

t07_name = ""
t07_image = ""
t07_is_python = True
t07_command = '''

'''



# t08 _________________________________________________________________________________________________

t08_name = ""
t08_image = ""
t08_is_python = True
t08_command = '''

'''



# t09 _________________________________________________________________________________________________

t09_name = ""
t09_image = ""
t09_is_python = True
t09_command = '''

'''



# t10 _________________________________________________________________________________________________

t10_name = ""
t10_image = ""
t10_is_python = True
t10_command = '''

'''