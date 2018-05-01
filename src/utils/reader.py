"""

"""

import copy
import os
import sys

from collections import OrderedDict

import numpy
import sklearn.utils
import torch
import torch.nn

import logging

from src.components.utils.utils import Embedding

from src.utils.utils import Component
from src.utils.utils import ParameterSetter
from src.utils.utils import ids_from_sentence
from src.utils.utils import sentence_from_ids
from src.utils.utils import subclasses
from src.utils.utils import subtract_dict


class Vocabulary(Component):
    """
    Wrapper class for the lookup tables of the languages.
    """
    abstract = False

    interface = OrderedDict(**{
        'vocab_path':            None,
        'provided_embeddings':   None,
        'fixed_embeddings':      None,
        'cuda':                 'Experiment:Policy:cuda',
        'language_identifiers': 'Experiment:language_identifiers'
    })

    def __init__(self,
                 vocab_path:            str,
                 language_identifiers:  list,
                 provided_embeddings:   bool,
                 fixed_embeddings:      bool,
                 cuda:                  bool):
        """

        Args:

        """
        self._word_to_id = {}
        self._id_to_word = {}
        self._word_to_count = {}

        self._language_identifiers = language_identifiers
        self._cuda = cuda
        self._provided = provided_embeddings

        self.requires_grad = not fixed_embeddings

        self._vocab_size = None
        self._embedding_size = None
        self._embedding_weights = None

        self._load_data(path=vocab_path)

        # noinspection PyTypeChecker
        self._embedding = Embedding(embedding_size=self._embedding_size,
                                    vocab_size=self._vocab_size,
                                    cuda=self._cuda,
                                    weights=self._embedding_weights,
                                    requires_grad=self.requires_grad)

    def _load_data(self, path: str):
        """
        Loads the vocabulary from a file. Path is assumed to be a text file, where each line contains
        a word and its corresponding embedding weights, separated by spaces.
        :param path: string, the absolute path of the vocab.
        """
        with open(path, 'r') as file:
            first_line = file.readline().split(' ')
            self._vocab_size = int(first_line[0]) + 4 + len(self._language_identifiers)
            self._embedding_size = int(first_line[1])

            if self._provided:
                self._embedding_weights = numpy.empty((self._vocab_size, self._embedding_size), dtype=float)

            for index, line in enumerate(file):
                line_as_list = list(line.split(' '))
                self._word_to_id[line_as_list[0]] = index
                if self._provided:
                    self._embedding_weights[index, :] = numpy.array([float(element) for element
                                                                    in line_as_list[1:]], dtype=float)

            for token in self._language_identifiers:
                self._word_to_id[token] = len(self._word_to_id)

            self._word_to_id['<SOS>'] = len(self._word_to_id)
            self._word_to_id['<EOS>'] = len(self._word_to_id)
            self._word_to_id['<UNK>'] = len(self._word_to_id)
            self._word_to_id['<PAD>'] = len(self._word_to_id)

            self._id_to_word = dict(zip(self._word_to_id.values(), self._word_to_id.keys()))

            if self._provided:
                self._embedding_weights[-1, :] = numpy.zeros(self._embedding_size)
                self._embedding_weights[-2, :] = numpy.zeros(self._embedding_size)
                self._embedding_weights[-3, :] = numpy.zeros(self._embedding_size)
                self._embedding_weights[-4, :] = numpy.zeros(self._embedding_size)

                for index in range(-5, -5-len(self._language_identifiers), -1):
                    self._embedding_weights[index, :] = numpy.random.rand(self._embedding_size)

                self._embedding_weights = torch.from_numpy(self._embedding_weights).float()

                if self._cuda:
                    self._embedding_weights = self._embedding_weights.cuda()

    def __call__(self, expression):
        """
        Translates the given expression to it's corresponding word or id.
        :param expression: str or int, if str (word) is provided, then the id will be returned, and
                           the behaviour is the same for the other case.
        :return: int or str, (id or word) of the provided expression.
        """
        _accepted_id_types = (int, numpy.int32, numpy.int64)

        if isinstance(expression, str):
            return self._word_to_id[expression]

        elif type(expression) in _accepted_id_types:
            return self._id_to_word[expression]

        else:
            raise ValueError(f'Expression must either be a string or an int, got {type(expression)}')

    @property
    def tokens(self):
        """
        Property for the tokens of the language.
        :return: dict, <UNK>, <EOS>, <PAD> and <SOS> tokens with their ids.
        """
        return {
            '<SOS>': self._word_to_id['<SOS>'],
            '<EOS>': self._word_to_id['<EOS>'],
            '<UNK>': self._word_to_id['<UNK>'],
            '<PAD>': self._word_to_id['<PAD>']
        }

    @property
    def embedding(self):
        """
        Property for the embedding layer.
        """
        if self._embedding is None:
            raise ValueError('The vocabulary has not been initialized for the language.')
        return self._embedding

    @property
    def embedding_size(self):
        """
        Property for the dimension of the embeddings.
        """
        if self._embedding is None:
            raise ValueError('The vocabulary has not been initialized for the language.')
        return self._embedding_size

    @property
    def vocab_size(self):
        """
        Property for the dimension of the embeddings.
        """
        return self._vocab_size - 1


