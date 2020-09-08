# Provincial: Province handling tool for Hearts of Iron IV
# Thomas Slade, 2020

# Generates or updates a province definition file based on the provided province map and terrain map.
# Provinces that already have a definition in the existing definitions CSV will be maintained and updated (their ID will not change, so your state/region definitions will be safe!).
# Undefined provinces will be added to the end of the existing definition file.
# Note that the existing definitions file MUST have a continuous sequence of IDs, with no gaps (i.e. no 1, 2, 3, 5). In this case, province number 4 will not be generated, and HoI 4 will probably crash.

import sys
import traceback
import math
import numpy as numpy
import matplotlib.pyplot as pyplot
from os import path, listdir
from skimage import data, io
from skimage.segmentation import flood, flood_fill
from provincialutils import *
from provincialsettings import *

# Use the provided province inverse coordinates (basically the indices of all pixels of that province within the province map) to find the most common terrain type in that province.
def get_terrain(terrain_map_flattened, province_inverse):
    largest_count = 0
    mode_terrain = None
    terrain_totals = {}

    province_terrain_pixels = terrain_map_flattened[province_inverse]
    
    t_cols, t_indices, t_inverses, t_counts = numpy.unique(province_terrain_pixels, axis = 0, return_index = True, return_inverse = True, return_counts = True)
    
    for t in range(len(t_cols)):
        terrain_col = tuple(t_cols[t])

        if not terrain_col in terrains:
            raise Exception("Error: Terrain color '{}' has no entry in the 'terrains' dictionary in the settings file. Terrain type pixel count: {}".format(terrain_col, t_counts[t]))

        current_terrain = terrains[terrain_col]
        if not current_terrain in terrain_totals:
            terrain_totals[current_terrain] = 0
            
        terrain_totals[current_terrain] += t_counts[t] * current_terrain.bias
        if terrain_totals[current_terrain] > largest_count:
            largest_count = terrain_totals[current_terrain]
            mode_terrain = current_terrain

    return mode_terrain

# Get the index of all land provinces neighboring the argued sea province. Returns none if no land provinces neighbor this sea province.
def get_coastal_neighbors(prov_inverses_unflattened, sea_prov_index, province_map, sea_province_set):
    sea_prov_mask = prov_inverses_unflattened == sea_prov_index
    x_min, y_min, x_max, y_max = find_bounds(sea_prov_mask)

    # Increase the province view in all directions by 1 pixel, where not limited by the source province map's size.
    y_min = max(0, y_min - 1)
    x_min = max(0, x_min - 1)
    y_max = min(province_map.shape[0] + 2, y_max + 2)
    x_max = min(province_map.shape[1] + 2, x_max + 2)
    
     # Get a clamped view of both the inverse map and the province map to speed up search operations.
    inverse_view_clamped = prov_inverses_unflattened[y_min:y_max, x_min:x_max]
    province_view_clamped = province_map[y_min:y_max, x_min:x_max]

    neighbor_prov_indices = set(inverse_view_clamped[get_outer_border(inverse_view_clamped, sea_prov_index)]) - sea_province_set

    if len(neighbor_prov_indices) == 0:
        return None
    else:
        return neighbor_prov_indices   

# Get a mask where entries on the inverse map are true if they neighbor the argued target value (manhatten neighbors).
def get_outer_border(inverse_map, target_province):
    border_map = numpy.zeros(inverse_map.shape, dtype = bool)
    
    for y in range(inverse_map.shape[0]):
        for x in range(inverse_map.shape[1]):
            if inverse_map[y, x] != target_province:
                border_map[y, x] = ((x > 0 and inverse_map[y, x - 1] == target_province) or
                    (x < inverse_map.shape[1] - 1 and inverse_map[y, x + 1] == target_province) or
                    (y > 0 and inverse_map[y - 1, x] == target_province) or
                    (y < inverse_map.shape[0] - 1 and inverse_map[y + 1, x] == target_province))

    return border_map

