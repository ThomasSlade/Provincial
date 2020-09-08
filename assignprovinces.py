# Provincial: Province handling tool for Hearts of Iron IV
# Thomas Slade, 2020

# Compares a filled-out province map to a map showing state areas, and outputs which provinces belong to which states.

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

# Find the unique state colors on the state map. This will also block-fill all states in the event that only borders have been drawn on the map.
def find_states(state_map):
    state_provs = {}

    discovered_states_array = numpy.unique(state_map.reshape(-1, state_map.shape[2]), axis = 0)

    for s in discovered_states_array:
        state_provs[tuple(s)] = []

    if ignore_col in state_provs:
        del state_provs[ignore_col]
    if paint_over_col in state_provs:
        del state_provs[paint_over_col]

    state_map = block_fill_states(state_map, state_provs.keys())
    
    return state_provs, state_map

# Fill in the areas inside of state borders, in case a border map was provided.
def block_fill_states(state_map, unique_cols):
    filled_map = state_map.copy()
    
    for u in unique_cols:
        state_mask, border_mask, x_min, y_min, x_max, y_max = get_state_mask(state_map, u)
        filled_map[y_min:y_max + 1, x_min:x_max + 1][numpy.where(state_mask)] = u

    return filled_map

# Searches a string for the '#COLOR' comment that can be placed in state files to bind a state to its color on the input map, and returns that color if it is found.
def get_col_comment(file_content):
    comment_index = file_content.find(color_comment_prefix)

    if comment_index == -1:
        return None
    else:
        newline_index = file_content.find("\n", comment_index)
        parsed_col = tuple(string_to_list(file_content[comment_index + len(color_comment_prefix):newline_index]))
        return parsed_col

def get_constituent_provinces(state_map, province_map, definitions_text):
    state_map_flattened = state_map.reshape(-1, state_map.shape[2])
    province_map_flattened = province_map.reshape(-1, province_map.shape[2])

    unique_prov_cols, prov_indices, prov_inverses = numpy.unique(province_map_flattened, return_index = True, return_inverse = True, axis = 0)

   # unique_prov_cols =  set(tuple(map(tuple, numpy.unique(province_map.reshape(-1, province_map.shape[2]), axis = 0))))
    unique_prov_cols = numpy.delete(unique_prov_cols, numpy.where((unique_prov_cols == ignore_col).all() or (unique_prov_cols == paint_over_col).all()), axis = -1)

    print("\nFound {} provinces on the province map.".format(len(unique_prov_cols)))

    i = 0
    
    for p in range(len(unique_prov_cols)):
        prov_col = unique_prov_cols[p]

        prov_pixels = prov_inverses == p# numpy.where(logical_and.reduce(province_map == p, axis = -1))

        # Need to convert the origin back to a 2D array index.
        prov_origin = [math.floor(prov_indices[p] / province_map.shape[0]), prov_indices[p] % province_map.shape[0]]
        state_cols, state_col_counts = numpy.unique(state_map_flattened[prov_pixels], axis = 0, return_counts = True)

        print(i)
        i += 1

        if len(state_cols) == 1:
            if (state_cols[0] == ignore_col).all() or (state_cols[0] == paint_over_col).all():
                orphan_provs.append(prov_origin)
            else:
                state_provs[tuple(state_cols[0])].append(get_province_id(prov_col, definitions_text))
        else:
            largest_count = 0
            largest_index = -1
            for c in range(len(state_col_counts)):
                if state_col_counts[c] > largest_count:
                    largest_count = state_col_counts[c]
                    largest_index = c

            if largest_count / len(prov_pixels) < min_tolerated_province_split:
                split_provs.append(prov_origin)
            else:
                state_provs[tuple(state_cols[largest_index])].append(get_province_id(prov_col, definitions_text))

    empty_states = []
    assigned_prov_count = 0
    for state in state_provs:
        if len(state_provs[state]) == 0:
            empty_states.append(state)
        else:
            assigned_prov_count += len(state_provs[state])
    
    if len(empty_states) > 0:
         print("\n{} states will be ignored because they contain no provinces. No files will be generated for them, and they won't have a province-block printout.".format(len(empty_states)))
    for e in empty_states:
        del state_provs[e]

    print("\nAssigned {} / {} provinces to {} states.".format(assigned_prov_count, len(unique_prov_cols), len(state_provs)))

