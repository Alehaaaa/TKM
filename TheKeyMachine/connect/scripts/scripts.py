
'''

    TheKeyMachine - Animation Toolset for Maya Animators                                           
                                                                                                                                              
                                                                                                                                              
    This file is part of TheKeyMachine, an open source software for Autodesk Maya licensed under the GNU General Public License v3.0 (GPL-3.0).                                           
    You are free to use, modify, and distribute this code under the terms of the GPL-3.0 license.                                              
    By using this code, you agree to keep it open source and share any modifications.                                                          
    This code is provided "as is," without any warranty. For the full license text, visit https://www.gnu.org/licenses/gpl-3.0.html

    thekeymachine.xyz / x@thekeymachine.xyz                                                                                                                                        
                                                                                                                                              
    Developed by: Rodrigo Torres / rodritorres.com                                                                                             
                                                                                                                                             





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


scripts_order = ["Demo script 01", "", "separator", "Demo script 02", "", "", "", "", "", ""]


# s01 _________________________________________________________________________________________________



s01_name = "Demo script 01"
s01_image = "green_dot.png"
s01_is_python = True
s01_command =  '''

import maya.cmds as cmds
cmds.warning("Demo script 01 code executed")


'''

 


# s02 _________________________________________________________________________________________________



s02_name = "Demo script 02"
s02_image = "blue_dot.png"
s02_is_python = True
s02_command = '''

import maya.cmds as cmds
cmds.warning("Demo script 02 code executed")


'''




# s03 _________________________________________________________________________________________________



s03_name = "separator"
s03_image = ""
s03_is_python = True
s03_command =  '''

'''




# s04 _________________________________________________________________________________________________



s04_name = ""
s04_image = ""
s04_is_python = True
s04_command =  '''

'''




# s05 _________________________________________________________________________________________________



s05_name = ""
s05_image = ""
s05_is_python = True
s05_command =  '''

'''




# s06 _________________________________________________________________________________________________

s06_name = ""
s06_image = ""
s06_is_python = True
s06_command =  '''

'''




# s07 _________________________________________________________________________________________________

s07_name = ""
s07_image = ""
s07_is_python = True
s07_command =  '''

'''




# s08 _________________________________________________________________________________________________

s08_name = ""
s08_image = ""
s08_is_python = True
s08_command = '''

'''




# s09 _________________________________________________________________________________________________

s09_name = ""
s09_image = ""
s09_is_python = True
s09_command =  '''

'''




# s10 _________________________________________________________________________________________________

s10_name = ""
s10_image = ""
s10_is_python = True
s10_command =  '''

'''