# Provincial: Province handling tool for Hearts of Iron IV
# Thomas Slade, 2020

# Toolset settings for use-adjustment
### General ###
# All directories are relative to the location of the scripts themselves.
inputs_dir = "Workspace/"   # Root directory for all input images and files. Leave blank if you have no unified area you want to work.
outputs_dir = "Workspace/" # Root directory for all files and images created by Provincial. This may also be left blank, and can also equal the inputs_directory for ease of use.

### fillprovinces.py ###
province_outlines_dir = inputs_dir + "ProvinceOutlines.bmp"  # Directory of the image used to define the outlines of a state and its borders. This is what's filled in with unique province colours.
# Optional directory of an existing map, which can be used to prevent duplicate province colors in the filled-province output image, if you're doing just a few states at a time.
existing_provinces_dir = inputs_dir + "ExistingProvinces.bmp"
filled_provinces_dir = outputs_dir + "FilledProvinces.bmp"    # Directory of the output image, containing the filled provinces.
# Special color Defines. These colors can't be used as province colors, as they serve a special purpose in reading the province guide.
ignore_col = (0, 0, 0)   # The color indicating that no operation needs to be done (will be filled black in the output).
paint_over_col = (255, 255, 255) # The color of areas that must be filled in with province colors.
undetermined_col = (127, 127, 127)  # The color used for pixels that could not be assigned to a province with any certainty, and require the user's judgement to paint over.
#Important values
# The number of white pixels a province must have, connected via Von-Neumann neighborhood (no diagonals), to be filled in the filling process.
# Areas found with less than thexe pixels will be filled with the undetermined_col and left for the user to fill in manually. This is for catching cases where tiny fragments of a province are cut
# off from its main body by border pixels. The border pixels surrounding an undetermined province fragment will also be filled with the undetermined_col.
min_province_pixels = 4
# If true, a completely random color will be picked as a state's color palette. If false, the state's borders on the province guide will be used as the base palette.
random_state_palette_colors = False
# Base palette color generation values (defined on a scale of 0-1, due to python handling colors that way).
hue_variation = 0.05  # How much hue can vary by.
sat_variation = 0.5  # The max value that saturation can vary by.
val_variation = 0.5  # The max value that value can vary by.
# Whether or not this script should record and play an animation (warning: recording can be very intensive, and is best done with smaller images for testing).
record_animation = False
open_in_fullscreen = False  # Whether or not the output image should be opened in fullscreen (nice for getting gifs).
# 0 = Pixels that did not directly link to a larger province(which are probably just cut off by border definitions) will be filled with grey and marked on the debug map.
# 1 = If an undetermined pixel borders only 1 other color in its state, it will be assigned that color.
# 2 = An undetermined pixel will be assigned to the color it neighbors the most.
undetermined_pixel_handling = 2

### validatemap.py ###
# The number of pixels a province must be less than or equal to in order to be considered excessively small. This ought to be the number that HoI flags when launching in debug mode (8 pixels).
small_province_pixel_count = 8
# The number of pixels wide or tall a key colour's bounding box must be, in order to be potentially flagged as a duplicate province colour (if the province in question is also found to be discontinuous).
large_province_bounds = 50
validation_target_dir = inputs_dir + "FilledProvinces.bmp"    # Directory of the map that needs to be validated.
debug_output_dir = outputs_dir + "Validation.bmp" # Directory of the validation map, which will have colored dots added to locate any issues found.

### assignprovinces.py ###
province_map_dir = inputs_dir + "FilledProvinces.bmp"  # Directory of the map showing the provinces that need to be assigned to states.
# Directory of the map showing state areas in unique colors. This can be the same map as the outline map used for filling provinces (the script will fill it in when assigning provinces).
state_map_dir = inputs_dir + "ProvinceOutlines.bmp"
mod_path_absolute = True   # Whether or not you want the script to search for the province_files_dir and the province_definitions_dir via an absolute path, rather than relative to the script's location.
mod_dir = "C:/Users/[Your User Directory]/Documents/Paradox Interactive/Hearts of Iron IV/mod/[Your Mod Directory/"    # The root absolute directory of your mod, pointing to its top-level file in the 'mod' folder in HoI.
state_files_dir = mod_dir + "history/states/" # Directory of the HoI state files that are being operated on.
province_definitions_dir = mod_dir + "map/definition.csv"   # The directory of the province definition file, where province colors are given their ID.
color_comment_prefix = "#COLOR"
template_naming_format = "$-@.txt" # The format used to create the names of state files, where '$' is the automatically selected state ID, and '@' is the state's name (which will be a placeholder color code).
# The minimum percent (normalised) of a province's pixels that need to be over a single state in order to not raise an error. So if this was 0.8, and a province was split between several states without any having 80% of the pixels,
# an error would be raised.
min_tolerated_province_split = 1.0
write_to_state_files = False # If true, the assigned provinces will be written into the state files found at the state files directory. If false, they'll just be printed in the console.
# 0 = a warning will be printed for any victory points in a state file that aren't in that state's new set of provinces.
# 1 = victory points in a state's file that aren't in its new provinces will be removed.
# 2 = all victory points are cleared from a state's file when it is being written to, unless that state's provinces haven't changed at all or have only had new provinces added.
victory_point_handling = 1
# 0 = states with no files will have template files created for them at the state file directory.
# 1 = states with no files will have their province blocks printed in the console.
fileless_state_handling = 0
# 0 = don't overwrite any of the state IDs in the generated template files: they will be left as the value in the template.
# 1 = use the lowest available ID for the state ID in generated template files. i.e. [1 ... 3, 4], will use 2.
# 2 = use the number above the highest detected state ID. i.e. [1 ... 3, 4] will use 5.
template_state_id_handling = 2
