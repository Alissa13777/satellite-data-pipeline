import numpy as np
import keras

class DataGenerator(keras.utils.Sequence):
    'Generates data for Keras'
    def __init__(self, list_IDs, batch_size, dims_input, dims_output, n_channels=1,
                 n_classes=10, shuffle=True):
        'Initialization'
        self.dims_input = dims_input
        self.dims_output = dims_output
        self.batch_size = batch_size
        self.list_IDs = list_IDs
        self.n_channels = n_channels
        self.n_classes = n_classes
        self.shuffle = shuffle
        self.on_epoch_end()

    def __len__(self):
        'Denotes the number of batches per epoch'
        return int(np.floor(len(self.list_IDs) / self.batch_size))

    def __getitem__(self, index):
        'Generate one batch of data'
        # Generate indexes of the batch
        indexes = self.indexes[index*self.batch_size:(index+1)*self.batch_size]

        # Find list of IDs
        list_IDs_temp = [self.list_IDs[k] for k in indexes]

        # Generate data
        X, y = self.__data_generation(list_IDs_temp)

        return X, y

    def on_epoch_end(self):
        'Updates indexes after each epoch'
        self.indexes = np.arange(len(self.list_IDs))
        if self.shuffle == True:
            np.random.shuffle(self.indexes)

    def __data_generation(self, list_IDs_temp):
        'Generates data containing batch_size samples' # X : (n_samples, *dim)
        # Initialization
        X = np.empty((self.batch_size, *self.dims_input))
        y = np.empty((self.batch_size, *self.dims_output))

        # Generate data
        for i, ID in enumerate(list_IDs_temp):

            X[i,:,:,0] = np.load('/workspaces/ASID-v2-builder/output/' + ID ).get('nersc_sar_primary')
            y[i,:,:,0] = np.load('/workspaces/ASID-v2-builder/output/' + ID ).get('CT')
        return X, y
