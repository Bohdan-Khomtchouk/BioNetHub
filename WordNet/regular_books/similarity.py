# -*- coding: utf-8 -*-

# Copyright (C) 2015-2016 Bohdan Khomtchouk and Kasra A. Vand
# This file is part of PubData.

# -------------------------------------------------------------------------------------------

import numpy as np
from itertools import chain
from functools import wraps
from collections import Counter, defaultdict
from itertools import permutations
from os import path as ospath
from operator import itemgetter
import json
import glob


class Initializer:
    def __init__(self, *args, **kwargs):
        self.main_dict = {i: set(j) for i, j in kwargs["main_dict"].items() if j}
        self.all_words = self.create_words()
        self.all_sent = self.get_sentences()

    def create_words(self):
        all_words = np.unique(np.fromiter(chain.from_iterable(self.main_dict.values()),
                              dtype='U20'))
        return all_words

    def get_sentences(self):
        return np.array(list(self.main_dict))

    def create_SSM(self):
        """
        Initialize the sentence similarity matrix by creating a NxN zero filled
        matrix where N is the number of sentences.
        """
        size = self.all_sent.size
        dt = np.dtype({"names": self.all_sent,
                       "formats": [np.float16] * size})
        return np.zeros(size, dtype=dt)


class FindSimilarity(Initializer):
    def __new__(cls, *args, **kwargs):
        def cache_matrix(f):
            cache_WSM = {}
            cache_SSM = {}
            if f.__name__ == "WSM":
                cache = cache_WSM
            else:
                cache = cache_SSM

            @wraps(f)
            def wrapped(n):
                try:
                    result = cache[n]
                except KeyError:
                    result = cache[n] = f(n)
                return result
            return wrapped

        def cache_weight(f):
            cache = {}

            @wraps(f)
            def wrapped(**kwargs):
                key = tuple(kwargs.values())
                try:
                    result = cache[key]
                except KeyError:
                    result = cache[key] = f(**kwargs)
                return result
            return wrapped

        def cache_general(f):
            cache = {}

            @wraps(f)
            def wrapped(*args):
                try:
                    result = cache[args]
                except KeyError:
                    result = cache[args] = f(*args)
                return result
            return wrapped

        obj = object.__new__(cls)
        general_attrs = ("affinity_WS",
                         "affinity_SW",
                         "similarity_W",
                         "similarity_S",
                         "sentence_include_word")
        for name in general_attrs:
            setattr(obj, name, cache_general(getattr(obj, name)))
        for name in ("WSM", "SSM"):
            setattr(obj, name, cache_matrix(getattr(obj, name)))
        setattr(obj, "weight", cache_weight(getattr(obj, "weight")))
        cache_general.cache = {}
        cache_matrix.cache = {}
        cache_weight.cache = {}
        return obj

    def __init__(self, *args, **kwargs):
        super(FindSimilarity, self).__init__(*args, **kwargs)
        try:
            self.iteration_number = args[0]
        except IndexError:
            raise Exception("Please provide an iteration number!")
        self.name = ospath.basename(kwargs["name"]).split('.')[0]
        # Word and the indices of its sentences.
        self.sentence_with_indices = self.create_sentence_with_indices()
        # Sentences and the indices of their words
        self.word_with_indices = self.create_words_with_indices()
        self.latest_WSM = self.create_WSM()
        self.latest_SSM = self.create_SSM()
        self.counter = Counter(self.all_words)
        self.sum5 = sum(j for _, j in self.counter.most_common(5))
        print("Finish initialization...!")

    def create_words_with_indices(self):
        w_w_i = {w: i for i, w in enumerate(self.all_words)}
        total = {}
        for s, words in self.main_dict.items():
            if len(words) > 1:
                total[s] = list(itemgetter(*words)(w_w_i))
            elif words:
                total[s] = w_w_i[next(iter(words))]
        return total

    def create_sentence_with_indices(self):
        s_w_i = {s: i for i, s in enumerate(self.all_sent)}
        total = {}
        for w in self.all_words:
            sentences = self.sentence_include_word(w)
            if len(sentences) > 1:
                total[w] = list(itemgetter(*sentences)(s_w_i))
            elif sentences:
                total[w] = [s_w_i[sentences.pop()]]
        return total

    def create_WSM(self):
        """
        Initialize the word similarity matrix by creating a matrix with
        1 as its main digonal and columns with word names.
        """
        dt = np.dtype({"names": self.all_words, "formats": [np.float16] * self.all_words.size})
        wsm = np.zeros(self.all_words.size, dtype=dt)
        wsm_view = wsm.view(np.float16).reshape(self.all_words.size, -1)
        np.fill_diagonal(wsm_view, 1)
        return wsm

    def affinity_WS(self, W, S, n):
        # return max(self.WSM(n)[W][self.w_w_i[w]] for w in self.main_dict[S])
        return self.WSM(n)[W][self.word_with_indices[S]].max()

    def affinity_SW(self, S, W, n):
        return self.SSM(n)[S][self.sentence_with_indices[W]].max()

    def similarity_W(self, W1, W2, n):
        return sum(self.weight(s=s, w=W1) * self.affinity_SW(s, W2, n - 1)
                   for s in self.sentence_include_word(W1))

    def similarity_S(self, S1, S2, n):
        return sum(self.weight(w=w, s=S1) * self.affinity_WS(w, S2, n - 1) for w in self.main_dict[S1])

    def sentence_include_word(self, word):
        return {sent for sent, words in self.main_dict.items() if word in words}

    def update_WSM(self, n):
        print("update_WSM")
        new = [tuple(self.similarity_W(w, self.all_words[index], n)
                     for index in range(self.all_words.size))
               for w in self.all_words]

        self.latest_WSM[:] = new

    def update_SSM(self, n):
        print("update_SSM")
        new = [tuple(self.similarity_S(s, self.all_sent[index], n)
                     for index in range(self.all_sent.size))
               for s in self.all_sent]

        self.latest_SSM[:] = new

    def WSM(self, n):
        if n > 0:
            self.update_WSM(n)
        return self.latest_WSM

    def SSM(self, n):
        if n > 0:
            self.update_SSM(n)
        return self.latest_SSM

    def weight(self, **kwargs):
        W, S = kwargs['s'], kwargs['s']
        word_factor = max(0, 1 - self.counter[W] / self.sum5)
        other_words_factor = sum(max(0, 1 - self.counter[w] / self.sum5) for w in self.main_dict[S])
        return word_factor / other_words_factor

    def iteration(self):
        for i in range(1, self.iteration_number + 1):
            # Update SSM
            for w1, w2 in permutations(self.all_words, 2):
                self.similarity_W(w1, w2, i)
            print("Finished similarity_W, iteration {}".format(i))
            # Update WSM
            for s1, s2 in permutations(self.all_sent, 2):
                self.similarity_S(s1, s2, i)
            print("Finished similarity_S, iteration {}".format(i))
        self.save_matrixs()

    def save_matrixs(self):
        np.save("SSM_{}.txt".format(self.name),
                self.latest_SSM)
        np.save("WSM_{}.txt".format(self.name),
                self.latest_WSM)


if __name__ == "__main__":
    def load_data():
        file_names = glob.glob("files/*.json")
        for name in file_names:
            with open(name) as f:
                print(name)
                yield name, json.load(f)

    for name, d in load_data():
        FS = FindSimilarity(4, main_dict=d, name=name)
        print("All words {}".format(len(FS.all_words))),
        FS.iteration()