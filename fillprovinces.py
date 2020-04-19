# Provincial: Province handling tool for Hearts of Iron IV
# Thomas Slade, 2020

# The Algorithm for filling in provinces on a province map with random colors.

import sys
import traceback
import numpy as numpy
import random as random
import colorsys as colorsys
import time
from numpy import arange, logical_and, where
from skimage import data, io
from skimage.segmentation import flood, flood_fill
import matplotlib.pyplot as pyplot
from matplotlib import animation as animation
import provincialutils as provutils
from provincialutils import *
from provincialsettings import *
import json

### Function Definitions ###
# Uses the province map, which should be an image defining province and state borders, to fill out provinces with a unique color (on the province output array).
# Returns false if the operation failed.
def fill_state(province_guide, province_output, state_color):
    try:
        state_mask, border_mask, x_min, y_min, x_max, y_max = get_state_mask(province_guide, state_color)

        # Define the area that we're operating on by cropping the entire image to the bounds of where the defining state key can be found, for optimisation.
        state_view = province_output[y_min:y_max + 1, x_min:x_max + 1]

        province_masks, province_origins, undetermined_mask = get_provinces(numpy.logical_and(state_mask, ~border_mask), min_province_pixels)

        undetermined_province_masks = None
        if undetermined_mask is not None:
            undetermined_province_masks, undetermined_origins, undetermined_second_mask = get_provinces(undetermined_mask, 0, 2)

        palette_color = None
        if random_state_palette_colors:
            palette_color = get_random_color()
        else:
            palette_color = state_color

        for p in province_masks:
            # Fill each province with a random color.
            new_prov_col = get_random_color(palette_color)

            if new_prov_col == ignore_col:
                raise Exception("Error: A province was almost filled with the ignore color {}! This shouldn't be possible, but I saw it happen once so I added this safeguard. Please report it to the tool author. Aborting the operation.".format(ignorecol))
            
            state_view[numpy.where(p)] = new_prov_col
            used_cols.add(tuple(new_prov_col))
            
            # Register an animation frame after each painted province.
            register_anim_frame(province_output)

        if undetermined_province_masks is not None:
            for u in undetermined_province_masks:
                # For now, treat the stray province pieces as regular provinces (this allows us to fill in the borders nicely), but they bay be filled with the undetermined col later
                # depending on the user settings.
                new_prov_col = get_random_color(palette_color)
                state_view[numpy.where(u)] = new_prov_col
                used_cols.add(tuple(new_prov_col))
        
        stray_border_origins = clean_up_borders(state_view, state_mask, border_mask, state_color)
        if stray_border_origins is not None:
            for s in stray_border_origins:
                s[0] = s[0] + y_min
                s[1] = s[1] + x_min

            global stray_border_fragments

            stray_border_fragments = numpy.concatenate((stray_border_fragments, stray_border_origins))

        # Decided what to do with the province fragments which were so small they were probably meant to be part of a bigger province.
        if undetermined_province_masks is not None:
            for u in undetermined_origins:
                mode_col = None

                post_border_cleanup_fragment = logical_and.reduce(state_view == state_view[u[0],u[1]], axis = -1)

                state_view[post_border_cleanup_fragment] = (255, 0, 255)
                
                if undetermined_pixel_handling != 0:
                    mode_col = get_mode_neighbors_of_area(post_border_cleanup_fragment, state_view, state_mask, undetermined_pixel_handling == 1)

                if mode_col is not None:

                    state_view[numpy.where(post_border_cleanup_fragment)] = mode_col
                else:
                    state_view[numpy.where(post_border_cleanup_fragment)] = undetermined_col

                    # Coordinates need to be in global array space.
                    # Don't forget, axes are [0] = y, [1] = x in numpy ...
                    u[0]= u[0] + y_min 
                    u[1]= u[1] + x_min
                    global undetermined_fragments
                    undetermined_fragments = numpy.concatenate((undetermined_fragments, [u]), axis = 0)

        # Register the final animation frame.
        register_anim_frame(province_output)
        
    except Exception as exc:
        print("Error: Failure while attempting to fill the state of color '{}':".format(state_color) + str(exc))
        traceback.print_exc()
        # Notify the caller that the operation was not a success
        return False

    return True