class Corpora(Component):
    """
    Wrapper class for the corpus of the task. Stores information about the corpus, and
    stores the location of the train, development and test data.
    """

    interface = OrderedDict(**{
        'data_path':      None,
        'vocabulary':    ':Vocabulary$',
        'cuda':          'Experiment:Policy:cuda$'
    })

    abstract = True

    def __init__(self,
                 data_path:  str,
                 vocabulary: Vocabulary,
                 cuda:       bool):
        """


        Args:

        """
        assert os.path.isfile(data_path), f'{data_path} is not a file'

        self._vocabulary = vocabulary
        self._data_path = data_path
        self._cuda = cuda

        self._data = None

    def initialize_corpus(self):
        raise NotImplementedError

    def _load_data(self, data_path):
        raise NotImplementedError

    # The following 'size' properties are required for the parameter value resolver mechanism.

    @property
    def data_path(self) -> str:
        """

        """
        return self._data_path

    @property
    def data(self) -> list:
        """

        """
        return self._data

    @property
    def embedding_size(self) -> int:
        """
        Property for the embedding size of the source language.
        """
        return self._vocabulary.embedding_size

    @property
    def vocabulary(self) -> Vocabulary:
        """
        Property for the vocabularies of the corpora.
        """
        return self._vocabulary

    @vocabulary.setter
    def vocabulary(self, value: Vocabulary):
        """
        Property for the vocabularies of the corpora.
        """
        self._vocabulary = value

    @property
    def vocab_size(self) -> int:
        """
        Property for the vocab size of the language.
        """
        return self._vocabulary.vocab_size


class Monolingual(Corpora):
    """
    Special case of Corpora class, where the data read from the files only have a single language.
    """

    interface = Corpora.interface

    abstract = False

    def __init__(self,
                 data_path:  str,
                 vocabulary: Vocabulary,
                 cuda:       bool):
        """


        Args:

        """
        super().__init__(data_path=data_path, cuda=cuda, vocabulary=vocabulary)

    def initialize_corpus(self):
        """

        """
        self._data = self._load_data(self._data_path)

    def _load_data(self, data_path: str) -> list:
        """
        Loader function for the monolingual corpora, where there is only a single language.
        :return: list, the data stored as a list of strings.
        """
        data = []
        with open(data_path, 'r') as file:
            for line in file:
                data.append(line)
        if len(data) == 0:
            raise ValueError('The given file is empty.')
        return data


