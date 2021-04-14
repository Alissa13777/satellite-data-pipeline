import os
import sys
import numpy as np
import netCDF4 as nc
from skimage.util.shape import view_as_windows
from json import dump, load
from calculate_mask import calculate_mask



def create_sar_variables_for_ML_training(
    sar_names, fil, window_size, stride_sar_size, mask_batches,
    pad_hight_up, pad_hight_down, pad_width_west, pad_width_east):
    """
    This function calculates the sar data and store them in a global variable with the same name
    """
    for sar_name in sar_names:
        values_array = np.ma.getdata(fil[sar_name])
        values_array = np.pad(
            values_array, ((pad_hight_up, pad_hight_down),(pad_width_west, pad_width_east)),
            'constant', constant_values=(None, None))
        batches = view_as_windows(values_array, window_size, stride_sar_size)
        # initiation of the array with one single layer of empty data (meaningless values)
        template_sar_float32 = np.empty(window_size).astype(np.float32)
        for ix, iy in np.ndindex(batches.shape[:2]):
            if (~mask_batches[ix, iy]).all():
                # stack data in 3rd dimension
                template_sar_float32 = np.dstack((template_sar_float32, batches[ix, iy]))
        globals()[sar_name] = template_sar_float32[:, :, 1:].astype(np.float32)#remove the first empty values
        del template_sar_float32
        del values_array
        del batches

def create_output_variables_for_ML_training(
        polygon_ids, mask_batches, window_size, map_id_to_variable_values, names_polygon_codes,
        stride_sar_size, pad_hight_up, pad_hight_down, pad_width_west, pad_width_east):
    """
    This function calculates the output data and store them in a global variable with the same name
    of them in the file for example 'CT' or 'CA' etc.
    """
    for index in range(10):  # iterating over variables that must be saved for example 'CT' or 'CA'
        values_array = polygon_ids
        values_array = np.pad(
            values_array, ((pad_hight_up, pad_hight_down),
                           (pad_width_west, pad_width_east)),
            'constant', constant_values=(0, 0)).astype(np.byte)
        batches = view_as_windows(values_array, window_size, stride_sar_size)
        # initiation of the array with one single layer of empty data (meaningless values)
        template_sar = np.empty(window_size).astype(np.byte)
        for ix, iy in np.ndindex(batches.shape[:2]):
            if (~mask_batches[ix, iy]).all():
                raw_id_values = batches[ix, iy]
                for id_value, variable_belong_to_id in map_id_to_variable_values.items():
                    # each loop changes all locations of raw_id_values (that have the very
                    # 'id_value') to its corresponding value inside 'variable_belong_to_id'
                    raw_id_values[raw_id_values == id_value] = np.byte(variable_belong_to_id[index])
                # stack to the data in 3rd dimension
                template_sar = np.dstack((template_sar, raw_id_values))

        globals()[names_polygon_codes[index+1]] = template_sar[:, :, 1:]
        del template_sar
        del batches
        del values_array


def create_amsr2_variables_for_ML_training(
    amsr_labels, fil, stride_ams2_size, final_mask_with_amsr2_size, window_size_amsr2):
    """
    This function calculates the amsr2 data and store them in a global variable with the same name
    """
    mask_batches_amsr2 = view_as_windows(
        final_mask_with_amsr2_size, window_size_amsr2, stride_ams2_size)
    for amsr_label in amsr_labels:
        values_array = np.ma.getdata(fil[amsr_label])
        batches = view_as_windows(values_array, window_size_amsr2, stride_ams2_size)
        # initiation of the array with one single layer of data
        template_amsr2 = np.empty(window_size_amsr2).astype(np.float32)
        for ix, iy in np.ndindex(batches.shape[:2]):
            if (~mask_batches_amsr2[ix, iy]).all():
                # stack the data in 3rd dimension
                template_amsr2 = np.dstack((template_amsr2, batches[ix, iy]))
        globals()[amsr_label.replace(".", "_")] = template_amsr2[:, :, 1:].astype(np.float32)
        del template_amsr2
        del batches
        del values_array
    del mask_batches_amsr2

def read_input_params():
    datapath = sys.argv[1]
    outpath = sys.argv[2]
    rm_swath = 0
    distance_threshold = 0
    amsr_labels = ['btemp_6.9h', 'btemp_6.9v', 'btemp_7.3h', 'btemp_7.3v',
                'btemp_10.7h', 'btemp_10.7v', 'btemp_18.7h', 'btemp_18.7v',
                'btemp_23.8h', 'btemp_23.8v', 'btemp_36.5h', 'btemp_36.5v',
                'btemp_89.0h', 'btemp_89.0v']
    window_size_amsr2 = (14, 14)
    window_size = (window_size_amsr2[0]*50, window_size_amsr2[1]*50)
    stride_ams2_size = 14
    stride_sar_size = stride_ams2_size*50

    nersc = 'nersc_'  # Leave as empty string '' for ESA noise corrections or as 'nersc_'
    # for the Nansen center noise correction.
    sar_names = [nersc+'sar_primary',nersc+'sar_secondary']
    if not os.path.exists(outpath):
        os.mkdir(outpath)
    return (sar_names, nersc, stride_sar_size,stride_ams2_size,window_size,window_size_amsr2,
        amsr_labels,distance_threshold,rm_swath,outpath, datapath)


