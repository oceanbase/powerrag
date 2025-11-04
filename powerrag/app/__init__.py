#
#  Copyright 2025 The OceanBase Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

"""PowerRAG Custom Parsers"""

from .title import chunk as title_chunk
from .regex import chunk as regex_chunk
from .smart import chunk as smart_chunk
import logging, copy, re
from rag.nlp import rag_tokenizer

__all__ = ['title_chunk', 'regex_chunk', 'smart_chunk']

def tokenize_chunks(chunks, doc, eng, pdf_parser=None):
    res = []
    # wrap up as es documents
    for ii, ck in enumerate(chunks):
        # Ensure ck is a string
        if not isinstance(ck, str):
            if isinstance(ck, tuple):
                # If it's a tuple, take the first element (content)
                ck = ck[0] if len(ck) > 0 else ""
            else:
                # Convert other types to string
                ck = str(ck) if ck is not None else ""
        
        # Skip empty chunks
        if not ck or len(ck.strip()) == 0:
            continue
        logging.debug("-- {}".format(ck))
        d = copy.deepcopy(doc)
        if pdf_parser:
            try:
                d["image"], poss = pdf_parser.crop(ck, need_position=True)
                add_positions(d, poss)
                ck = pdf_parser.remove_tag(ck)
            except (NotImplementedError, AttributeError, Exception) as e:
                # If crop fails, fallback to using chunk index as position
                # This ensures position information is always set for proper ordering
                logging.debug(f"Failed to get position from pdf_parser.crop: {e}, using chunk index")
                add_positions(d, [[ii]*5])
        else:
            # No PDF parser: use chunk index as position
            add_positions(d, [[ii]*5])
        tokenize(d, ck, eng)
        res.append(d)
    return res

def add_positions(d, poss):
    if not poss:
        return
    page_num_int = []
    position_int = []
    top_int = []
    for pn, left, right, top, bottom in poss:
        page_num_int.append(int(pn + 1))
        top_int.append(int(top))
        position_int.append((int(pn + 1), int(left), int(right), int(top), int(bottom)))
    d["page_num_int"] = page_num_int
    d["position_int"] = position_int
    d["top_int"] = top_int

def tokenize(d, t, eng):
    d["content_with_weight"] = t
    t = re.sub(r"</?(table|td|caption|tr|th)( [^<>]{0,12})?>", " ", t)
    d["content_ltks"] = rag_tokenizer.tokenize(t)
    d["content_sm_ltks"] = rag_tokenizer.fine_grained_tokenize(d["content_ltks"])