class Parallel(Corpora):  # TODO vocabulary parameter extraction
    """
    Wrapper class for the corpora, that yields two languages. The languages are paired, and
    are separated by a special separator token.
    """

    interface = OrderedDict(**{
        'data_path':          None,
        'separator':          None,
        'vocabulary':        'Vocabulary$',
        'second_vocabulary': 'Vocabulary$',
        'cuda':              'Experiment:Policy:cuda$'
    })

    abstract = False

    def __init__(self,
                 data_path:  str,
                 separator:  str,
                 vocabulary: Vocabulary,

                 cuda:       bool):
        """

        Args:

        """
        super().__init__(data_path=data_path, cuda=cuda, vocabulary=vocabulary)


    def _load_data(self, data_path):
        """
        Loader function for parallel data. Data is read from the provided path, and separated
        by the separator token.
        :return: list, the data stored as a list of strings.
        """
        data = []
        with open(data_path, 'r') as file:
            for line in file:
                data.append(line[:-1].split(self._separator_token))
        if len(data) == 0:
            raise ValueError('The given file is empty.')
        return data

    def initialize_corpus(self):
        """

        """
        self._data = self._load_data(self._data_path)

    @property
    def source_vocabulary(self):
        """
        Property for the source language of the text corpora.
        :return: Language, instance of the wrapper class for the source language.
        """
        if self._vocabulary is None:
            raise ValueError('Source vocabulary has not been set.')
        return self._vocabulary[0]

    @property
    def target_vocabulary(self):
        """
        Property for the target language of the text corpora.
        :return: Language, instance of the wrapper class for the target language.
        """
        if self._vocabulary is None:
            raise ValueError('Target vocabulary has not been set.')
        return self._vocabulary[-1]

    @property
    def source_vocab_size(self):
        """
        Property for the vocab size of the source language.
        :return: int, number of words in the source language.
        """
        if self._vocabulary is None:
            raise ValueError('Source vocabulary has not been set.')
        return self._vocabulary[0].vocab_size

    @property
    def target_vocab_size(self):
        """
        Property for the vocab size of the target language.
        :return: int, number of words in the target language.
        """
        if self._vocabulary is None:
            raise ValueError('Target vocabulary has not been set.')
        return self._vocabulary[-1].vocab_size


class InputPipeline(Component):
    """
    Derived classes should implement the reading logic for the seq2seq model. Readers divide the
    data into segments. The purpose of this behaviour, is to keep the sentences with similar lengths
    in segments, so they can be freely shuffled without mixing them together with larger sentences.
    """

    def batch_generator(self):
        """
        The role of this function is to generate batches for the seq2seq model. The batch generation
        should include the logic of shuffling the samples. A full iteration should include
        all of the data samples.
        """
        raise NotImplementedError


class MemoryInput(InputPipeline):
    """
    A faster implementation of reader class than FileReader. The source data is fully loaded into
    the memory.
    """

    interface = OrderedDict(**{
        'max_segment_size':  None,
        'batch_size':        None,
        'padding_type':      None,
        'shuffle':           None,
        'cuda':             'Experiment:Policy:cuda$',
        'corpora':           Corpora
    })

    abstract = False

    def __init__(self,
                 max_segment_size:  int,
                 batch_size:        int,
                 shuffle:           bool,
                 cuda:              bool,
                 corpora:           Corpora,
                 padding_type:      str = 'PostPadding'):
        """
        An instance of a fast reader.
        :param batch_size: int, size of the input batches.
        :param cuda: bool, True if the device has cuda support.
        :param padding_type: str, type of padding that will be used during training. The sequences in
                             the mini-batches may vary in length, so padding must be applied to convert
                             them to equal lengths.
        :param max_segment_size: int, the size of each segment, that will contain the similar length data.
        """
        super().__init__()

        self._cuda = cuda
        self._shuffle = shuffle
        self._corpora = corpora
        self._batch_size = batch_size
        self._max_segment_size = max_segment_size

        padding_types = subclasses(Padding)

        self._padder = padding_types[padding_type](self._corpora.vocabulary, max_segment_size)

        self._corpora.initialize_corpus()

        self._data = self._padder(self._corpora.data)

    def batch_generator(self):
        """
        Generator for mini-batches. Data is read from memory. The _format_batch function comes from the
        definition of the task. It is a wrapper function that transform the generated batch of data into a form,
        that is convenient for the current task.
        :return: tuple, a PyTorch Variable of dimension (Batch_size, Sequence_length), containing
                 the ids of words, sorted by their length in descending order. Each sample is
                 padded to the length of the longest sequence in the batch/segment.
                 The latter behaviour may vary. Second element of the tuple is a numpy array
                 of the lengths of the original sequences (without padding).
        """
        for data_segment in self._segment_generator():
            if self._shuffle:
                shuffled_data_segment = sklearn.utils.shuffle(data_segment)
            else:
                shuffled_data_segment = data_segment
            for index in range(0, len(shuffled_data_segment)-self._batch_size+1, self._batch_size):
                batch = self._padder.create_batch(
                    shuffled_data_segment[index:index + self._batch_size]
                )
                yield batch

    def print_validation_format(self, dictionary):
        """
        Convenience function for printing the parameters of the function, to the standard output.
        The parameters must be provided as keyword arguments. Each argument must contain a 2D
        array containing word ids, which will be converted to the represented words from the
        dictionary of the language, used by the reader instance.
        """
        id_batches = numpy.array(list(dictionary.values()))
        expression = ''
        for index, ids in enumerate(zip(*id_batches)):
            expression += '{%d}:\n' % index
            for param in zip(dictionary, ids):
                expression += ('> [%s]:\t%s\n' % (param[0], '\t'.join(sentence_from_ids(self._corpora.vocabulary,
                                                                                        param[1]))))
            expression += '\n'
        print(expression)

    def _segment_generator(self):
        """
        Divides the data to segments of size MAX_SEGMENT_SIZE.
        """
        for index in range(0, len(self._data), self._max_segment_size):
            yield copy.deepcopy(self._data[index:index + self._max_segment_size])

    @property
    def corpora(self):
        """
        Property for the corpora of the reader.
        """
        return self._corpora

    @property
    def vocabulary(self):
        """
        Property for the reader object's vocabulary.
        :return: Language object, the source vocabulary.
        """
        return self._corpora.vocabulary