# Update the state's content string with the new provinces. Returns true if any change actually took place.
def replace_province_definitions(state_col, provinces):
    state_script = state_file_contents[state_col]
    state_name = state_file_dirs[state_col]

    existing_provinces_string = get_field_content(state_script, "provinces", True)
    existing_provinces = string_to_list(existing_provinces_string)
    any_province_changes = existing_provinces != provinces
    
    if any_province_changes:
        state_script = set_field_content(state_script, "provinces", list_to_string(provinces), True)

    replace_vp_block = False
    clear_vp_block = False
    
    # Handle the victory point block.
    vp_string = get_field_content(state_script, "victory_points", True)
    if any_province_changes and vp_string is not None:
        vp_set = set(string_to_list(vp_string))
        missing_vps = vp_set - existing_provinces
        
        if missing_vps:
            if victory_point_handling == 0:
                print("The following victory points of state '{}' were not present in that state's new set of provinces: {}".format(state_name, list_to_string(missing_vps, ", ")))
            elif victory_point_handling == 1:
                vp_set -= missing_vps
                if len(vp_set) == 0:
                    clear_vp_block = True
                else:
                    replace_vp_block = True
            elif victory_point_handling == 2:
                clear_vp_block = True
        if replace_vp_block:
            state_script = set_field_content(state_script, "victory_points", list_to_string(vp_set), True)
        elif clear_vp_block:
            state_script = delete_field(state_script, "victory_points", True)

    state_file_contents[state_col] = state_script
    return any_province_changes or clear_vp_block or replace_vp_block

# Get text to populate a new template state file for the argued state.
def get_template_content(state, state_id):
    output = color_comment_prefix + " " + list_to_string(state) + "\n" + template_text

    try:
        output = set_field_content(output, "id", str(state_id))

        output = set_field_content(output, "name", str(state))
        output = set_field_content(output, "provinces", list_to_string(state_provs[state]), True)
    except Exception as exc:
        raise Exception("Failure when creating state template file for state '{}'".format(state))
    return output

# Read the file associated with the argued state and register its ID number.
def register_state_id(state):
    state_script = state_file_contents[state]
    state_name = state_file_dirs[state]
    id_field_ind = state_script.find("id=")
    if id_field_ind == -1:
        id_field_ind = state_script.find("id = ")
    if id_field_ind == -1:
        raise Exception("The state file for state '{}' did not contain an id field of format 'id=' or 'id ='. This field should be present in all HoI state files.")
    id_field_ind += 3
    end_ind = state_script.find("\n", id_field_ind)
    registered_id = int(state_script[id_field_ind:end_ind])
    registered_ids.add(registered_id)

# Figure out where the template ID count should start.
def get_lowest_available_state_id(current_id, mode):
    lowest_found = current_id
    
    if mode == 1:
        while True:
            if lowest_found in registered_ids:
                lowest_found += 1
            else:
                break
    elif mode == 2:
        for ids in registered_ids:
            if ids > lowest_found:
                lowest_found = ids
        lowest_found += 1

    return lowest_found

def get_state_name(state_col, state_id = -1):
    if state_col in state_file_dirs:
        return state_file_dirs[state_col]
    else:
        state_id_text = ""
        if state_id == -1:
            state_id_text = "?"
        else:
            state_id_text = str(state_id)
            
        new_name = template_naming_format
        id_ind = new_name.find("$")
        if id_ind != -1:
            new_name = new_name[0:id_ind] + state_id_text + new_name[id_ind + 1:len(new_name)]

        name_ind = new_name.find("@")
        if name_ind != -1:
            new_name = new_name[0:name_ind] + "UNNAMED STATE " + str(state_col) + new_name[name_ind + 1:len(new_name)]
        return new_name
            
