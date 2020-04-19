# Provincial: Province handling tool for Hearts of Iron IV
# Thomas Slade, 2020

# Identifies flaws in an already generated map.

import numpy
import matplotlib.pyplot as pyplot
from skimage import io
from numpy import logical_and
from provincialutils import paste, get_dot, find_bounds, get_provinces
from scipy.spatial import distance
from provincialsettings import *

# Identify points where 4 pixels of different colors neighbor each other, forming a non-pathfinding-friendly 'x' crossing. Mark the points with a small cross.
def find_x_crossings(province_map, province_output):
    print("Searching for x-crossings ...")
    
    global x_crossings_count
    
    for y in range(height - 1):
        for x in range(width - 1):
            
            if ((province_map[y, x] != province_map[y, x + 1]).any() and
                (province_map[y, x] != province_map[y + 1, x]).any() and
                (province_map[y + 1, x + 1] != province_map[y, x + 1]).any() and
                (province_map[y + 1, x + 1] != province_map[y + 1, x]).any()):

                x_crossings.append([y, x])

def check_prov_sizes(province_map, province_output):
    print("Checking for provinces that are suspiciously small or large ...")

    unique_cols_arr = numpy.unique(province_map.reshape(-1, province_map.shape[2]), axis = 0)

    undetermined_mask = logical_and.reduce(province_map == undetermined_col, axis = -1)
    global undetermined_origins
    undetermined_province_masks, undetermined_origins, useless_mask = get_provinces(undetermined_mask, 0, 2)
    
    for u in range(len(unique_cols_arr)):
        unique_col = unique_cols_arr[u]
        #Ignore black and white.
        if (unique_col == (0, 0, 0)).all() or (unique_col == (255, 255, 255)).all():
            continue

        unique_col_coords = numpy.where(logical_and.reduce(province_map == unique_col, axis = -1))
        unique_col_origin = unique_col_coords[0][0], unique_col_coords[1][0]
        
        unique_col_mask = logical_and.reduce(province_map == unique_col, axis = -1)

        if numpy.count_nonzero(unique_col_mask) <= small_province_pixel_count:
            small_provinces.append(unique_col_origin)

        x_min, y_min, x_max, y_max = find_bounds(unique_col_mask)
        
        if x_max - x_min > large_province_bounds or y_max - y_min > large_province_bounds:
            fragments_masks, fragment_origins, undetermined_mask = get_provinces(unique_col_mask, 0, 2)

            if  len(fragment_origins) > 1:
                spread_out_provinces[tuple(unique_col)] = [len(fragment_origins), x_max - x_min, y_max - y_min, unique_col_origin]
            


# Create a set of coordinates representing a diagonally-armed cross shape, with an arm length of the argued number.
def get_x_shape(centre_coord, arm_length = 1):
    cols = numpy.array([0] * (arm_length * 4 + 1))
    rows = numpy.array([0] * (arm_length * 4 + 1))

    cols[0] = centre_coord[0]
    rows[0] = centre_coord[1]

    for l in range(arm_length):
        l = l + 1# Due to 0-based indexing, 'l' should start at 1.

        cols[1 * l] = centre_coord[0] + l
        rows[1 * l] = centre_coord[1] + 1
        cols[2 * l] = centre_coord[0] + l
        rows[2 * l] = centre_coord[1] + -1
        cols[3 * l] = centre_coord[0] + -1
        rows[3 * l] = centre_coord[1] + -1
        cols[4 * l] = centre_coord[0] + -1
        rows[4 * l] = centre_coord[1] + 1

    return numpy.array([cols, rows])

# Apply the argued shape to the image, where the shape's coordinates fall within the image's bounds.
def paint_shape(coords, color, image):
    for c in range(len(coords[0])):
        if coords[0][c] >= 0 and coords[0][c] < image.shape[0] and coords[1][c] >= 0 and coords[1][c] < image.shape[1]:
            image[coords[0][c], coords[1][c]] = color

### Main Program ###
x_crossings =[]
spread_out_provinces = {}
small_provinces = []
undetermined_origins = []

province_map = io.imread(validation_target_dir)
province_output = province_map.copy()
width = province_map.shape[1]
height = province_map.shape[0]

find_x_crossings(province_map, province_output)
check_prov_sizes(province_map, province_output)

any_issues_found = False

if len(x_crossings) > 0:
    for x in x_crossings:
        paste(province_output, get_dot((255, 0, 0), (255, 255, 255)), x)
    print("\n{} 'X' Crossings were found in on the map when validating. Only three provinces should meet at a given point in Hearts of Iron 4.\nSee the red dots on the output map.".format(len(x_crossings)))
    any_issues_found = True

if len(spread_out_provinces) > 0:
    print("\n{} provinces were found to have pixels more than {} distance appart, and were also drawn in multiple continuous areas. These may represent repeated province colors.\nSee the blue dots on the output.\nDetails: ...".format(len(spread_out_provinces), large_province_bounds))
    for s in spread_out_provinces:
        paste(province_output, get_dot((0, 0, 255), (255, 255, 255)), spread_out_provinces[s][3])
        print("Province {} has bounds of {}x{} and {} continuous areas.".format(s, spread_out_provinces[s][1], spread_out_provinces[s][2], spread_out_provinces[s][0]))
    any_issues_found = True

if len(small_provinces) > 0:
    for s in small_provinces:
        paste(province_output, get_dot((0, 255, 0), (255, 255, 255)), s)
    print("\n{} provinces were found with less than {} pixels. Hearts of Iron will print a warning for provinces with fewer than 8 pixels.\nSee the green dots on the output map.".format(len(small_provinces), small_province_pixel_count))
    any_issues_found = True

if len(undetermined_origins) > 0:
    print("\nWarning: The defined undetermined color '{}' was found in the map provided for validation.".format(undetermined_col) +
            "The ignore color is added to province maps by fillprovinces.py to signify pixels that need user attention due to their owner province being ambiguous. Did you mean to leave '{}' pixels in this map?".format(undetermined_col) +
              "\nSee the cyan dots on the output map.")
    for u in undetermined_origins:
        paste(province_output, get_dot((0, 255, 255), (255, 255, 255)), u)

map_dpi = province_map.shape[0] / 10

if any_issues_found:
    print("\nSaving the debug image to '{}'".format(debug_output_dir))
    pyplot.imsave(debug_output_dir, province_output)
else:
    print("\nMap found to be completely valid!")

pyplot.figure(figsize = (10, province_map.shape[1] / map_dpi), dpi = map_dpi)
pyplot.imshow(province_output)
pyplot.axis('off')
pyplot.show()