# Given a defined area in an array of colors, go through the pixels neiughboring that area (von-Neumann neighborhood) and find the most prevalant color.
# If check_for_ubiquity, will instead return the neighboring col if that color is the ONLY color to neighbor the area, otherwise returns None.
def get_mode_neighbors_of_area(area_mask, state_view, state_mask, check_for_ubiquity = False):
    neighboring_cols = {}
    highest_count = 0
    mode_col = None
    for y in range(state_view.shape[0]):
        for x in range(state_view.shape[1]):
            tuple_col = tuple(state_view[y, x])

            if (state_mask[y, x] and not area_mask[y, x] and
                (y > 0 and area_mask[y - 1, x]
                or
                (y < state_view.shape[0] - 1 and area_mask[y + 1, x])
                or
                x > 0 and area_mask[y, x - 1]
                or
                x < state_view.shape[1] - 1 and area_mask[y, x + 1])):
                
                # If checking for ubiquity, and found a different color, return None.
                if check_for_ubiquity and mode_col is not None and tuple_col != mode_col:
                    return None
                
                if tuple_col not in neighboring_cols:
                    neighboring_cols[tuple_col] = 0
                neighboring_cols[tuple_col] += 1
                if neighboring_cols[tuple_col] > highest_count:
                    highest_count += 1
                    mode_col = tuple_col

    return mode_col

# Iterate through all province border pixels, assigning them the color of neighboring provinces until none are left.
# A border pixel is assigned to a province based on which province has the most pixels neighboring it. This can be done over several iterations.
def clean_up_borders(state_view, state_mask, border_mask, state_color):
    waning_border_mask = border_mask.copy() # We need a copy of the border mask that loses pixels over the course of the operation.

    filled_mask = state_mask & ~border_mask # A mask tracking the pixels which have been filled, either before or during the border cleanup.

    border_coords = numpy.where(border_mask)
    leftover_coords = [[],[]]
    stray_borders_origins = None

    if len(border_coords[0]) == 0:
        raise Exception("No border pixels were found in the specified border mask.")
        return
    
    previous_leftover = len(border_coords[0])

    while len(border_coords[0]) > 0:
        for b in range(len(border_coords[0])):
            coord = numpy.array([border_coords[0][b], border_coords[1][b]])

            # Each iteration, color any pixels that are immediately adjacent to pixels that have already been colored. This helps avoid accidentally creating
            # 'X' crossings where a pixel may not be von-Neumann connected to the area that it drew its color from.
            if has_neighbor_in_mask(coord, filled_mask):
                mode_color = get_mode_neighbor(coord, state_view, state_mask, border_mask, waning_border_mask)
                
                if mode_color == None:
                    leftover_coords[0].append(coord[0])
                    leftover_coords[1].append(coord[1])
                else:
                    state_view[coord[0], coord[1]] = mode_color
                    waning_border_mask[coord[0], coord[1]] = False
                    filled_mask[coord[0], coord[1]] = True
            else:
                leftover_coords[0].append(coord[0])
                leftover_coords[1].append(coord[1])

        # If, after an iteration, the number of leftover coordinates hasn't changed, it means we've found some stray border pixels that have no associated white pixels (probably very small islands).
        # Mark their locations for debugging purposes, and fill them in the undetermined_col.
        if len(leftover_coords[0]) == previous_leftover:
            leftover_pixels_mask = numpy.zeros(state_mask.shape, dtype = bool)
            leftover_pixels_mask[leftover_coords[0], leftover_coords[1]] = True

            stray_borders_masks, stray_borders_origins, undetermined_mask = get_provinces(leftover_pixels_mask, 0, 2)

            state_view[leftover_coords[0], leftover_coords[1]] = undetermined_col
            break

        previous_leftover = len(leftover_coords[0])
        border_coords = numpy.array(leftover_coords)
        leftover_coords = [[],[]]

        # Register an animation frame after every border-cleanup iteration.
        register_anim_frame(province_output)

    return stray_borders_origins

# Determine if the coordinate has a von Neumann neighbor that is true in the argued mask.
def has_neighbor_in_mask(coordinate, mask):
    for d in range(0, len(directions), 2):
        direction = directions[d]
        neighbor = numpy.array([coordinate[0] + direction[0], coordinate[1] + direction[1]])

        if neighbor[0] >= 0 and neighbor[0] < mask.shape[0] and neighbor[1] >= 0 and neighbor[1] < mask.shape[1]:
            if mask[neighbor[0], neighbor[1]]:
                return True
    return False
    