class FileInput(InputPipeline):
    """
    An implementation of the reader class. Batches are read from the source in file real-time.
    This version of the reader should only be used if the source file is too large to be stored
    in memory.
    """

    interface = OrderedDict(**{
        'max_segment_size':     None,
        'batch_size':           None,
        'padding_type':         None,
        'shuffle':              None,
        'cuda':                'Experiment:Policy:cuda$',
        'corpora':              Corpora
    })

    abstract = False

    def __init__(self,
                 max_segment_size:  int,
                 batch_size:        int,
                 cuda:              bool,
                 shuffle:           bool,
                 corpora:           Corpora,
                 padding_type:      str = 'PostPadding'):
        """


        Args:
.
        """
        super().__init__()

        self._cuda = cuda
        self._corpora = corpora
        self._batch_size = batch_size
        self._shuffle = shuffle
        self._max_segment_size = max_segment_size

        self._data_reader = DataQueue(corpora=self._corpora)

        padding_types = subclasses(Padding)

        self._padder = padding_types[padding_type](self._corpora.vocabulary, max_segment_size)

    def batch_generator(self):
        """
        Generator for mini-batches. Data is read from memory. The _format_batch function comes from the
        definition of the task. It is a wrapper function that transform the generated batch of data into a form,
        that is convenient for the current task.
        :return: tuple, a PyTorch Variable of dimension (Batch_size, Sequence_length), containing
                 the ids of words, sorted by their length in descending order. Each sample is
                 padded to the length of the longest sequence in the batch/segment.
                 The latter behaviour may vary. Second element of the tuple is a numpy array
                 of the lengths of the original sequences (without padding).
        """
        for data_segment in self._segment_generator():
            if self._shuffle:
                shuffled_data_segment = sklearn.utils.shuffle(data_segment)
            else:
                shuffled_data_segment = data_segment
            for index in range(0, len(shuffled_data_segment)-self._batch_size+1, self._batch_size):
                batch = self._padder.create_batch(
                    shuffled_data_segment[index:index + self._batch_size]
                )
                yield batch

    # noinspection PyTypeChecker
    def _segment_generator(self):
        """
        Divides the data to segments of size MAX_SEGMENT_SIZE.
        """
        for file_data_segment in self._data_reader.generator():
            for index in range(0, len(file_data_segment), self._max_segment_size):
                yield copy.deepcopy(file_data_segment[index:index + self._max_segment_size])

    @property
    def corpora(self):
        """
        Property for the corpora of the reader.
        """
        return self._corpora

    @property
    def vocabulary(self):
        """
        Property for the reader object's vocabulary.
        :return: Language object, the source vocabulary.
        """
        return self._corpora.vocabulary


