# -*- coding: utf-8 -*-

"""KGE models that only use triples."""

from .complex_cwa import ComplexCWA
from .trans_e import TransE
from .trans_h import TransH

__all__ = [
    'ComplexCWA',
    'TransE',
    'TransH',
]
