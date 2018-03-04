import torch
import torch.nn as nn
import torch.autograd as autograd
import torch.optim

from utils.utils import padded_sequence_to_batch
from utils.utils import batch_to_padded_sequence
from utils.utils import Parameter


class Encoder(nn.Module):

    def __init__(self, *args, **kwargs):
        super().__init__()

    def forward(self, *args, **kwargs):
        return NotImplementedError

    @classmethod
    def abstract(cls):
        return True

    @classmethod
    def descriptor(cls, **kwargs):
        return NotImplementedError

    @property
    def interface(self):
        return [parameter for parameter in self.__dict__.keys()
                if isinstance(self.__dict__[parameter], Parameter)]


class RNNEncoder(Encoder):
    """
    Recurrent encoder module of the sequence to sequence model.
    """

    _param_dict = {
        'hidden_size': Parameter(name='_hidden_size',        doc='int, size of recurrent layer of the LSTM/GRU.'),
        'embedding_size': Parameter(name='_embedding_size',  doc='int, dimension of the word embeddings.'),
        'recurrent_type':  Parameter(name='_recurrent_type', doc='str, name of the recurrent layer (GRU, LSTM).'),
        'num_layers': Parameter(name='_num_layers',          doc='int, number of stacked RNN layers.'),
        'learning_rate': Parameter(name='_learning_rate',    doc='float, learning rate.'),
        'use_cuda':  Parameter(name='_use_cuda',             doc='bool, True if the device has cuda support.')
    }

    def __init__(self, parameter_setter):
        """
        A recurrent encoder module for the sequence to sequence model.
        :param parameter_setter: required parameters for the setter object.
            :parameter hidden_size: int, size of recurrent layer of the LSTM/GRU.
            :parameter recurrent_layer: str, name of the recurrent layer ('GRU', 'LSTM').
            :parameter embedding_size: int, dimension of the word embeddings.
            :parameter learning_rate: float, learning rate.
            :parameter use_cuda: bool, True if the device has cuda support.
        """
        super().__init__()
        self._parameter_setter = parameter_setter

        self._embedding = None
        self._optimizer = None

        self._recurrent_layer = None

    def init_parameters(self):
        """
        Calls the parameter setter, which initializes the Parameter type attributes.
        After initialization, the main components of the encoder, which require the previously
        initialized parameter values, are created as well.
        """
        for parameter in self._param_dict:
            self.__dict__[self._param_dict[parameter].name] = self._param_dict[parameter]

        self._parameter_setter(self.__dict__)

        if self._recurrent_type.value == 'LSTM':
            unit_type = torch.nn.LSTM
        else:
            unit_type = torch.nn.GRU

        self._recurrent_layer = unit_type(input_size=self._embedding_size.value,
                                          hidden_size=self._hidden_size.value,
                                          num_layers=self._num_layers.value,
                                          bidirectional=False,
                                          batch_first=True)

        if self._use_cuda.value:
            self._recurrent_layer = self._recurrent_layer.cuda()

        return self

    def init_optimizer(self):
        """
        Initializes the optimizer for the encoder.
        """
        self._optimizer = torch.optim.Adam(self.parameters(), lr=self._learning_rate.value)

        return self

    def forward(self,
                inputs,
                lengths):
        """
        A forward step of the encoder. The batch of sequences with word ids are
        packed into padded_sequence object, which are processed by the recurrent layer.
        :param inputs: Variable, (batch_size, sequence_length) containing the ids of the words.
        :param lengths: Ndarray, containing the real lengths of the sequences in the batch (prior to padding).
        :return outputs: Variable, (batch_size, sequence_length, vocab_size) the output at each time
                         step of the encoder.
        :return hidden_state: Variable, (num_layers * directions, batch_size, hidden_size) the final hidden state.
        """
        initial_state = self._init_hidden(inputs.size(0))

        embedded_inputs = self._embedding(inputs)
        padded_sequence = batch_to_padded_sequence(embedded_inputs, lengths)

        self._recurrent_layer.flatten_parameters()

        outputs, final_hidden_state = self._recurrent_layer(padded_sequence, initial_state)
        outputs, _ = padded_sequence_to_batch(outputs)

        return outputs, final_hidden_state

    def _init_hidden(self, batch_size):
        """
        Initializes the hidden state of the encoder module.
        :return: Variable, (num_layers*directions, batch_size, hidden_dim) with zeros as initial values.
        """
        result = autograd.Variable(torch.zeros(self._num_layers.value, batch_size, self._hidden_size.value))

        if self._use_cuda.value:
            result = result.cuda()

        if isinstance(self._recurrent_layer, torch.nn.LSTM):
            return result, result
        else:
            return result

    @classmethod
    def abstract(cls):
        return False

    @classmethod
    def descriptor(cls, **kwargs):
        return

    @property
    def optimizer(self):
        """
        Property for the optimizer of the encoder.
        :return self.__optimizer: Optimizer, the currently used optimizer of the encoder.
        """
        return self._optimizer

    @optimizer.setter
    def optimizer(self, optimizer):
        """
        Setter for the optimizer of the encoder.
        :param optimizer: Optimizer, instance to be set as the new optimizer for the encoder.
        """
        self._optimizer = optimizer

    @property
    def embedding(self):
        """
        Property for the encoder's embedding layer.
        :return: The currently used embeddings of the encoder.
        """
        return self._embedding

    @embedding.setter
    def embedding(self, embedding):
        """
        Setter for the encoder's embedding layer.
        :param embedding: Embedding, to be set as the embedding layer of the encoder.
        """
        self._embedding = nn.Embedding(embedding.size(0), embedding.size(1))
        self._embedding.weight = nn.Parameter(embedding)
        self._embedding.weight.requires_grad = False

    @property
    def hidden_size(self):
        """
        Property for the hidden size of the recurrent layer.
        :return: int, size of the hidden layer.
        """
        return self._hidden_size.value


class CNNEncoder(Encoder):  # TODO
    """
    Convolutional encoder module of the sequence to sequence model.
    """

    def __init__(self, ):
        super(CNNEncoder, self).__init__()

        self._embedding = None
        self._optimizer = None

    def forward(self,
                inputs,
                lengths,
                hidden):
        """
        :param inputs:
        :param lengths:
        :param hidden:
        :return:
        """
        return NotImplementedError

    @classmethod
    def abstract(cls):
        return False

    @property
    def optimizer(self):
        """

        :return:
        """
        return self._optimizer

    @optimizer.setter
    def optimizer(self, optimizer):
        """

        :param optimizer:
        :return:
        """
        self._optimizer = optimizer

    @property
    def embedding(self):
        """

        :return:
        """
        return self._embedding

    @embedding.setter
    def embedding(self, embedding):
        """

        :param embedding:
        :return:
        """
        self._embedding = nn.Embedding(embedding.size(0), embedding.size(1))
        self._embedding.weight = nn.Parameter(embedding)
        self._embedding.weight.requires_grad = False

    @property
    def hidden_size(self):
        """
        Property for the hidden size of the recurrent layer.
        :return: int, size of the hidden layer.
        """
        return self._hidden_dim