# Find the most common potential color (i.e. not a key color) neighboring the border pixel at this coordinate.
# Special priority is given to pixels that aren't just a border pixel that's been recolored on a previous iteration, but are an original province-pixel instead
def get_mode_neighbor(coordinate, state_view, state_mask, border_mask, remaining_border_mask):
    neighbor_cols = {}
    neighboring_native_col = {}
    current_mode = None

    for d in range(len(directions)):
        direction = directions[d]
        neighbor_coord = numpy.array([coordinate[0] + direction[0], coordinate[1] + direction[1]])

        is_cardinal = d % 2 == 0
    
        # If this neighboring pixel is within the state view's bounds ...
        # and is not a (currently unpainted) border pixel, add its color to the mode count.
        if (neighbor_coord[0] >= 0 and neighbor_coord[0] < state_view.shape[0]
            and neighbor_coord[1] >= 0 and neighbor_coord[1] < state_view.shape[1]
            and state_mask[neighbor_coord[0], neighbor_coord[1]] and not remaining_border_mask[neighbor_coord[0], neighbor_coord[1]]):

            neighbor_col = tuple(state_view[neighbor_coord[0], neighbor_coord[1]])

            if neighbor_col not in neighbor_cols:
                neighbor_cols[neighbor_col] = 0
                neighboring_native_col[neighbor_col] = False

            # Cardinal neighbors are worth more than diagonal ones.
            if is_cardinal:
                neighbor_cols[neighbor_col] += 2;
            else:
                neighbor_cols[neighbor_col] += 1;
            
            if not border_mask[neighbor_coord[0], neighbor_coord[1]] and is_cardinal:
                neighboring_native_col[neighbor_col] = True
    
    # If the neighboring pixel is of a province and not a recoloured border pixel, mark it as native-colored, giving it a priority.
    for c in neighbor_cols:
        if current_mode is None:
            current_mode = c
        elif neighboring_native_col[c] and not neighboring_native_col[current_mode] or neighbor_cols[c] > neighbor_cols[current_mode]:
            current_mode = c
    
    return current_mode

# Identify the palette colour assigned to a state by searching for its base palette marker.
# If the marker is not found, provide a random color instead.
# -- Depracated. May be useful some other time ... --
def get_palette_color(state_view, state_mask):
    palette_marker_coords = numpy.where(numpy.logical_and((state_view == [0, 255, 255]).all(axis = 2), state_mask))

    if len(palette_marker_coords[0]) == 0:
        global missing_palette_marker_count
        missing_palette_marker_count = missing_palette_marker_count + 1
        if not allow_missing_palette_marker:
            raise Exception("No palette marker of color '{}' was found when filling this state. ".format(base_palette_marker_col)
                + " A pixel of this color should be present within this state to specify a base color for the state's provinces. Creating a random base color instead.")
        else:
            return get_random_color()

    if len(palette_marker_coords[0]) > 1:
        raise Exception("A total of {} pixels of the palette marker of color '{}' were found when filling a state".format(len(palette_marker_coords[0]), base_palette_marker_col)
              + " Only one pixel of this color may be specified within a state, as it is used to denote a palette base using the pixel immediately to its right.")
        return None

    palette_marker_coord = [palette_marker_coords[0][0], palette_marker_coords[1][0]]

    if palette_marker_coord[0] + 1 > state_view.shape[0]:
        raise Exception("The detected palette marker at position ({}, {}) was found to be on the right edge of the enclosing state's bounding box.".format(palette_marker_coord[0], palette_marker_coord[1])
                        + " It should be placed comfortably within one of the state's provinces.")
    
    # The palette pixel should be the one immediately to the right of the marker.
    palette_base = state_view[palette_marker_coord[0], palette_marker_coord[1] + 1]
    if not validate_color(palette_base):
        raise Exception("The color found to the right of marker position ({}, {}) has a value of '{}', which was found to be reserved for image operations. Choose a different base color."
                        .format(palette_marker_coord[0], palette_marker_coord[1], palette_base))
    
    return palette_base

