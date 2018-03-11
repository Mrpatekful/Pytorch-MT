from torch.nn import Module

from modules.rnn import encoders
from modules.rnn import decoders
from utils.utils import Component

from collections import OrderedDict


class Model(Module, Component):
    """
    Abstract base class for the models of the application.
    """

    def __init__(self, *args, **kwargs):
        super().__init__()

    def forward(self, *args, **kwargs):
        return NotImplementedError

    def step(self):
        return NotImplementedError

    def zero_grad(self):
        return NotImplementedError


class SeqToSeq(Model):
    """
    Sequence to sequence model according to the one described in:

        https://arxiv.org/abs/1409.3215

    The model has two main components, an encoder and a decoder, which may be
    implemented as recurrent or convolutional units. The main principle of this technique
    is to map a sequence - in case of translation - a sentence to another sentence,
    by encoding it to a fixed size representation, and then decoding this latent meaning
    vector to the desired sequence.
    """

    def __init__(self, encoder, decoder):
        """
        An instance of ta sequence to sequence model.
        :param encoder: Encoder, an encoder instance.
        :param decoder: Decoder, a decoder instance.
        """
        super().__init__()

        self._encoder = encoder.init_parameters().init_optimizer()
        self._decoder = decoder.init_parameters().init_optimizer()

    def forward(self,
                inputs,
                targets,
                max_length,
                lengths):
        """
        Forward step of the sequence to sequence model.
        :param inputs: Variable, containing the ids of the tokens for the input sequence.
        :param targets: Variable, containing the ids of the tokens for the target sequence.
        :param max_length: int, the maximum length of the decoded sequence.
        :param lengths: Ndarray, containing the lengths of the original sequences.
        :return decoder_outputs: dict, containing the concatenated outputs of the encoder and decoder.
        """
        encoder_outputs = self._encoder.forward(inputs=inputs, lengths=lengths)
        decoder_outputs = self._decoder.forward(targets=targets, max_length=max_length, **encoder_outputs)

        return {**decoder_outputs, **encoder_outputs}

    def step(self):
        """
        Updates the parameters of the encoder and decoder modules.
        """
        self._encoder.optimizer.step()
        self._decoder.optimizer.step()

    def zero_grad(self):
        """
        Refreshes the gradients of the optimizer.
        """
        self._encoder.optimizer.zero_grad()
        self._decoder.optimizer.zero_grad()

    @classmethod
    def abstract(cls):
        return False

    @classmethod
    def interface(cls):
        return OrderedDict(
            encoder=encoders.Encoder,
            decoder=decoders.Decoder
        )

    @property
    def decoder_tokens(self):
        """
        Tokens used by the decoder, for special outputs.
        """
        return self._decoder.tokens

    @decoder_tokens.setter
    def decoder_tokens(self, tokens):
        """
        Setter for the tokens, that will be used by the decoder.
        :param tokens: dict, tokens from the lut of decoding target.
        """
        self._decoder.tokens = tokens

    @property
    def decoder_embedding(self):
        """
        Property for the embedding of the decoder.
        :return embedding: Embedding, the currently used embedding of the decoder.
        """
        return self._decoder.embedding

    @decoder_embedding.setter
    def decoder_embedding(self, embedding):
        """
        Setter for the embedding of the decoder.
        """
        self._decoder.embedding = embedding

    @property
    def encoder_embedding(self):
        """
        Property for the embedding of the decoder.
        :return embedding: Embedding, the currently used embedding of the encoder.
        """
        return self._encoder.embedding

    @encoder_embedding.setter
    def encoder_embedding(self, embedding):
        """
        Setter for the embedding of the encoder.
        """
        self._encoder.embedding = embedding
