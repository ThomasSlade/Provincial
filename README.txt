Provincial 1.0
A toolset for faster map-creation workflow for Hearts of Iron IV.
Thomas Slade, 2020

Provincial is a collection of python scripts. To use it, place this package in whatever directory you like. Input and output files will, by default, need to be placed in the ‘Workspace’ folder in the same directory as the scripts.
You need python in order to run these scripts (at least version 3.8.2). You may run the scripts from command line, or you can use the python IDLE shell, which allows for quick edits of the script and a nicer-looking output log.

IF USING CMD
To run a script:
- Navigate to the root directory of this package with ‘cd’.
- Enter ‘py [filename]’ (filename must include the .py suffix)

IF USING IDLE
To run a script:
- Open the IDLE interpreter.
- File > Open > navigate to this package directory.
- Select the script which performs the operation you want. This will open the script’s source code (which is free to edit and tweak, if you need to).
- Hit ‘F5’ or go to Run > Run Module

PYTHON AND PACKAGES INSTALLATION
First, you'll need to set up python as a command-line variable if you have not already (see section 3.3.1 of https://docs.python.org/2/using/windows.html)
Unfortunately, I was not able to sort the required python packages into Provincial for a one-click installation, so for the scripts to work, you'll need some packages installed in addition to installing Python itself.
The required packages are:
- numpy 1.18.2 (or later)
- scipy 1.4.1 (or later)
- scimage 0.16.2 (or later)
I recommend using the pip package manager to quickly install these other packages (https://pip.pypa.io/en/stable/installing/)

INTRODUCTION: FILLPROVINCES AND VALIDATEMAP
Provincial provides the following utilities, each carried out by a particular script:
- provincialsettings.py – This is the only file you’ll definitely want to edit. It’s basically a config file. Change its values around to tweak what Provincial is doing. There are directory options, color-randomization options, options for overwriting state files, etc …
- fillprovinces.py – Takes an image that defines state and province borders, and fills out the provinces in block color (will also fill out the borders) with random, non-colliding colors. Province colors will be filled using the base ‘color palette’ of the state itself, making it easier to see which provinces belong to what when revising your province image. The purpose of this method is to reduce the province-creation to simply drawing province outlines, removing the tedium of filling them all in.
- validatemap.py – Searches a province map for ‘x-crossings’ (places where 4 different provinces meet), provinces that are too small, provinces that seem to be too spread out, and provinces that could not be filled automatically by fillprovinces.py. These are mostly issues that Hearts of Iron will flag in its startup, but this script displays a debug image showing the location of the discovered invalidities, and saves it as a validation map. This makes hunting down issues much faster.
- assignprovinces.py – Compares a state image (which may be your original border-image that fillprovinces.py filled out) to a province image, and assigns provinces to states based on which state pixels they overlap. This script can be directed to your working mod directory, in which case it will edit and overwrite your state definition files, or it can simply spit the province definitions out into the log. This makes state definition much faster than shift-clicking in Nudge, and can even try and identify victory-point inconsistencies. It can also be directed to auto-generate state files if a state doesn’t have one yet.

To demonstrate the basics, an example ProvinceOutlines.bmp image has been provided in this package, under the /Workspace/ directory. Take a moment to look at this image. Note the following:
- Areas that we don’t want filled in are in black.
- Areas that we do want filled in are in white.
- Each letter in the word ‘provincial’ represents a Hearts of Iron IV state. States are recognized by their unique RGB value, rather than by continuity (see how the ‘i’ is just one state: this makes islands possible). What’s more, unless specified otherwise, this border color will be used as the base color for all provinces of this state, giving you a nice and pretty color-coded province-map.
- There are no gaps in the borders of the states, or their internal province borders. The filling process uses a ‘paint bucket’ tool, just like the one in MS paint, so a gap in state borders will make the state’s area spill out into the whole image.
- Neighboring states must have pixels on both sides of the border between them. Or, in other words, a state must be ENTIRELY SURROUNDED by a solid border of its pixels. Another state's border will not substitute a first state's border.

To fill out this image, execute fillprovinces.py using either command-line or IDLE. You should see some information in the output log, followed by (after a few seconds) the appearance of the output image itself.
The actual image you want will be saved in the /Workspace/ directory, named ‘FilledProvinces’. You could take these provinces and place them into your Hearts of Iron 4 province map. However, before doing so, it’s wise to run validatemap.py to check for any problems. Do this now.

validateprovinces.py should have recognized one issue with the map: a single ‘x’ crossing on the first ‘i’ of provincial. This problem would have made the map unusable for Hearts of Iron. You’ll see it marked with a little white and red dot on the output image (debug dots are how all problems are denoted in Provincial).
This covers the basics. In order to use assignprovinces.py, you’ll need to already have a working mod directory with a province map.

USING ASSIGNPROVINCES
assignprovinces.py can be used to place provinces into their appropriate states by comparing the province image to a state image (which may be the border map you provided to fillprovinces.py).
To do this, Provincial needs to know about the definitions.csv file that Hearts of Iron keeps in its /map/ directory. This file is where RGB values are keyed to province IDs, and since state files are interested in province IDs instead of RGB values, the latter needs to be translated to the former. So your usual workflow with assignprovinces.py is:
- Make sure that in provincialsettings.py, ‘mod_dir’ has your mod’s absolute directory, assuming that’s where you’re keeping your definitions.csv file.
- Create your province map.
- Run Hearts of Iron 4 with that province map.
- Check your Documents/Paradox Interactive/Hearts of Iron IV/map directory for a file called definitions.csv.fixed.csv. This is an automatically generated definitions list which will now contain IDs for all of your provinces. Move this to your mod’s /map/ directory and rename it to definitions.csv (and then delete it from the /Hearts of Iron IV/ directory).
- With the RGB values now keyed to province IDs, you can now run assignprovinces.py. If ‘write_to_state_files’ is false, this will simply print the province sets in the log. Otherwise, Provincial will attempt to overwrite your state files (if any exist) or create new ones if ‘fileless_state_handling’ is set to do so. Be warned: there is no backup system in Provincial, so it’s best to save a copy of your state files before running this script if you’re unsure.

assignprovinces.py uses a ‘color comment’ to figure out which unique state color refers to which state file. By default, this comment looks like ‘#COLOR 255, 0, 255’. So if you have existing state files and want to define their unique border colors for Provincial to automatically use, add this comment to the top of those state files with the unique RGB color of that state.
UNDETERMINED PROVINCE FRAGMENTS

Province borders can be tight and fiddly, especially in parts of the map with high province density. This sometimes results in ‘ambiguous’ pixels, or pixels that are not connected to their appropriate province via a von-Neumann (up, down, left, right) neighbor. In other words, they’re cut off from the province they’re supposed to be a part of by border pixels. For an example of this, take a look at the second ‘i’s leftmost tip in the example ProvinceOutlines.bmp image.

There is a pixel at the top of this leftmost province which only touches its neighbor diagonally. If it didn’t know better, Provincial might have guessed that this stray pixel was a province of its own and filled it with a unique color, resulting in an unwanted, and very tiny, province in Hearts of Iron 4. But Provincial has a few techniques to try and detect these stray pixels: how exactly it responds to them is determined by the ‘undetermined_pixel_handling’ setting. Change this setting to 0 for now, and run fillprovinces.py again.

Your log should mention ‘Undetermined Fragments found’, and if you take a look at the map, you’ll see a debug dot marking the location of the pixel of concern. If you look at the filled_provinces output, you’ll see that the area has been filled with 50% grey (127, 127, 127) instead of an appropriate blue for that state. This is Provincial’s way of leaving areas it thinks you need to handle by yourself uncolored.

If you change the setting back to 2, you’ll find that the fragment is assigned to the province to the right of it. This is because it shared more border with that province than with the province to its south, once the border-cleanup was complete.
Islands that are too small to fill in, or too small to contain any white pixels, will similarly be marked as ‘undetermined’.