### Main program ###
province_map = io.imread(province_map_dir)  # The map defining provinces.
terrain_map = io.imread(terrain_map_dir) # The map defining terrain. Slice away the alpha channel for indexed color images, I guess.
province_definitions_dir_context = province_definitions_dir # The location of the province definition file, accounting for whether or not absolute path is enabled.
terrain_debug = province_map.copy()
type_debug = province_map.copy()

# Using numpy.unique necessitates working on a 'flattened' (not actually flattened, but with only one traversable dimension, still allowing for RGB values) array.
province_map_flattened = province_map.reshape(-1, province_map.shape[2])
terrain_map_flattened = terrain_map.reshape(-1, terrain_map.shape[2])

# If we're working with an absolute directory structure, rather than searching for files to read within this script's own directory, update the target directory accordingly.
if mod_path_absolute:
        my_path = path.abspath(path.dirname(__file__))
        state_files_dir_context = path.join(my_path, state_files_dir)
        province_definitions_dir_context = path.join(my_path, province_definitions_dir)

print("Reading definitions file at '{}' to inform province IDs and respect existing data.".format(province_definitions_dir_context))
definitions_file = open(province_definitions_dir_context, "r")
definitions_text = definitions_file.read()
definitions_file.close()

# Find each unique color on the province map. Also get the 'inverse' of the map, which can be used to traverse a province's pixels more efficiently.
print("Getting unique provinces ...")
unique_prov_cols, prov_inverses = numpy.unique(province_map_flattened, return_inverse = True, axis = 0)
number_of_provs = len(unique_prov_cols)
prov_inverses_unflattened = prov_inverses.reshape([province_map.shape[0], province_map.shape[1]])

print("Discovered {} provinces.".format(number_of_provs))
highest_province_id = get_highest_province_id(definitions_text)
print("The ID at the bottom line of the existing definitions file was '{}'. All newly assigned IDs will count up from this value.".format(highest_province_id))
terrain_counts = {}
type_counts = {}

iterator = 0

# Cache various data about each province's terrain, type, and coastal status. These arrays are indexed by province number.
prov_terrains = numpy.empty(unique_prov_cols.shape[0], dtype = object)
prov_types = numpy.empty(unique_prov_cols.shape[0], dtype = object)
prov_coastal = numpy.zeros(unique_prov_cols.shape[0], dtype = bool)
prov_coastal_count = 0
sea_provs = set()

# For each province, find its 'dominant' terrain (the terrain color most common in that province's bounds) and the consequent type (if 'ocean', the type is sea, if 'lake' it's lake, otherwise it's land).
print("Finding dominant province terrains and types ...")
for p in range(len(unique_prov_cols)):
    iterator += 1
    print(iterator)

    prov_col = unique_prov_cols[p]
    dominant_terrain = get_terrain(terrain_map_flattened, prov_inverses == p)
    prov_terrains[p] = dominant_terrain
    if not dominant_terrain in terrain_counts:
        terrain_counts[dominant_terrain] = 0
    terrain_counts[dominant_terrain] += 1

    if dominant_terrain.name == "ocean":
        type_string = "sea"
        sea_provs.add(p)
    elif dominant_terrain.name == "lake":
        type_string = "lake"
    else:
        type_string = "land"

    if not type_string in type_counts:
        type_counts[type_string] = 0
    prov_types[p] = type_string
    type_counts[type_string] += 1

# For each sea province, check all of its neighboring provinces. If any of them are land, then this sea province and its neighbor are both coastal.
print("Determing coastal provinces ...")
iterator = 0
for s in sea_provs:
    iterator += 1
    print(iterator)
    
    neighboring_prov_indices = get_coastal_neighbors(prov_inverses_unflattened, s, province_map, sea_provs)
    if neighboring_prov_indices != None:
        prov_coastal[s] = True
        prov_coastal_count += 1
        for n in neighboring_prov_indices:
            prov_coastal[n] = True

        prov_coastal_count += len(neighboring_prov_indices)