def file_health_check(fil, rm_swath, outpath,amsr_labels,window_size,filename):
    if 'polygon_icechart' not in fil.variables:
        print(f"'polygon_icechart' should be in 'fil.variables'. for {fil}")
        return False
    lowerbound = max([rm_swath, fil.aoi_upperleft_sample])
    if amsr_labels and not (amsr_labels[0] in fil.variables):
        f = open(os.path.join(outpath,"/discarded_files.txt"), "a")
        f.write(filename+",missing AMSR file"+"\n")
        f.close()
        print("wrote "+filename+" to discarded_files.txt in "+outpath)
        return False
    elif ((fil.aoi_lowerright_sample-lowerbound) < window_size[0] or
        (fil.aoi_lowerright_line-fil.aoi_upperleft_line) < window_size[1]):
        f = open(os.path.join(outpath,"/discarded_files.txt"), "a")
        f.write(filename+",unmasked scene is too small"+"\n")
        f.close()
        print("wrote "+filename+" to discarded_files.txt in "+outpath)
        return False
    else:
        return True

def read_file_info(fil, filename):
    scene = filename.split('_')[0]
    #just from beginning up to variable 'FC' is considered, thus it is [:11] in line below
    names_polygon_codes = fil['polygon_codes'][0].split(";")[:11]
    map_id_to_variable_values = {}  # initialization
    # this dictionary has the ID as key and the corresponding values
    # as a list at the 'value postion' of that key in the dictionary.
    for id_and_corresponding_variable_values in fil['polygon_codes'][1:]:
        id_val_splitted = id_and_corresponding_variable_values.split(";")
        map_id_to_variable_values.update({int(id_val_splitted[0]): id_val_splitted[1:]})
    polygon_ids = np.ma.getdata(fil["polygon_icechart"])
    return (polygon_ids, map_id_to_variable_values, names_polygon_codes, scene)


def get_unprocessed_files(outpath, datapath):
    try:
        with open(os.path.join(outpath,"processed_files.json")) as json_file:
            processed_files = load(json_file)
    except FileNotFoundError:
        print("all files are being processed!")
        processed_files = []
    files=[]
    for elem in os.listdir(datapath):
        if (elem.endswith(".nc") and elem not in processed_files):
            files.append(elem)
    return files, processed_files

def update_processed_files(processed_files, files, outpath):
    if processed_files == []:
        processed_files = files
    else:
        processed_files.append(*files) if (files and files not in processed_files) else None
    with open(os.path.join(outpath, "processed_files.json"), 'w') as outfile:
        dump(processed_files, outfile)

def main():

    (sar_names, nersc, stride_sar_size,stride_ams2_size,window_size,window_size_amsr2,
        amsr_labels,distance_threshold,rm_swath,outpath, datapath) = read_input_params()
    files, processed_files = get_unprocessed_files(outpath, datapath)
    for i, filename in enumerate(files):
        print("Starting %d out of %d files" % (i, len(files)))
        fil = nc.Dataset(os.path.join(datapath,filename))
        if file_health_check(fil, rm_swath, outpath,amsr_labels,window_size,filename):

            (polygon_ids, map_id_to_variable_values, names_polygon_codes, scene) = read_file_info(fil, filename)

            (final_ful_mask, final_mask_with_amsr2_size, pads) = calculate_mask(fil, amsr_labels,
                                                                    sar_names, distance_threshold)

            mask_batches = view_as_windows(final_ful_mask, window_size, stride_sar_size)

            create_sar_variables_for_ML_training(
                sar_names, fil, window_size, stride_sar_size, mask_batches, *pads
            )

            create_output_variables_for_ML_training(
                polygon_ids, mask_batches,
                window_size, map_id_to_variable_values, names_polygon_codes, stride_sar_size, *pads
            )
            del mask_batches
            create_amsr2_variables_for_ML_training(
                amsr_labels, fil, stride_ams2_size, final_mask_with_amsr2_size, window_size_amsr2
            )
            #saving section
            desired_variable_names = sar_names+amsr_labels+names_polygon_codes[1:]
            #removing dot from the name of variable
            desired_variable_names = [x.replace(".", "_") for x in desired_variable_names]
            #loop for saving each batch of separately in each file.
            # This way, it is compatible with the generator
            # code explained in link below
            # https://stanford.edu/~shervine/blog/keras-how-to-generate-data-on-the-fly
            for iiii in np.arange(np.shape(globals()[nersc+'sar_primary'])[2]):
            # third dim is equal for both sizes of input as well as the output data.Here sar_primary
            # variable is selected as one of them in the for loop.
                dict_for_saving = {}
                for name_without_dot in desired_variable_names:
                    dict_for_saving.update(
                        {name_without_dot: globals()[name_without_dot][:, :, iiii]})
                np.savez(f"{os.path.join(outpath,scene)}_{iiii:0>6}_{nersc}", **dict_for_saving)
            del fil, dict_for_saving, final_ful_mask, final_mask_with_amsr2_size
            for useless_variable_after_save in desired_variable_names:
                del globals()[useless_variable_after_save]

    update_processed_files(processed_files, files, outpath)

if __name__ == "__main__":
    main()
