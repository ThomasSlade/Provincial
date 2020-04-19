# Provincial: Province handling tool for Hearts of Iron IV
# Thomas Slade, 2020

# Common functions for image manipulation in the Provincial tool.

import numpy as numpy
from numpy import arange
from skimage import data, io
from skimage.segmentation import flood, flood_fill
from numpy import logical_and, logical_or
from provincialsettings import *

# Makes a 'selection' starting at the specified startingCoord and filling out adjacent pixels of equal colour value. Returns a 2D np array where a True element indicates a pixel that was flooded.
def flood_rgb(image, starting_coord):
    image = image.copy()
    width = len(image)
    height = len(image[0])
    # Sadly, I need to use this 'alternate color' approach because I can't get flood working with an RGB image, so I need to make several calls to flood on each color channel, using
    # either black or white as an invalidation marker (white if the actual sample colour is black, else black).
    alternate_col = [1, 1, 1] if (image[starting_coord[0]][starting_coord[1]] == [0, 0, 0]).all() else [0, 0, 0] 
    
    r_flood = flood(image, (starting_coord[0], starting_coord[1], 0), connectivity = 1)
    for x in range(width):
        for y in range(height):
            if not r_flood[x, y, 0]:
                image[x, y] = alternate_col
    g_flood = flood(image, (starting_coord[0], starting_coord[1], 1), connectivity = 1)
    for x in range(width):
        for y in range(height):
            if not g_flood[x, y, 1]:
                image[x, y] = alternate_col
    b_flood = flood(image, (starting_coord[0], starting_coord[1], 2), connectivity = 1)

    all_flood = numpy.empty([width, height], bool)

    for x in arange(width):
        for y in arange(height):
            all_flood[x][y] = r_flood[x, y, 0] and g_flood[x, y, 1] and b_flood[x, y, 2]
            
    return all_flood

# Returns true if this color's R and B values match but its G value is different.
def is_magenta_shade(color):
    return color[0] == color[2] and color[0] != color[1] and color[0] != 0

# Find the bounding of all elements in the argued mask array that equal True.
# Returns the min x, min y (top-left coord), and max x, max y (bottom-right coord) as separate numbers.
def find_bounds(mask_array):
    rows = numpy.any(mask_array, axis=1)
    cols = numpy.any(mask_array, axis=0)
    y_min, y_max = numpy.where(rows)[0][[0, -1]]
    x_min, x_max = numpy.where(cols)[0][[0, -1]]

    return x_min, y_min, x_max, y_max

# Returns a set of pixels representing a 3x3 'donut' dot with a single colored pixel at its centre.
def get_dot(centre_col, outline_col):
    return numpy.array([[outline_col, outline_col, outline_col],
                       [outline_col, centre_col, outline_col],
                       [outline_col, outline_col, outline_col]])

def paste_slices(tup):
  pos, w, max_w = tup
  wall_min = max(pos, 0)
  wall_max = min(pos+w, max_w)
  block_min = -min(pos, 0)
  block_max = max_w-max(pos+w, max_w)
  block_max = block_max if block_max != 0 else None
  return slice(wall_min, wall_max), slice(block_min, block_max)

# Pastes the block array over the wall array at the (top-left) location, accounting for clamping if the block is over the wall's edge.
def paste(wall, block, loc):
  loc_zip = zip(loc, block.shape, wall.shape)
  wall_slices, block_slices = zip(*map(paste_slices, loc_zip))
  wall[wall_slices] = block[block_slices]