# Use the discovered data to write a new definitions file.
print("Writing new definitions ...")
for p in range(len(unique_prov_cols)):
    prov_col = unique_prov_cols[p]

    start_index, end_index = get_province_line(prov_col, definitions_text)
    existing_definition = ""
    new_definition = ""

    if start_index == -1:
        new_definition += str(highest_province_id + 1) + ";"
        highest_province_id += 1
    else:
        existing_definition = definitions_text[start_index:end_index]
        id_semicolon = existing_definition.find(";")
        new_definition += existing_definition[0:id_semicolon] + ";"

    # A province definition uses the format "R_Value ; G_Value ; B_Value ; Type ; Is_Coastal? ; Terrain ; Continent", followed by a new line.
    new_definition += str(prov_col[0]) + ";" + str(prov_col[1]) + ";" + str(prov_col[2]) + ";" + prov_types[p] + ";" + str(prov_coastal[p]).lower() +  ";" + prov_terrains[p].name + ";" + "1"

    if start_index == -1:
        required_new_line = "\n" if len(definitions_text) > 0 and definitions_text[len(definitions_text) - 1] != "\n" else ""
        definitions_text += required_new_line + new_definition
    else:
        definitions_text = definitions_text[0:start_index] + new_definition + definitions_text[end_index:len(definitions_text)]

# Print some sanity-check logs to help the user be sure that everything is working okay (or indicate if something went wrong).
terrain_count_text = "Of {} provinces, the following percentages were of a given terrain:\n".format(number_of_provs)
for terrain in terrain_counts:
    terrain_count_text += terrain.name + ": " + str(terrain_counts[terrain] / number_of_provs * 100) + "%, "

type_count_text = "Of {} provinces, the following percentages were of a given type:\n".format(number_of_provs)
for type_str in type_counts:
    type_count_text += type_str + ": " + str(type_counts[type_str] / number_of_provs * 100) + "%, "

coastal_count_text = "Of {} provinces, the following percentages were coastal:\n{}".format(number_of_provs, str(prov_coastal_count / number_of_provs * 100) + "%")

print(terrain_count_text)
print(type_count_text)
print(coastal_count_text)

# If specified, automatically write the result to the existing definitions directory.
if edit_existing_definitions:
    new_definitions_file = open(definitions_output_dir, "w+")
    print("Writing new definitions text to '{}'".format(definitions_output_dir))
    new_definitions_file.write(definitions_text)
else:
    print("Will not write new definitions to existing directory '{}', set the 'edit_existing_definitions' flag in the provincial settings file to change this.").format(definitions_output_dir)

# Create a debug map to help show recognised terrain types.
for y in range(terrain_debug.shape[0]):
    for x in range(terrain_debug.shape[1]):
        period = (x + y) % 5
        if period >= 3 and period < 5:
            province_index = prov_inverses_unflattened[y, x]
            terrain_debug[y, x] = prov_terrains[province_index].display_col

map_dpi = terrain_debug.shape[0] / 10
pyplot.figure(figsize = (10, province_map.shape[1] / map_dpi), dpi = map_dpi)
pyplot.imshow(terrain_debug)
pyplot.axis('off')
pyplot.show()

# Create a second debug map to help show recognised coastal statuses.
for y in range(type_debug.shape[0]):
    for x in range(type_debug.shape[1]):
        period = (x + y) % 5
        if period >= 3 and period < 5:
            province_index = prov_inverses_unflattened[y, x]
            stripe_col = None
            if prov_coastal[province_index]:
                stripe_col = (255, 255, 0)
            else:
                prov_type = prov_types[province_index]
                stripe_col = (255, 0, 0) if prov_type == "sea" else ((0, 64, 127) if prov_type == "land" else (255, 127, 0))
                
            type_debug[y, x] = stripe_col

map_dpi = type_debug.shape[0] / 10
pyplot.figure(figsize = (10, province_map.shape[1] / map_dpi), dpi = map_dpi)
pyplot.imshow(type_debug)
pyplot.axis('off')
pyplot.show()

        
        
    