class DataQueue:
    """
    A queue object for the data feed. This can be later configured to load the data to
    memory asynchronously.
    """
    MAX_SEGMENT = 50000

    @staticmethod
    def _location_scheme(path):
        file_name = os.path.splitext(os.path.basename(path))
        return os.path.join(os.path.dirname(os.path.realpath(path)),
                            '%s_id%s' % (file_name[0], ''.join(file_name[1:])))

    def __init__(self,
                 corpora:           Corpora,
                 max_segment_size:  int = MAX_SEGMENT):
        """

        """
        self._data_path = corpora.data_path
        self._id_data_path = self._location_scheme(corpora.data_path)

        self._corpora = corpora
        self._max_segment_size = max_segment_size
        self._data_segment_queue = []

        if os.path.isfile(self._id_data_path):
            logging.info(f'Using {self._id_data_path} as data source')
        else:
            logging.info(f'Creating {self._id_data_path} as data source')
            self._generate_id_file()

    def _generate_id_file(self):
        """

        """
        with open(self._data_path, 'r') as text_file:
            with open(self._id_data_path, 'w') as id_file:
                for line in text_file:
                    ids = ids_from_sentence(self._corpora.vocabulary, line)
                    id_file.write('%s %d\n' % (' '.join(list(map(str, ids))), len(ids)))

    def generator(self):
        """
        Data is retrieved directly from a file, and loaded into data chunks of size MAX_CHUNK_SIZE.
        """
        with open(self._id_data_path, 'r') as file:
            data_segment = []
            for line in file:
                if len(data_segment) < self._max_segment_size:
                    data_segment.append(list(map(int, line.strip().split())))
                else:
                    temp_data_segment = copy.deepcopy(data_segment)
                    del data_segment[:]
                    yield temp_data_segment
            yield data_segment


class ParallelDataQueue:
    """
    A queue object for the data feed. This can be later configured to load the data to
    memory asynchronously.
    """
    MAX_SEGMENT = 50000

    @staticmethod
    def _location_scheme(path):
        file_name = os.path.splitext(os.path.basename(path))
        return os.path.join(os.path.dirname(os.path.realpath(path)),
                            '%s_id%s' % (file_name[0], ''.join(file_name[1:])))

    def __init__(self,
                 corpora:           Corpora,
                 max_segment_size:  int = MAX_SEGMENT):
        """

        """
        self._data_path = corpora.data_path
        self._id_data_path = self._location_scheme(corpora.data_path)

        self._corpora = corpora
        self._max_segment_size = max_segment_size
        self._data_segment_queue = []

        if os.path.isfile(self._id_data_path):
            logging.info(f'Using {self._id_data_path} as data source')
        else:
            logging.info(f'Creating {self._id_data_path} as data source')
            self._generate_id_file()

    def _generate_id_file(self):
        """

        """
        with open(self._data_path, 'r') as text_file:
            with open(self._id_data_path, 'w') as id_file:
                for line in text_file:
                    ids = ids_from_sentence(self._corpora.vocabulary, line)
                    id_file.write('%s %d\n' % (' '.join(list(map(str, ids))), len(ids)))

    def generator(self):
        """
        Data is retrieved directly from a file, and loaded into data chunks of size MAX_CHUNK_SIZE.
        """
        with open(self._id_data_path, 'r') as file:
            data_segment = []
            for line in file:
                if len(data_segment) < self._max_segment_size:
                    data_segment.append(list(map(int, line.strip().split())))
                else:
                    temp_data_segment = copy.deepcopy(data_segment)
                    del data_segment[:]
                    yield temp_data_segment
            yield data_segment


class Padding:
    """
    Base class for the padding types.
    """

    abstract = True

    def __init__(self,
                 vocabulary,
                 max_segment_size):
        """


        Args:
            vocabulary:

            max_segment_size:

        """
        self._vocabulary = vocabulary
        self._max_segment_size = max_segment_size

    def create_batch(self, data):
        raise NotImplementedError