# Get a list of masks representing pixels belonging to distinct continuous areas in the argued mask.
# Any pixels belonging to a province smaller than the minimum fill pixel quantity will be added to the undetermined mask. If none are found, the undetermined mask returns as None.
def get_provinces(province_mask, min_province_pixels, connectivity = 1):
    province_masks = []
    province_origins = []
    undetermined_mask = numpy.zeros(province_mask.shape, dtype = bool)
    undetermined_pixels_found = False

    for x in range(province_mask.shape[0]):
        for y in range(province_mask.shape[1]):
            if province_mask[x][y] and ~undetermined_mask[x][y]:
                flooded_pixels = flood(province_mask, (x, y), connectivity = connectivity)

                if numpy.count_nonzero(flooded_pixels) < min_province_pixels:
                    undetermined_pixels_found = True
                    # If the discovered area was too small, mark it on the undetermined map (this will be re-evaluated later, allowing for diagonal pixel connections next time).
                    undetermined_mask = numpy.logical_or(undetermined_mask, flooded_pixels)
                else:
                    # Remove the mask of the discovered province (found via flooding) from the province_mask, preventing it from being re-added by future iterations.
                    province_mask = numpy.logical_and(province_mask, ~flooded_pixels)
                    province_masks.append(flooded_pixels)
                    province_origins.append([x, y])

    if not undetermined_pixels_found:
        undetermined_mask = None
    
    return province_masks, province_origins, undetermined_mask

# Puts a list of numbers into a string, separated by commas.
def list_to_string(to_string, separator = " "):
    if type(to_string) is set:
        to_string = list(to_string)
    output = ""
    for l in range(len(to_string)):
        output = output + str(to_string[l])
        if l < len(to_string) - 1:
            output = output + separator
    return output

# Converts a string to a list of numbers, using the argued separation character.
def string_to_list(to_list, separator = " "):
    splits = to_list.split(separator)
    output = []
    for s in splits:
        if s != "":
            try:
                output.append(int(s))
            except:
                print("Error when converting the string '{}' to a list of numbers. Can '{}' be successfully parsed into an int?".format(to_list, s))
    return output

# Takes a map which may have only state borders (drawn in their unique state-colors), and identifies the area encompassed by the state of the argued state_color.
# In other words, identifies all the pixels inside or including a state's borders, essentially 'filling in' the state.
# Also returns a mask representing the original pixels of the state_color in the guide, as well as the bounds of these pixels (x_min, y_min, x_max, y_max).
def get_state_mask(state_guide, state_color):
    # Get a mask of all pixels of the border key color.
    # Running two_d_array == value produces a 'mask' where only individual pixels are compared, but we want to know about cases where all three pixels are equal.
    # logical_and does this sort of thing, apparently.
    border_mask = logical_and.reduce(state_guide == state_color, axis = -1)

    x_min, y_min, x_max, y_max = find_bounds(border_mask)
    guide_view = state_guide[y_min:y_max + 1, x_min:x_max + 1]
    
    # Crop the border_mask too.
    border_mask = border_mask[y_min:y_max + 1, x_min:x_max + 1]

    # Create a copy of the border mask with a new layer of false pixels all around the edge.
    state_mask = border_mask.copy()
    state_mask = numpy.insert(state_mask, 0, False, axis = 0)
    state_mask = numpy.insert(state_mask, 0, False, axis = 1)
    state_mask = numpy.insert(state_mask, state_mask.shape[0], False, axis = 0)
    state_mask = numpy.insert(state_mask, state_mask.shape[1], False, axis = 1)

    # Get a mask of all pixels outside the state's borders, by performing a flood from the top-left pixel on the expanded mask we've made.
    # Then invert the mask. All true values on the mask signify a point on or within the state's borders.
    state_mask = ~flood(state_mask, (0, 0), connectivity = 1)
        
    # Crop the state_mask back to the bounds of the relevant pixels.
    state_mask = numpy.delete(state_mask, state_mask.shape[0] - 1, 0)
    state_mask = numpy.delete(state_mask, state_mask.shape[1] - 1, 1)
    state_mask = numpy.delete(state_mask, 0, 0)
    state_mask = numpy.delete(state_mask, 0, 1)

    state_mask = state_mask & logical_or.reduce(guide_view != ignore_col, axis = -1)

    return state_mask, border_mask, x_min, y_min, x_max, y_max