# Get a random color that doesn't equal any of the key colors used to operate on the image.
# If palette_base is specified, the random color will be a variant of this color.
def get_random_color(palette_base = None, disallowed_values = []):
    generation_attempts = 10
    current_attempt = 0

    for i in range(generation_attempts):
        current_attempt = i
        generated_color = None
        
        if palette_base is None:
            generated_color = [random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)]
        else:
            # If we want to deal with color generation in Hue-Sat-Value, we need to use python's own colorsys module, which deals with colors in 0-1 rather than 0-255.
            palette_norm = numpy.array(palette_base, numpy.single) * col_inverse_factor
            palette_hsv = colorsys.rgb_to_hsv(palette_norm[0], palette_norm[1], palette_norm[2])

            # A base palette with low saturation cannot change its saturation much. This preserves 'grey' base colors.
            scaled_sat_variation = sat_variation * palette_hsv[1]
            # Greyer tones should also have less value variation.
            scaled_val_variation = val_variation * (palette_hsv[1] * 0.5 + 0.5)
            
            # Clamp the base sat and val variables such that any possible variation added to them will not take them over 1 or under 0.
            clamped_sat = max(min(palette_hsv[1], 1 - scaled_sat_variation * 0.5), scaled_sat_variation * 0.5)
            clamped_val = max(min(palette_hsv[2], 1 - scaled_val_variation * 0.5), scaled_val_variation * 0.5)

            adjusted_hsv = [0, 0, 0]
            # Adjust the hue with the hue_variation, and use modulo to wrap the output (allowing red values to straddle into crimson ones, for example).
            adjusted_hsv[0] = ((random.uniform(0.0, hue_variation) + palette_hsv[0]) % 1)
            # For saturation and value, get a random number within the range of the variations, and subtract half of that value to allow the values to move up or down.
            adjusted_hsv[1] = clamped_sat + random.uniform(0.0, scaled_sat_variation) - scaled_sat_variation * 0.5
            adjusted_hsv[2] = clamped_val + random.uniform(0.0, scaled_val_variation) - scaled_val_variation * 0.5

            # Get the RGB again (which will be in a 0-1 format) then convert it back to 0-255.
            generated_color_norm = colorsys.hsv_to_rgb(adjusted_hsv[0], adjusted_hsv[1], adjusted_hsv[2])
            generated_color = [int(round(generated_color_norm[0] * 255)), int(round(generated_color_norm[1] * 255)), int(round(generated_color_norm[2] * 255))]

        # Check if the generated color equals any of the key colors.
        if not validate_color(generated_color):
            continue

        if tuple(generated_color) in used_cols:
            continue
        
        # CHeck if the generated color equals any of the disallowed values.
        is_disallowed = False
        for d in range(len(disallowed_values)):
            if generated_color == disallowed_values:
                is_disallowed = True
                continue

        if is_disallowed:
            continue

        return generated_color

    raise Exception("Error: After {} attempts, get_random_color failed to generate a color of the argued specifications and one that doesn't match any of the key colors.".format(current_attempt));
    return None

# Check to see if a color is one of the key colors reserved for operating on the image.
def validate_color(color):
    color = list(color)
    return not (color == ignore_col or
                color == paint_over_col or
                color == undetermined_col)

# Play an animation, looping through the recorded animation frames.
def animate(frame):
    global animation_frames
    
    latest_frame = min(frame, len(animation_frames) - 1)
    
    mat.set_data(animation_frames[latest_frame])
    return mat

# Copy the argued image into the animation frame for display later (will not record anything unless the 'animate' flag has been raised.
def register_anim_frame(image):
    if record_animation:
        global animation_frames
        animation_frames.append(image.copy())

### Globals ###
# Equal to 1 / 255. The number to multiply by when converting a normalised color value to a 255 color value.
col_inverse_factor = 0.00392
# 4 cardinal directions directions to find a coordinate's neighbours, defined clockwise starting from 'above'.
directions = [[0, 1], [1, 1], [1, 0], [1, -1], [0, -1], [-1, -1], [-1, 0], [-1, 1]]
# Stores the animation frames, which are iterated through after the process.
animation_frames = []

### Main Program ###
province_guide = io.imread(province_outlines_dir)
existing_map = None
try:  
    existing_map = io.imread(existing_provinces_dir)
except FileNotFoundError:
    print("\nNo existing map specified! The filling operation will not avoid any pre-existing province colour keys that are already on the map you're working on."
          " If you have a map with existing provinces, add it to the workspace directory as an image named '{}'".format(existing_provinces_dir))
    
province_output = numpy.zeros(province_guide.shape, dtype = numpy.uint8)
register_anim_frame(province_output)
width = len(province_guide)
height = len(province_guide[0])
error_states_count = 0 # Debug counter to track if any states failed during the filling process.

