# Provincial: Province handling tool for Hearts of Iron IV
# Thomas Slade, 2020

# Adjusts text and file names of all files found under the target directory to be within the appropriate format.
# This is useful for quickly and correctly naming and ID-ing the default '1-Bavaria.txt' files that HoI creates when map editing, giving them sequential IDs and correctly formatted names.

import sys
import traceback
import re
from os import path, listdir, rename
from provincialutils import *
from provincialsettings import *

def get_lowest_id():
    incremented_id = lowest_available_id
    while True:
        if incremented_id not in id_set:
            return incremented_id
        
        incremented_id += 1

### Main Program ###
format_target_dir_context = format_target_dir
file_dirs = []
file_contents = []
ids = []
names = []
lowest_available_id = 1
id_set = set()

try:
    if mod_path_absolute:
        my_path = path.abspath(path.dirname(__file__))
        stratregion_dir_context = path.join(my_path, format_target_dir)

    # Load all the files in the target directory.
    if path.exists(format_target_dir_context):
        file_dirs = listdir(format_target_dir_context)
        file_count = len(file_dirs)
        print("Found {} files for formating under directory '{}'".format(file_count, format_target_dir_context))

        for file_dir in file_dirs:
            file = open(format_target_dir_context + file_dir, "r")
            file_contents.append(file.read())
            file.close()
    else:
        print("'{}' directory not found, so the script cannot perform its reformat.".format(format_target_dir_context))

    # Get all of the existing names and ids from the loaded files.
    for i in range(len(file_contents)):
        content = file_contents[i]
        file_dir = file_dirs[i]
        
        content_id = int(get_field_content(content, format_id_target))
        content_name = ""
        if format_name_target == "FILENAME":
            # Remove the '.txt'
            content_name = file_dir[0:-4]
        else:
            content_name = get_field_content(content, format_name_target)
        id_set.add(content_id)
        ids.append(content_id)
        names.append(content_name)

    discovered_first_one_id = False
    for i in range(len(file_contents)):
        content = file_contents[i]
        content_id = ids[i]
        content_name = names[i]

        if content_id == 1:
            if discovered_first_one_id:
                content_id = get_lowest_id()
                id_set.add(content_id)
            else:
                discovered_first_one_id = True

        # If the name of the content has any numbers in it, remove the first number and any dash or underscore that follows.
        numbers_in_name = [match.end(0) for match in re.finditer(r'\d+', content_name)]
        if len(numbers_in_name) > 0:
            number_termination = numbers_in_name[0]
            if len(content_name) > number_termination + 1 and content_name[number_termination] == '_' or content_name[number_termination] == '-':
                number_termination += 1

            content_name = content_name[number_termination:]

        final_name = naming_format.replace('$', str(content_id))
        final_name = final_name.replace('@', content_name)

        # Hardcoded id and name targets. Needs to be fixed later.
        content = set_field_content(content, "id", str(content_id))
        content = set_field_content(content, "name", final_name)

        names[i] = final_name
        ids[i] = content_id
        file_contents[i] = content

    for i in range(len(file_dirs)):
        file = open(format_target_dir_context + file_dirs[i], "w+")
        file.write(file_contents[i])
        file.close()

        rename(format_target_dir_context + file_dirs[i], format_target_dir_context + names[i] + ".txt")
        

except Exception as exc:
    print("\nError: Filegroup was not reformatted.\n" + str(exc))
    traceback.print_exc()
