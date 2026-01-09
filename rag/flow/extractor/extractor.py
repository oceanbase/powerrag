#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
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
import json
import logging
import random
import traceback
from copy import deepcopy

import langextract as lx
import xxhash

from agent.component.llm import LLMParam, LLM
from rag.flow.base import ProcessBase, ProcessParamBase
from powerrag.server.services.langextract_service import get_langextract_service
from rag.prompts.generator import run_toc_from_text

logger = logging.getLogger(__name__)


class ExtractorParam(ProcessParamBase, LLMParam):
    def __init__(self):
        super().__init__()
        self.field_name = ""
        self.extraction_type = "simple"  # "simple" or "langextract"
        # langextract specific parameters
        self.prompt_description = ""  # Required for langextract
        self.examples = []  # List of example dicts for langextract

    def check(self):
        super().check()
        self.check_empty(self.field_name, "Result Destination")
        if self.extraction_type == "langextract":
            self.check_empty(self.prompt_description, "Prompt Description")


class Extractor(ProcessBase, LLM):
    component_name = "Extractor"

    async def _build_TOC(self, docs):
        self.callback(0.2,message="Start to generate table of content ...")
        docs = sorted(docs, key=lambda d:(
            d.get("page_num_int", 0)[0] if isinstance(d.get("page_num_int", 0), list) else d.get("page_num_int", 0),
            d.get("top_int", 0)[0] if isinstance(d.get("top_int", 0), list) else d.get("top_int", 0)
        ))
        toc = await run_toc_from_text([d["text"] for d in docs], self.chat_mdl)
        logging.info("------------ T O C -------------\n"+json.dumps(toc, ensure_ascii=False, indent='  '))
        ii = 0
        while ii < len(toc):
            try:
                idx = int(toc[ii]["chunk_id"])
                del toc[ii]["chunk_id"]
                toc[ii]["ids"] = [docs[idx]["id"]]
                if ii == len(toc) -1:
                    break
                for jj in range(idx+1, int(toc[ii+1]["chunk_id"])+1):
                    toc[ii]["ids"].append(docs[jj]["id"])
            except Exception as e:
                logging.exception(e)
            ii += 1

        if toc:
            d = deepcopy(docs[-1])
            d["doc_id"] = self._canvas._doc_id
            d["content_with_weight"] = json.dumps(toc, ensure_ascii=False)
            d["toc_kwd"] = "toc"
            d["available_int"] = 0
            d["page_num_int"] = [100000000]
            d["id"] = xxhash.xxh64((d["content_with_weight"] + str(d["doc_id"])).encode("utf-8", "surrogatepass")).hexdigest()
            return d
        return None

    async def _invoke(self, **kwargs):
        self.set_output("output_format", "chunks")
        self.callback(random.randint(1, 5) / 100.0, "Start to generate.")
        inputs = self.get_input_elements()
        chunks = []
        chunks_key = ""
        args = {}
        for k, v in inputs.items():
            args[k] = v["value"]
            if isinstance(args[k], list):
                chunks = deepcopy(args[k])
                chunks_key = k

        if self._param.extraction_type == "langextract":
            await self._invoke_langextract(chunks, chunks_key, args)
        else:
            await self._invoke_simple(chunks, chunks_key, args)

    async def _invoke_simple(self, chunks, chunks_key, args):
        if chunks:
            if self._param.field_name == "toc":
                for ck in chunks:
                    ck["doc_id"] = self._canvas._doc_id
                    ck["id"] = xxhash.xxh64((ck["text"] + str(ck["doc_id"])).encode("utf-8")).hexdigest()
                toc = await self._build_TOC(chunks)
                chunks.append(toc)
                self.set_output("chunks", chunks)
                return

            prog = 0
            for i, ck in enumerate(chunks):
                args[chunks_key] = ck["text"]
                msg, sys_prompt = self._sys_prompt_and_msg([], args)
                msg.insert(0, {"role": "system", "content": sys_prompt})
                ck[self._param.field_name] = await self._generate_async(msg)
                prog += 1. / len(chunks)
                if i % (len(chunks) // 100 + 1) == 1:
                    self.callback(prog, f"{i + 1} / {len(chunks)}")
            self.set_output("chunks", chunks)
        else:
            msg, sys_prompt = self._sys_prompt_and_msg([], args)
            msg.insert(0, {"role": "system", "content": sys_prompt})
            self.set_output("chunks", [{self._param.field_name: await self._generate_async(msg)}])

    async def _invoke_langextract(self, chunks, chunks_key, args):
        """Langextract-based extraction (compat with ob/main)."""
        try:
            langextract_service = get_langextract_service()
            tenant_id = self._canvas.get_tenant_id()
            llm_id = self._param.llm_id if hasattr(self._param, "llm_id") and self._param.llm_id else None

            examples = self._param.examples if hasattr(self._param, "examples") and self._param.examples else []

            temperature = None
            if hasattr(self._param, "temperature") and self._param.temperature > 0:
                temperature = float(self._param.temperature)

            model_parameters = {}
            if hasattr(self._param, "top_p") and self._param.top_p > 0:
                model_parameters["top_p"] = float(self._param.top_p)
            if hasattr(self._param, "max_tokens") and self._param.max_tokens > 0:
                model_parameters["max_tokens"] = int(self._param.max_tokens)
            if hasattr(self._param, "presence_penalty") and self._param.presence_penalty > 0:
                model_parameters["presence_penalty"] = float(self._param.presence_penalty)
            if hasattr(self._param, "frequency_penalty") and self._param.frequency_penalty > 0:
                model_parameters["frequency_penalty"] = float(self._param.frequency_penalty)

            if chunks:
                documents = []
                for i, ck in enumerate(chunks):
                    chunk_text = ck.get("text", "") or ck.get("content_with_weight", "")
                    doc_id = f"chunk_{i}"
                    documents.append(lx.data.Document(text=chunk_text, document_id=doc_id, additional_context=None))

                result = langextract_service.extract_sync(
                    text_or_documents=documents,
                    prompt_description=self._param.prompt_description,
                    examples=examples,
                    tenant_id=tenant_id,
                    llm_id=llm_id,
                    temperature=temperature,
                    model_parameters=model_parameters if model_parameters else None,
                    max_char_buffer=1000,
                    extraction_passes=1,
                )

                result = list(result)
                doc_id_to_extractions = {}
                for i, doc in enumerate(documents):
                    if i < len(result):
                        item = result[i]
                        extractions = item.get("extractions", [])
                        doc_id_to_extractions[doc.document_id] = extractions

                for i, ck in enumerate(chunks):
                    doc_id = f"chunk_{i}"
                    extractions = doc_id_to_extractions.get(doc_id, [])
                    ck[self._param.field_name] = {"langextract": extractions}

                self.set_output("chunks", chunks)
            else:
                text = args.get(chunks_key, "")
                if text:
                    result = langextract_service.extract_sync(
                        text_or_documents=text,
                        prompt_description=self._param.prompt_description,
                        examples=examples,
                        tenant_id=tenant_id,
                        llm_id=llm_id,
                        temperature=temperature,
                        model_parameters=model_parameters if model_parameters else None,
                        max_char_buffer=1000,
                        extraction_passes=1,
                    )
                    extractions = result.get("extractions", []) if isinstance(result, dict) else []
                    self.set_output("chunks", [{self._param.field_name: {"langextract": extractions}}])
                else:
                    self.set_output("chunks", [{self._param.field_name: {"langextract": []}}])
        except Exception as e:
            logger.exception(f"Error in langextract extraction: {e} \n{traceback.format_exc()}")
            raise e