# Image-based debugging. Arrays used for printing shapes on the debug-output image to highlight any potential concerns with the map generation.
undetermined_fragments = numpy.empty((0, 2), dtype = int)  # Positions of detected province fragments whose colour could not safely be determined automatically.
stray_border_fragments = numpy.empty((0, 2), dtype = int)  # Positions of chunks of border pixels that had no internal white pixels (likely very small/narrow islands)

used_cols = set()
if existing_map is not None:
    unique_cols_arr = numpy.unique(existing_map.reshape(-1, existing_map.shape[2]), axis = 0)
    # Unique colours need to be made into tuples for their use in sets.
    unique_in_existing = set(tuple(map(tuple, unique_cols_arr)))
    # Black and white shouldn't be counted.
    unique_in_existing.discard(ignore_col)
    unique_in_existing.discard(paint_over_col)
    print("\nDiscovered {} unique province key colours in {}.".format(len(unique_in_existing), existing_provinces_dir))
    
    used_cols.update(unique_in_existing)

state_keys = set();

unique_state_cols = set(tuple(map(tuple, numpy.unique(province_guide.reshape(-1, province_guide.shape[2]), axis = 0))))
unique_state_cols.discard(ignore_col)
unique_state_cols.discard(paint_over_col)
print("\nDiscovered {} unique province key colours in {}.".format(len(unique_state_cols), province_outlines_dir))
state_keys.update(unique_state_cols)

print("\nAttempting to fill states ...")

undetermined_log = "Small province fragments (less than {} non-border pixels)".format(min_province_pixels)
if undetermined_pixel_handling == 0:
    print(undetermined_log + " with ambiguous province ownership will be colored {} and marked on the debug output.".format(undetermined_col))
elif undetermined_pixel_handling == 1:
    print(undetermined_log + " will be assigned to a neighboring province if that province is the only province in the same state touching them.")
elif undetermined_pixel_handling == 2:
    print(undetermined_log + " will be assigned to the neighboring province in the same state that they border the most.")
else:
    raise Exception("Error: undetermined_pixel_handling had an invalid value of {}.".format(undetermined_pixel_handling))
for key in state_keys:
    if not fill_state(province_guide, province_output, key):
        error_states_count = error_states_count + 1

# Add debug dots.
if error_states_count > 0:
    print("\nError: Not all states generated successfully, and the resulting image is not a reliable province map! "
          + "The output will NOT be saved to FilledProvinces.png.\n\nStates successfully generated: {} / {}".format(len(state_keys) - error_states_count, len(state_keys)))
else:
    print("\nAll states generated successfully! Saving the output as {}! Use this output file, as it has the correct DPI.".format(filled_provinces_dir))
    # I can only get the saved image to have the correct resolution, for some reason.
    pyplot.imsave(filled_provinces_dir, province_output)

if len(undetermined_fragments) > 0:
    print("\nUndetermined Fragments found: {}\nThese are places where the continuous pixel count was below 'min_province_pixels' ({}), and thus were liable to be a disconnected chunk of another province.\n"
          "Orange dots on the debug image.".format(len(undetermined_fragments), min_province_pixels))

    for u in undetermined_fragments:
        paste(province_output,  provutils.get_dot([255, 127, 0],  [255, 255, 255]), (u[0] - 1, u[1] - 1))

# Register an animation-frame post debug dots.
register_anim_frame(province_output)

if len(stray_border_fragments) > 0:
    print("\nStray Border Fragments found: {}\n(These are border pixels that had no connected white pixels. They're probably islands that were too small to contain any white pixels.\n" 
      "Blue dots on the debug image.".format(len(stray_border_fragments)))

    for s in stray_border_fragments:
        paste(province_output,  provutils.get_dot([0, 0, 255],  [255, 255, 255]), (s[0] - 1, s[1] - 1))

# Register an animation-frame post debug dots.
register_anim_frame(province_output)

map_dpi = province_guide.shape[0] / 10

anim_figure, axes = pyplot.subplots(figsize = (10, province_guide.shape[1] / map_dpi), dpi = map_dpi)
mat = axes.matshow(province_output)

if record_animation:
    anim = animation.FuncAnimation(anim_figure, animate, save_count=50, interval=5)

if open_in_fullscreen:
    mng = pyplot.get_current_fig_manager()
    mng.full_screen_toggle()

pyplot.axis('off')
pyplot.show()




    
