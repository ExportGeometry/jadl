'''
MIT License

Copyright (c) 2024 Mason Stevenson

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''


'''
JSON Asset Definition Library (jadl)

Utility functions for loading node parameters from JSON.

Author: Mason Stevenson
Version: 1.0
Currently supported controls file:           jadl_controls_v1.4.ds
Currently supported pdg controls file:       jadl_pdg_v1.0.ds
'''
import hou
import json
import os.path

# JSON Keys
JK_ALL_DEFS = 'asset_definitions'
JK_ASSET_NAME = 'name'

# Keys that reference asset definition parameters must be prefixied with this
# or they will be ignored.
PARM_ID_PREFIX = 'pi_'

# Multiparms
MULTIPARM_ID_PREFIX = 'mpi_'
MULTIPARM_CONTROLLER_PREFIX = 'mpc_'
MULTIPARM_INDEX_WILDCARD = '#'

# Cached User Data Ids
CUD_JSON_DATA = 'json_data'

# Houdini Node Parm IDs
PI_ASSET_DEFS_ENABLED = 'asset_defs_enabled'
PI_ENABLE_LOGGING = 'enable_logging'
PI_PDG_ENABLED = 'pdg_enabled'
PI_ASSET_ID = 'asset_def_name'
PI_ASSET_MENU = 'asset_def_menu'
PI_CHANGED_PARM_COUNT = 'changed_parms'
PI_JSON_FILE_PATH = 'json_file_path'
PI_CREATE_MISSING_FILE = 'create_missing_file'

# Work Item Attribute Ids
WIA_ASSET_NAME = 'asset_name'
WIA_ASSET_INDEX = 'asset_index'

def about():
    print('************* JSON Asset Definition Library v1.0.0 ****************')
    print('Currently supported controls file:           jadl_controls_v1.4.ds')
    print('Currently supported pdg controls file:       jadl_pdg_v1.0.ds')
    print('*******************************************************************')

def log(node, msg, check_enabled=True):
    if (check_enabled):
        logging_parm = node.parm(PI_ENABLE_LOGGING)

        if (not logging_parm):
            print('WARNING: missing logging parm (' + PI_ENABLE_LOGGING + ') (original message: ' + msg + ')')
            return
        if (not logging_parm.eval()):
            return

    print(msg)

def eval_parm_safe(node, path):
    if (node.parm(path)):
        return node.evalParm(path)
    
    return None

def clear_multiparm_parent(node, parm):
    if (not parm.isMultiParmParent()):
        log(None, 'Expected parm "' + parm.name() + '" to be a multiparm parent.', False)
        return
    
    # Note: parm.multiParmInstancesCount() doesn't do what it sounds like. It
    #       actually grabs num_instances x parms_per_instance. But this is moot
    #       since you can actaully just eval the multiparm folder to get the
    #       count.
    num_instances = parm.eval()

    while (num_instances > 0):
        parm.removeMultiParmInstance(num_instances - 1)
        num_instances = parm.eval()

    multiparm_controller_name = MULTIPARM_CONTROLLER_PREFIX + parm.name().removeprefix(MULTIPARM_ID_PREFIX)
    multiparm_controller = node.parm(multiparm_controller_name)
    if (multiparm_controller):
        multiparm_controller.set(0)

def extract_multiparm_data(parm):
    parent_name = parm.parentMultiParm().name()
    tokens = parm.name().split('_')
    last_token = tokens[len(tokens) - 1]
    multiparm_index = int(last_token[0]) - 1
    tokens[len(tokens) - 1] = MULTIPARM_INDEX_WILDCARD + last_token[1:]
    wildcard_parm_id = '_'.join(tokens)
    return (parent_name, multiparm_index, wildcard_parm_id)

def add_or_set_detail_attr(node, attr_id, value):
    geo = node.geometry()

    existing_attribute = geo.findGlobalAttrib(attr_id)
    if (existing_attribute):
        try:
            geo.setGlobalAttribValue(attr_id, value)
        except hou.OperationFailed as ex:
            log(
                None,
                'Failed to update detail attribute on node. This is ' + 
                'most likely caused by a type mismatch between your JSON ' +
                'data and existing attribute type. ' + 
                '\nOriginal error: \n' + repr(ex) + ' ' + str(ex),
                False
            )
    else:
        geo.addAttrib(hou.attribType.Global, attr_id, value)
        geo.setGlobalAttribValue(attr_id, value)

def is_manual_mode(node):
    if (node.type().name() == 'hdaprocessor'):
        return False

    return (
        node.evalParm(PI_ASSET_DEFS_ENABLED) and
        not eval_parm_safe(node, PI_PDG_ENABLED)
    )

def force_cook(node):
    if (not is_manual_mode(node)):
        log(node, 'error: tried to call force_cook for automated process.')
        return

    node.cook(force=True)

def get_empty_json_data():
    json_data = {}
    json_data[JK_ALL_DEFS] = []
    return json_data

def load_json_data(node, path=None):  
    json_data = get_empty_json_data()

    json_file_path = path if path else node.evalParm(PI_JSON_FILE_PATH)
    create_if_missing = node.evalParm(PI_CREATE_MISSING_FILE)

    if (json_file_path == ''):
        return json_data

    if (not json_file_path.lower().endswith('.json')):
        log(node, 'unable to load json data. file path does not end in .json: ' + json_file_path, False)
        return json_data

    if (not os.path.isfile(json_file_path) and create_if_missing):
        with open(json_file_path, 'w') as new_file:
            json.dump(json_data, new_file)


    if (os.path.isfile(json_file_path)):
        log(node, 'loading json data from: ' + json_file_path)
    else:
        log(node, 'unable to load json data. file is missing: ' + json_file_path, False)
        return json_data

    with open(json_file_path, 'r') as json_file:
        json_data = json.load(json_file)

    return json_data

def get_cached_json_data(node):
    if (not is_manual_mode(node)):
        log(node, "error: tried to call get_cached_json_data for automated process.")
        return

    cached_node_data = node.cachedUserDataDict()

    if (CUD_JSON_DATA not in cached_node_data):
        json_data = load_json_data(node)
        if (not json_data):
            return
        node.setCachedUserData(CUD_JSON_DATA, json_data)
        cached_node_data = node.cachedUserDataDict()

    return cached_node_data.get(CUD_JSON_DATA, {})

def get_asset_def_index(node):
    asset_def_name = node.evalParm(PI_ASSET_ID)
    menu_labels = node.parm(PI_ASSET_MENU).menuLabels()

    if (asset_def_name == '' or asset_def_name not in menu_labels):
        return max(len(menu_labels) - 1, 0)

    # Match the asset definition index to whatever is currently in the name
    # field, NOT which menu item is actually selected. This fixes bugs that
    # manifest when the user picks an asset def, changes the PI_ASSET_ID
    # text field, then presses the save button.
    return menu_labels.index(asset_def_name)

def update_changed_parms(node):
    print('update_changed_parms is DEPRECATED. Use parm_changed.')

""" Callback for when a JSON-linked parm has changed in the UI.

This fn works by scanning through the cached data associated with the current
asset and checking if the manual controls on the associated node match the
values in the cache. A count of how many params have been changed will be
propagated up to the PI_CHANGED_PARM_COUNT parm, which is how the 'Save Asset'
button knows to enable or disable itself.

Usage:
    Add the following to the callback script of each of your linked parameters:

    __import__('jadl').parm_changed(kwargs['node'], kwargs['parm'])
"""
def parm_changed(node, target_parm):
    if (target_parm):
        target_name = target_parm.name()
        if (target_name.startswith(MULTIPARM_CONTROLLER_PREFIX)):
            multiparm_parent_name = MULTIPARM_ID_PREFIX + target_name.removeprefix(MULTIPARM_CONTROLLER_PREFIX)
            multiparm_parent = node.parm(multiparm_parent_name)
            if (not multiparm_parent):
                log(None, 'WARNING: expected node named "' + multiparm_parent_name + '" to exist.', False)

            multiparm_parent.set(target_parm.eval())
    
    if (not is_manual_mode(node)):
        return

    asset_def_index = get_asset_def_index(node)

    json_data = get_cached_json_data(node)
    if (json_data is None):
        return
    
    asset_defs = json_data[JK_ALL_DEFS]

    if (asset_defs is None or asset_def_index > len(asset_defs)):
        return
    if (asset_def_index == len(asset_defs)):
        node.parm(PI_CHANGED_PARM_COUNT).set(-1)
        return

    current_asset = asset_defs[asset_def_index]
    changed_parms = 0
    all_parms = set()
    all_multiparms = set()
    changed_parm_names = set() # for debugging

    # scan JSON data
    for parm_id in current_asset:
        if (parm_id.startswith(PARM_ID_PREFIX)):
            all_parms.add(parm_id)
        elif (parm_id.startswith(MULTIPARM_ID_PREFIX)):
            all_multiparms.add(parm_id)

    # scan node
    for parm in node.parms():
        parm_id = parm.name()
        if (parm_id.startswith(PARM_ID_PREFIX)):
            all_parms.add(parm_id)
        elif (parm_id.startswith(MULTIPARM_ID_PREFIX)):
            all_multiparms.add(parm_id)

    for multiparm_id in all_multiparms:
        parm = node.parm(multiparm_id)
        if (not parm):
            log(None, 'Warning: multiparm "{}" is null'.format(multiparm_id), False)
            continue

        if (not parm.isMultiParmParent()):
            log(None, 'Warning: expected parm "' + parm.name() + '" to be a multiparm parent.', False)
            continue
        
        multiparm_count = parm.eval()

        if (
                # it's okay if the multiparm is empty in the UI and missing in
                # the JSON file, but not if it is empty in the UI and present
                # in the JSON file.
                multiparm_count == 0 and
                multiparm_id in current_asset and
                multiparm_count != len(current_asset[multiparm_id])
            ) or (
                multiparm_count > 0 and (
                    multiparm_id not in current_asset or 
                    multiparm_count != len(current_asset[multiparm_id])
            )
        ):
            changed_parms += 1
            changed_parm_names.add(multiparm_id)
    
    for parm_id in all_parms:
        parm = node.parm(parm_id)
        if (not parm):
            log(None, 'Warning: parm "{}" is null'.format(parm_id), False)
            continue

        if (parm.isMultiParmInstance()):
            parent_name, multiparm_index, wildcard_id = extract_multiparm_data(parm)
            if (parent_name not in current_asset):
                continue
            multiparm_list = current_asset[parent_name]
            if (type(multiparm_list) is not list or multiparm_index < 0 or multiparm_index >= len(multiparm_list)):
                continue
            multiparm_dict = multiparm_list[multiparm_index]
            if (type(multiparm_dict) is not dict):
                continue
            if (multiparm_dict[wildcard_id] != parm.eval()):
                changed_parms += 1
                changed_parm_names.add(parent_name + ':' + wildcard_id + ':' + str(multiparm_index))
        elif (parm_id not in current_asset or parm.eval() != current_asset[parm_id]):
            changed_parms += 1
            changed_parm_names.add(parm_id)

    # print(changed_parm_names) # DEBUG
    node.parm(PI_CHANGED_PARM_COUNT).set(changed_parms)


def clear_asset_defs(node):
    if (not is_manual_mode(node)):
        log(node, 'error: tried to call clear_asset_defs for automated process.')
        return
                
    multiparms_to_clear = []

    for parm in node.parms():
        parm_id = parm.name()

        if (parm_id.startswith(PARM_ID_PREFIX)):
            parm.revertToDefaults()
        elif (parm_id.startswith(MULTIPARM_ID_PREFIX)):
                multiparms_to_clear.append(parm)
        
    for parm in multiparms_to_clear:
        clear_multiparm_parent(node, parm)

def set_manual_controls(node, reset_parms=True):
    if (not is_manual_mode(node)):
        log(node, 'error: tried to call set_manual_controls for automated process.')
        return

    asset_def_index = get_asset_def_index(node)

    json_data = get_cached_json_data(node)
    asset_defs = json_data[JK_ALL_DEFS]

    if (asset_defs is None or asset_def_index > len(asset_defs)):
        return

    # We need to always revert everything to default first because the
    # definition file might not have a reference to all the linked parms. We
    # should always assume default value if the asset def is missing.
    #
    # The exception to this is when the file is first loaded, since no asset
    # should be chosen yet.
    if (reset_parms):
        clear_asset_defs(node)

    # special 'new asset definition' index
    if (asset_def_index == len(asset_defs)):
        return


    current_asset = asset_defs[asset_def_index]

    for parm_id, value in current_asset.items():
        if (parm_id.startswith(PARM_ID_PREFIX)):
            current_parameter = node.parm(parm_id)

            if (current_parameter):
                node.parm(parm_id).set(value)
            else:
                log(node, 'Warning: found unknown parameter name in json file (' + parm_id + ')')
        elif (parm_id.startswith(MULTIPARM_ID_PREFIX)):
            instance_count = len(value)
            node.parm(parm_id).set(instance_count)
            multiparm_controller_name = MULTIPARM_CONTROLLER_PREFIX + parm_id.removeprefix(MULTIPARM_ID_PREFIX)
            multiparm_controller = node.parm(multiparm_controller_name)
            if (multiparm_controller):
                multiparm_controller.set(instance_count)

            multiparm_index = 1

            for multiparm_map in value:
                for multiparm_id, multiparm_value in multiparm_map.items():
                    if (not multiparm_id.startswith(PARM_ID_PREFIX)):
                        continue
                    
                    indexed_id = multiparm_id.replace(MULTIPARM_INDEX_WILDCARD, str(multiparm_index))
                    node.parm(indexed_id).set(multiparm_value)
                multiparm_index += 1

def asset_def_menu_callback(node, reset_parms=True):
    if (not is_manual_mode(node)):
        return

    menu_labels = node.parm(PI_ASSET_MENU).menuLabels()

    if (not menu_labels):
        log(node, 'warning: expected there to be at least one menu label')
        return

    asset_def_index = node.evalParm(PI_ASSET_MENU)
    current_label = menu_labels[asset_def_index]

    if (asset_def_index == len(menu_labels) - 1):
        node.parm(PI_ASSET_ID).set('')
    else:
        node.parm(PI_ASSET_ID).set(current_label)


    set_manual_controls(node, reset_parms)
    parm_changed(node, None)

def force_reload(node, menu_index=-1, reset_parms=True):
    if (not is_manual_mode(node)):
        return

    if (node.cachedUserData(CUD_JSON_DATA)):
        node.destroyCachedUserData(CUD_JSON_DATA)
    json_data = get_cached_json_data(node)

    # This will force the asset definition menu to rebuild itself. It will not
    # actually trigger the internal network to recook.
    force_cook(node)

    asset_defs = json_data[JK_ALL_DEFS]

    if (menu_index < 0):
        node.parm(PI_ASSET_MENU).set(len(asset_defs))
    else:
        node.parm(PI_ASSET_MENU).set(menu_index)
    asset_def_menu_callback(node, reset_parms)

def update_asset_def(node, is_delete=False):
    if (not is_manual_mode(node)):
        log(node, 'error: tried to call update_asset_def for automated process.')
        return

    asset_def_index = get_asset_def_index(node)

    json_data = get_cached_json_data(node)
    asset_defs = json_data[JK_ALL_DEFS]

    if (asset_defs is None or asset_def_index > len(asset_defs)):
        return
    if (is_delete and asset_def_index == len(asset_defs)):
        log(node, 'error: invalid deletion index.')
        return

    asset_def_data = {}

    if (not is_delete):
        asset_def_name = node.evalParm(PI_ASSET_ID)
        asset_def_data[JK_ASSET_NAME] = asset_def_name
        
        for parm in node.parms():
            parm_id = parm.name()

            if (not parm_id.startswith(MULTIPARM_ID_PREFIX)):
                continue

            if (not parm.isMultiParmParent()):
                log(None, 'Expected parm "' + parm.name() + '" to be a multiparm parent.', False)
                return
            
            asset_def_data[parm_id] = [{} for _ in range(parm.eval())]

        for parm in node.parms():
            if (not parm.name().startswith(PARM_ID_PREFIX)):
                continue

            if (parm.isMultiParmInstance()):
                parent_name, multiparm_index, wildcard_id = extract_multiparm_data(parm)
                asset_def_data[parent_name][multiparm_index][wildcard_id] = parm.eval()
            else:
                asset_def_data[parm.name()] = parm.eval()

    if (is_delete):
        asset_defs.pop(asset_def_index)
        asset_def_index = len(asset_defs)
    elif (asset_def_index == len(asset_defs) or node.parm(PI_ASSET_MENU).menuLabels()[asset_def_index] != asset_def_name):
        # create new asset definition
        asset_def_index = len(asset_defs)
        asset_defs.append(asset_def_data)
    else:
        # edit existing asset definition
        asset_defs[asset_def_index] = asset_def_data

    json_data[JK_ALL_DEFS] = asset_defs

    json_file_path = node.evalParm(PI_JSON_FILE_PATH)
    if (os.path.isfile(json_file_path) and json_file_path.lower().endswith('.json')):
        log(node, 'writing json data to: ' + json_file_path)
    else:
        log(node, 'unable to write json data. path is invalid: ' + json_file_path)
        return

    json_serialized = json.dumps(json_data, indent=4)

    with open(json_file_path, 'w') as json_file:
        json_file.write(json_serialized)

    force_reload(node, asset_def_index)

def load_detail_attributes(generator_node, target_node, asset_index):
    if (eval_parm_safe(generator_node, PI_PDG_ENABLED)):
        json_data = load_json_data(generator_node)
        
        if (not json_data or JK_ALL_DEFS not in json_data):
            return
        
        asset_defs = json_data[JK_ALL_DEFS]

        if (asset_index < 0 or asset_index >= len(asset_defs)):
            return

        asset_def = asset_defs[asset_index]
        multiparms_to_clear = []

        for parm in generator_node.parms():
            parm_id = parm.name()
                
            if (parm_id.startswith(MULTIPARM_ID_PREFIX)):
                multiparms_to_clear.append(parm)
        for parm in multiparms_to_clear:
            clear_multiparm_parent(generator_node, parm)

        # We revert all parms in the top level node to their defaults so that if
        # a parm is missing from the JSON file, we can just use the default
        # value from the top level node.
        for parm in generator_node.parms():
            parm_id = parm.name()

            if (parm_id.startswith(PARM_ID_PREFIX)):
                stripped_id = parm_id.removeprefix(PARM_ID_PREFIX) # python 3.9+

                # There does not appear to be a parm.getDefaultValue() fn, so instead
                # we are just reverting the parm first and then grabbing its value.
                parm.revertToDefaults()
                add_or_set_detail_attr(target_node, stripped_id, parm.eval())

        for parm_id, value in asset_def.items():
            # Add parm from JSON file
            if (parm_id.startswith(PARM_ID_PREFIX)):
                stripped_id = parm_id.removeprefix(PARM_ID_PREFIX) # python 3.9+
                add_or_set_detail_attr(target_node, stripped_id, value)
            
            # Add multiparms from JSON file
            elif (parm_id.startswith(MULTIPARM_ID_PREFIX)):
                stripped_id = parm_id.removeprefix(MULTIPARM_ID_PREFIX) # python 3.9+
                add_or_set_detail_attr(target_node, stripped_id, len(value))

                multiparm_index = 1

                for multiparm_map in value:
                    for multiparm_id, multiparm_value in multiparm_map.items():
                        if (not multiparm_id.startswith(PARM_ID_PREFIX)):
                            continue
                        
                        stripped_id = multiparm_id.removeprefix(PARM_ID_PREFIX) # python 3.9+
                        indexed_id = stripped_id.replace(MULTIPARM_INDEX_WILDCARD, str(multiparm_index))
                        add_or_set_detail_attr(target_node, indexed_id, multiparm_value)
                    multiparm_index += 1

        add_or_set_detail_attr(target_node, JK_ASSET_NAME, asset_def[JK_ASSET_NAME])

    else:
        for parm in generator_node.parms():
            parm_id = parm.name()

            if (parm_id.startswith(PARM_ID_PREFIX)):
                stripped_id = parm_id.removeprefix(PARM_ID_PREFIX) # python 3.9+
                add_or_set_detail_attr(target_node, stripped_id, parm.eval())
            elif (parm_id.startswith(MULTIPARM_ID_PREFIX)):
                stripped_id = parm_id.removeprefix(MULTIPARM_ID_PREFIX) # python 3.9+
                add_or_set_detail_attr(target_node, stripped_id, parm.eval())

        asset_name = 'undefined'
        asset_name_from_node = generator_node.evalParm(PI_ASSET_ID)

        if (generator_node.evalParm(PI_ASSET_DEFS_ENABLED) and asset_name_from_node):
            asset_name = asset_name_from_node
        add_or_set_detail_attr(target_node, JK_ASSET_NAME, asset_name)

def generate_work_items(node, item_holder, json_file_path):
    json_data = load_json_data(node, json_file_path)

    if (JK_ALL_DEFS not in json_data):
        log(node, 'error: expected json to have key: ' + JK_ALL_DEFS)
        return
    
    for index, asset_def in enumerate(json_data[JK_ALL_DEFS]):
        work_item = item_holder.addWorkItem()

        if (JK_ASSET_NAME in asset_def):
            work_item.setStringAttrib(WIA_ASSET_NAME, asset_def[JK_ASSET_NAME])
        else:
            work_item.setStringAttrib(WIA_ASSET_NAME, 'unknown_' + str(index))

        # It's probably fine to just use @index, but this is a little safer
        # since even if the work items get shuffled up, this index will still be
        # valid.
        work_item.setIntAttrib(WIA_ASSET_INDEX, index)