### Main Program ###
province_map = io.imread(province_map_dir)  # The map containing the provinces.
state_map = io.imread(state_map_dir)    # The map containing the states, which may either be block-filled or borders.
debug_map = province_map.copy() # Used as the base image for showing important output locations.
state_files_dir_context = state_files_dir # The appropriate directory of the state files.
province_definitions_dir_context = province_definitions_dir # The appropriate directory of the province definitions csv.
state_files_count = 0 # The number of state files found.
state_files_with_col_count = 0 # The number of state files found that had a color comment.
state_file_contents = {}    # The text from any discovered state files, keyed by their state color.
state_file_dirs = {}    # The file names of each state file, keyed by their color.
state_provs = {}    # The provinces belonging to each state, keyed by their state color.
orphan_provs = []   # Coordinates of any provinces found which are not in any states.
split_provs = [] # Coordinates of provinces that are excessively split between multiple states, indicating an inconsistency between the province and state map.
definitions_text = ""   # The loaded text from the definitions file.
template_text = ""  # The loaded text used to populate an auto-generated state file.
lowest_available_state_id = 1 # The number next available to be used as a state ID, given the currently detected state IDs in existing state files.
registered_ids = set()  # A set containing all state IDs that have been read from existing files or added to new files.

try:
    if mod_path_absolute:
        my_path = path.abspath(path.dirname(__file__))
        state_files_dir_context = path.join(my_path, state_files_dir)
        province_definitions_dir_context = path.join(my_path, province_definitions_dir)

    print("\nIdentifying states ...")
    state_provs, state_map = find_states(state_map)

    # Make the state overlay on the debug map diagonally stripey.
    for y in range(debug_map.shape[0]):
        for x in range(debug_map.shape[1]):
            period = (x + y) % 5
            if period >= 3 and period < 5:
                debug_map[y, x] = state_map[y, x]

    print("\n{} state colours found in {}.".format(len(state_provs), state_map_dir))

    if path.exists(state_files_dir_context):
        state_file_dirs_array = listdir(state_files_dir_context)
        state_files_count = len(state_file_dirs_array)
        print("\nFound {} state files under '{}'.".format(state_files_count, state_files_dir_context))

        for s_dir in state_file_dirs_array:
            state_file = open(state_files_dir_context + s_dir, "r")
            contents = state_file.read()
            state_file.close()

            state_col = get_col_comment(contents)
            if state_col is not None:
                state_files_with_col_count = state_files_with_col_count + 1
                state_file_contents[state_col] = contents
                state_file_dirs[state_col] = s_dir

                register_state_id(state_col)
    else:
        print("\n'{}' state file directory not found, so this script is unable to infer any state names. States will be labelled with their RGB value instead.".format(state_files_dir_context))

    definitions_file = open(province_definitions_dir_context, "r")
    definitions_text = definitions_file.read()
    definitions_file.close()
    definitions_lines = definitions_text.count("\n")

    print("\nDefinitions file read with {} lines of text. Now attempting to assign province IDs to states using the province and state map ...".format(definitions_lines))
    get_constituent_provinces(state_map, province_map, definitions_text)

    abort_overwriting = False
    if len(split_provs) > 0:
        for s in split_provs:
            paste(debug_map, get_dot((255, 175, 0), (255, 255, 255)), s)

        print("\n{} provinces were found to be spread ambiguously between different states, with less than {}% of their pixels on a single state. Province assignment will not continue.".format(len(split_provs), min_tolerated_province_split * 100) +
              " Are there inconsistencies between your state borders and province borders in the state/province maps?\nSee the orange dots on the debug map.")
        abort_overwriting = True
        
    if not abort_overwriting:
        # With the constituent provinces assigned to each state on the state map, determine what to do with these findings based on the tool settings.
        # If writing to files ...
        if write_to_state_files:
            vp_handling_log = ""
            if victory_point_handling == 0:
                vp_handling_log = "No victory point definitions will be changed, but a warning will be printed if any VPs in a state file are removed from that state's province list."
            elif victory_point_handling == 1:
                vp_handling_log = "Victory points in a state that has the relevant province removed will also be removed from that province's file."
            elif victory_point_handling == 2:
                vp_handling_log = "If a state has any changes to its province set, all of its victory points will be cleared."
            else:
                raise Exception("Error: Invalid victory_point_handling value of {}".format(victory_point_handling))

            state_id_handling_log = ""
            if template_state_id_handling == 0:
                state_id_handling_log = "State IDs will not be written over in generated template files."
            elif template_state_id_handling == 1:
                state_id_handling_log = "State IDs will take the lowest number available to them."
            elif template_state_id_handling == 2:
                state_id_handling_log = "State IDs will take the number above the highest ID in existing state files."
            else:
                raise Exception("Error: Invalid template_state_id_handling value of {}".format(victory_point_handling))
            
            print("\nWriting new provinces to state files.\n{}\n{}".format(vp_handling_log, state_id_handling_log))
            lowest_available_state_id = get_lowest_available_state_id(lowest_available_state_id, state_id_handling_log)

            state_files_changed = 0
            fileless_states = []
            
            for state in state_provs:
                if state in state_file_contents:
                    if replace_province_definitions(state, state_provs[state]):
                        state_files_changed += 1
                        state_file = open(state_files_dir_context + state_file_dirs[state], "w")
                        state_file.write(state_file_contents[state])
                        state_file.close()
                else:
                    fileless_states.append(state)
                    print("\nThe state of color '{}' did not have an associated file marked by a color comment.".format(state))
                    
            print("\Overwriting complete. Wrote over {} / {} state file contents ...".format(state_files_changed, len(state_provs)))
            if len(fileless_states) > 0:
                state_handling_log = ""
                if fileless_state_handling == 0:
                    state_handling_log = " Creating template files for these states ..."
                elif fileless_state_handling == 1:
                    state_handling_log = " Printing the province blocks in the log ..."
                else:
                    raise Exception("Error: fileless_state_handling had an invalid value of {}".format(state_handling_log))
                print("\n{} states did not have associated files. ".format(len(fileless_states)) + state_handling_log)

                if fileless_state_handling == 0:
                    if not path.exists("StateFileTemplate.txt"):
                        raise Exception("Cannot automatically generated state files from a template because there is no file named 'StateFileTemplate.txt' in the same directory as this script.")
                    template_file = open("StateFileTemplate.txt", "r")
                    template_text = template_file.read()
                    template_file.close()

                    for fileless in fileless_states:
                        template_content = get_template_content(fileless, lowest_available_state_id)

                        new_state_file = open(state_files_dir_context + get_state_name(fileless, lowest_available_state_id), "w+")
                        new_state_file.write(template_content)
                        new_state_file.close()

                        registered_ids.add(lowest_available_state_id)
                        lowest_available_state_id = get_lowest_available_state_id(lowest_available_state_id, template_state_id_handling)
                elif fileless_state_handling == 1:
                    for fileless in fileless_states:
                        print(get_state_name(fileless) + ":\n{" + list_to_string(state_provs[fileless]) + "\n}")
                print("\nTemplate file creation complete.")
            
        # If not writing to files, print the findings in the log.
        else:
            print("\nOutputting new province blocks in the log ...")
            
            for state in state_provs:
                state_name = ""
                prov_block = ""
                if state in state_file_contents:
                    state_name = state_file_dirs[state]
                    state_script = state_file_contents[state]

                    existing_provinces = string_to_list(get_field_content(state_script, "provinces", True))
                    
                    if existing_provinces != state_provs[state]:
                        prov_block = "{" + list_to_string(state_provs[state]) + "\n}"
                    else:
                        prov_block = "No changes from the state's file."
                else:
                    state_name = str(state)
                    prov_block = "{"  + list_to_string(state_provs[state]) + "\n}"

                print(get_state_name(state) + ":\n" + prov_block)

            print("\nOutput complete.")

    map_dpi = debug_map.shape[0] / 10
    pyplot.figure(figsize = (10, province_map.shape[1] / map_dpi), dpi = map_dpi)
    pyplot.imshow(debug_map)
    pyplot.axis('off')
    pyplot.show()

except Exception as exc:
    print("\nError: Provinces were not assigned.\n" + str(exc))
    traceback.print_exc()