class PostPadding(Padding):
    """
    Data is padded during the training iterations. Padding is determined by the longest
    sequence in the batch.
    """

    abstract = False

    def create_batch(self, data):
        """
        Creates a sorted batch from the data. Each line of the data is padded to the
        length of the longest sequence in the batch.
        :param data:
        :return:
        """
        sorted_data = sorted(data, key=lambda x: x[-1], reverse=True)
        batch_length = sorted_data[0][-1]
        for index in range(len(sorted_data)):
            while len(sorted_data[index]) - 1 < batch_length:
                sorted_data[index].insert(-1, self._vocabulary.tokens['<PAD>'])

        return numpy.array(sorted_data, dtype='int')

    def __init__(self, vocabulary, max_segment_size):
        """
        An instance of a post-padder object.
        :param vocabulary: Vocabulary, instance of the used language object.
        """
        super().__init__(vocabulary, max_segment_size)

    def __call__(self, data):
        """
        Converts the data of (string) sentences to ids of the words.
        :param data: list, strings of the sentences.
        :return: list, list of (int) ids of the words in the sentences.
        """
        data_to_ids = []
        for index in range(0, len(data), self._max_segment_size):
            for line in data[index:index + self._max_segment_size]:
                ids = ids_from_sentence(self._vocabulary, line)
                ids.append(len(ids))
                data_to_ids.append(ids)
        return data_to_ids


class PrePadding(Padding):
    """
    Data is padded previously to the training iterations. The padding is determined
    by the longest sequence in the data segment.
    """

    abstract = False

    def create_batch(self, data):
        """
        Creates the batch, by sorting the elements in descending order with respect to the
        lengths of the sequences.
        :param data: list, containing lists of the ids.
        :return: Numpy Array, sorted batch.
        """
        return numpy.array(sorted(data, key=lambda x: x[-1], reverse=True))

    def __init__(self, vocabulary, max_segment_size):
        """
        An instance of a pre-padder object.
        :param vocabulary: Vocabulary, instance of the used language object.
        """
        super().__init__(vocabulary, max_segment_size)

    def __call__(self, data):
        """
        Converts the data of (string) sentences to ids of the words.
        Sentences are padded to the length of the longest sentence in the data segment.
        Length of a segment is determined by MAX_SEGMENT_SIZE.
        :param data: list, strings of the sentences.
        :return: list, list of (int) ids of the words in the sentences.
        """
        data_to_ids = []
        for index in range(0, len(data), self._max_segment_size):
            segment_length = len(ids_from_sentence(self._vocabulary, data[index:index + self._max_segment_size][0]))
            for line in data[index:index + self._max_segment_size]:
                ids = ids_from_sentence(self._vocabulary, line)
                ids_len = len(ids)
                while len(ids) < segment_length:
                    ids.append(self._vocabulary.tokens['<PAD>'])
                data_line = numpy.zeros((segment_length + 1), dtype='int')
                data_line[:-1] = ids
                data_line[-1] = ids_len
                data_to_ids.append(data_line)

        return data_to_ids


class Language(Component):
    """

    """

    abstract = False

    interface = OrderedDict(**{
        'identifier':           None,
        'vocabulary':           Vocabulary,
        'input_pipelines':      InputPipeline,
    })

    def __init__(self,
                 identifier:        str,
                 input_pipelines:   dict,
                 vocabulary:        Vocabulary):
        """


        Args:
            identifier:

            input_pipelines:

            vocabulary:
        """

        self._identifier = identifier

        try:
            assert isinstance(input_pipelines, dict), 'train, dev, test'

            assert 'train' in input_pipelines, 'train'
            assert 'dev' in input_pipelines, 'dev'
            assert 'test' in input_pipelines, 'test'

        except AssertionError as error:
            logging.error(f'Language configuration file must contain {error} key(s) in the input pipeline dictionary')
            sys.exit()

        logging.debug('Language object initialized with %d input pipelines (%s)' %
                      (len(input_pipelines), ', '.join(list(input_pipelines.keys()))))

        self._input_pipelines = input_pipelines

        self._vocabulary = vocabulary

    @property
    def identifier(self):
        return self._identifier

    @property
    def input_pipelines(self):
        return self._input_pipelines

    @property
    def vocabulary(self):
        return self._vocabulary