#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
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
import datetime
import json
import logging
import re
from copy import deepcopy
from typing import Optional, Tuple
import jinja2
import json_repair
import trio
from api.utils import hash_str2int
from rag.nlp import rag_tokenizer
from rag.prompts.template import load_prompt
from rag.settings import TAG_FLD
from rag.utils import encoder, num_tokens_from_string


STOP_TOKEN="<|STOP|>"
COMPLETE_TASK="complete_task"
INPUT_UTILIZATION = 0.5

def get_value(d, k1, k2):
    return d.get(k1, d.get(k2))


def chunks_format(reference):

    return [
        {
            "id": get_value(chunk, "chunk_id", "id"),
            "content": get_value(chunk, "content", "content_with_weight"),
            "document_id": get_value(chunk, "doc_id", "document_id"),
            "document_name": get_value(chunk, "docnm_kwd", "document_name"),
            "dataset_id": get_value(chunk, "kb_id", "dataset_id"),
            "image_id": get_value(chunk, "image_id", "img_id"),
            "positions": get_value(chunk, "positions", "position_int"),
            "url": chunk.get("url"),
            "similarity": chunk.get("similarity"),
            "vector_similarity": chunk.get("vector_similarity"),
            "term_similarity": chunk.get("term_similarity"),
            "doc_type": chunk.get("doc_type_kwd"),
        }
        for chunk in reference.get("chunks", [])
    ]


def message_fit_in(msg, max_length=4000):
    def count():
        nonlocal msg
        tks_cnts = []
        for m in msg:
            tks_cnts.append({"role": m["role"], "count": num_tokens_from_string(m["content"])})
        total = 0
        for m in tks_cnts:
            total += m["count"]
        return total

    c = count()
    if c < max_length:
        return c, msg

    msg_ = [m for m in msg if m["role"] == "system"]
    if len(msg) > 1:
        msg_.append(msg[-1])
    msg = msg_
    c = count()
    if c < max_length:
        return c, msg

    ll = num_tokens_from_string(msg_[0]["content"])
    ll2 = num_tokens_from_string(msg_[-1]["content"])
    if ll / (ll + ll2) > 0.8:
        m = msg_[0]["content"]
        m = encoder.decode(encoder.encode(m)[: max_length - ll2])
        msg[0]["content"] = m
        return max_length, msg

    m = msg_[-1]["content"]
    m = encoder.decode(encoder.encode(m)[: max_length - ll2])
    msg[-1]["content"] = m
    return max_length, msg


def kb_prompt(kbinfos, max_tokens, hash_id=False):
    from api.db.services.document_service import DocumentService

    knowledges = [get_value(ck, "content", "content_with_weight") for ck in kbinfos["chunks"]]
    kwlg_len = len(knowledges)
    used_token_count = 0
    chunks_num = 0
    for i, c in enumerate(knowledges):
        if not c:
            continue
        used_token_count += num_tokens_from_string(c)
        chunks_num += 1
        if max_tokens * 0.97 < used_token_count:
            knowledges = knowledges[:i]
            logging.warning(f"Not all the retrieval into prompt: {len(knowledges)}/{kwlg_len}")
            break

    docs = DocumentService.get_by_ids([get_value(ck, "doc_id", "document_id") for ck in kbinfos["chunks"][:chunks_num]])
    docs = {d.id: d.meta_fields for d in docs}

    def draw_node(k, line):
        if line is not None and not isinstance(line, str):
            line = str(line)
        if not line:
            return ""
        return f"\n├── {k}: " + re.sub(r"\n+", " ", line, flags=re.DOTALL)

    knowledges = []
    for i, ck in enumerate(kbinfos["chunks"][:chunks_num]):
        cnt = "\nID: {}".format(i if not hash_id else hash_str2int(get_value(ck, "id", "chunk_id"), 500))
        cnt += draw_node("Title", get_value(ck, "docnm_kwd", "document_name"))
        cnt += draw_node("URL", ck['url'])  if "url" in ck else ""
        for k, v in docs.get(get_value(ck, "doc_id", "document_id"), {}).items():
            cnt += draw_node(k, v)
        cnt += "\n└── Content:\n"
        cnt += get_value(ck, "content", "content_with_weight")
        knowledges.append(cnt)

    return knowledges


CITATION_PROMPT_TEMPLATE = load_prompt("citation_prompt")
CITATION_PLUS_TEMPLATE = load_prompt("citation_plus")
CONTENT_TAGGING_PROMPT_TEMPLATE = load_prompt("content_tagging_prompt")
CROSS_LANGUAGES_SYS_PROMPT_TEMPLATE = load_prompt("cross_languages_sys_prompt")
CROSS_LANGUAGES_USER_PROMPT_TEMPLATE = load_prompt("cross_languages_user_prompt")
FULL_QUESTION_PROMPT_TEMPLATE = load_prompt("full_question_prompt")
KEYWORD_PROMPT_TEMPLATE = load_prompt("keyword_prompt")
QUESTION_PROMPT_TEMPLATE = load_prompt("question_prompt")
VISION_LLM_DESCRIBE_PROMPT = load_prompt("vision_llm_describe_prompt")
VISION_LLM_FIGURE_DESCRIBE_PROMPT = load_prompt("vision_llm_figure_describe_prompt")

ANALYZE_TASK_SYSTEM = load_prompt("analyze_task_system")
ANALYZE_TASK_USER = load_prompt("analyze_task_user")
NEXT_STEP = load_prompt("next_step")
REFLECT = load_prompt("reflect")
SUMMARY4MEMORY = load_prompt("summary4memory")
RANK_MEMORY = load_prompt("rank_memory")
META_FILTER = load_prompt("meta_filter")
try:
    LANGEXTRACT_META_FILTER = load_prompt("langextract_meta_filter")
except FileNotFoundError:
    # Default template for langextract meta filter
    LANGEXTRACT_META_FILTER = """You are a metadata filtering condition generator for langextract extractions. Analyze the user's question, extraction schema, and available langextract metadata to output a JSON array of filter objects.

1. **Langextract Metadata Structure**: 
   - Langextract metadata is a list of extraction objects, each containing:
     - extraction_class: The type/category of extraction (e.g., "Product", "Person", "Event")
     - extraction_text: The extracted text content
     - attributes: Additional attributes as key-value pairs (e.g., {% raw %}{{"price": "100", "category": "electronics"}}{% endraw %})
   - Example metadata structure:
     {% raw %}[
       {"extraction_class": "Product", "extraction_text": "iPhone 15", "attributes": {"price": "999", "brand": "Apple"}},
       {"extraction_class": "Product", "extraction_text": "Samsung Galaxy", "attributes": {"price": "899", "brand": "Samsung"}}
     ]{% endraw %}

2. **Extraction Schema**:
   - Prompt Description: {{prompt_description}}
   - Examples: {{examples}}
   - Additional Context (available langextract data): {{additional_context}}

3. **Output Requirements**:
   - Always output a JSON array of filter objects
   - Each object must have:
        "key": (filter key, e.g., "extraction_class", "extraction_text", or "attributes_<attr_name>"),
        "value": (string value to compare),
        "op": (operator from allowed list)

4. **Operator Guide**:
   - Use these operators only: ["contains", "not contains", "start with", "end with", "empty", "not empty", "=", "≠", ">", "<", "≥", "≤"]
   - For extraction_class and extraction_text: Use "contains", "=", or "≠"
   - For attributes: Use "attributes_<attr_name>" as key (e.g., "attributes_price")
   - Date ranges: Break into two conditions (≥ start_date AND < next_month_start)
   - Negations: Always use "≠" for exclusion terms ("not", "except", "exclude")

5. **Processing Steps**:
   a) Identify filterable fields from the extraction schema and user query
   b) Match against extraction_class, extraction_text, or attributes
   c) Generate appropriate filter conditions
   d) Skip conditions if field doesn't exist in the extraction schema

6. **Example**:
   - User query: "Find products with price less than 1000"
   - Output: 
        {% raw %}[
          {"key": "extraction_class", "value": "Product", "op": "="},
          {"key": "attributes_price", "value": "1000", "op": "<"}
        ]{% endraw %}

**Current Task**:
- Today's date: {{current_date}}
- Extraction schema: {{prompt_description}}
- Examples: {{examples}}
- User query: "{{user_question}}"

Generate filters:"""
ASK_SUMMARY = load_prompt("ask_summary")

PROMPT_JINJA_ENV = jinja2.Environment(autoescape=False, trim_blocks=True, lstrip_blocks=True)


def citation_prompt(user_defined_prompts: dict={}) -> str:
    template = PROMPT_JINJA_ENV.from_string(user_defined_prompts.get("citation_guidelines", CITATION_PROMPT_TEMPLATE))
    return template.render()


def citation_plus(sources: str) -> str:
    template = PROMPT_JINJA_ENV.from_string(CITATION_PLUS_TEMPLATE)
    return template.render(example=citation_prompt(), sources=sources)


def keyword_extraction(chat_mdl, content, topn=3):
    template = PROMPT_JINJA_ENV.from_string(KEYWORD_PROMPT_TEMPLATE)
    rendered_prompt = template.render(content=content, topn=topn)

    msg = [{"role": "system", "content": rendered_prompt}, {"role": "user", "content": "Output: "}]
    _, msg = message_fit_in(msg, chat_mdl.max_length)
    kwd = chat_mdl.chat(rendered_prompt, msg[1:], {"temperature": 0.2})
    if isinstance(kwd, tuple):
        kwd = kwd[0]
    kwd = re.sub(r"^.*</think>", "", kwd, flags=re.DOTALL)
    if kwd.find("**ERROR**") >= 0:
        return ""
    return kwd


def question_proposal(chat_mdl, content, topn=3):
    template = PROMPT_JINJA_ENV.from_string(QUESTION_PROMPT_TEMPLATE)
    rendered_prompt = template.render(content=content, topn=topn)

    msg = [{"role": "system", "content": rendered_prompt}, {"role": "user", "content": "Output: "}]
    _, msg = message_fit_in(msg, chat_mdl.max_length)
    kwd = chat_mdl.chat(rendered_prompt, msg[1:], {"temperature": 0.2})
    if isinstance(kwd, tuple):
        kwd = kwd[0]
    kwd = re.sub(r"^.*</think>", "", kwd, flags=re.DOTALL)
    if kwd.find("**ERROR**") >= 0:
        return ""
    return kwd


def full_question(tenant_id=None, llm_id=None, messages=[], language=None, chat_mdl=None):
    from api.db import LLMType
    from api.db.services.llm_service import LLMBundle
    from api.db.services.tenant_llm_service import TenantLLMService

    if not chat_mdl:
        if TenantLLMService.llm_id2llm_type(llm_id) == "image2text":
            chat_mdl = LLMBundle(tenant_id, LLMType.IMAGE2TEXT, llm_id)
        else:
            chat_mdl = LLMBundle(tenant_id, LLMType.CHAT, llm_id)
    conv = []
    for m in messages:
        if m["role"] not in ["user", "assistant"]:
            continue
        conv.append("{}: {}".format(m["role"].upper(), m["content"]))
    conversation = "\n".join(conv)
    today = datetime.date.today().isoformat()
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

    template = PROMPT_JINJA_ENV.from_string(FULL_QUESTION_PROMPT_TEMPLATE)
    rendered_prompt = template.render(
        today=today,
        yesterday=yesterday,
        tomorrow=tomorrow,
        conversation=conversation,
        language=language,
    )

    ans = chat_mdl.chat(rendered_prompt, [{"role": "user", "content": "Output: "}])
    ans = re.sub(r"^.*</think>", "", ans, flags=re.DOTALL)
    return ans if ans.find("**ERROR**") < 0 else messages[-1]["content"]


def cross_languages(tenant_id, llm_id, query, languages=[]):
    from api.db import LLMType
    from api.db.services.llm_service import LLMBundle
    from api.db.services.tenant_llm_service import TenantLLMService

    if llm_id and TenantLLMService.llm_id2llm_type(llm_id) == "image2text":
        chat_mdl = LLMBundle(tenant_id, LLMType.IMAGE2TEXT, llm_id)
    else:
        chat_mdl = LLMBundle(tenant_id, LLMType.CHAT, llm_id)

    rendered_sys_prompt = PROMPT_JINJA_ENV.from_string(CROSS_LANGUAGES_SYS_PROMPT_TEMPLATE).render()
    rendered_user_prompt = PROMPT_JINJA_ENV.from_string(CROSS_LANGUAGES_USER_PROMPT_TEMPLATE).render(query=query, languages=languages)

    ans = chat_mdl.chat(rendered_sys_prompt, [{"role": "user", "content": rendered_user_prompt}], {"temperature": 0.2})
    ans = re.sub(r"^.*</think>", "", ans, flags=re.DOTALL)
    if ans.find("**ERROR**") >= 0:
        return query
    return "\n".join([a for a in re.sub(r"(^Output:|\n+)", "", ans, flags=re.DOTALL).split("===") if a.strip()])


def content_tagging(chat_mdl, content, all_tags, examples, topn=3):
    template = PROMPT_JINJA_ENV.from_string(CONTENT_TAGGING_PROMPT_TEMPLATE)

    for ex in examples:
        ex["tags_json"] = json.dumps(ex[TAG_FLD], indent=2, ensure_ascii=False)

    rendered_prompt = template.render(
        topn=topn,
        all_tags=all_tags,
        examples=examples,
        content=content,
    )

    msg = [{"role": "system", "content": rendered_prompt}, {"role": "user", "content": "Output: "}]
    _, msg = message_fit_in(msg, chat_mdl.max_length)
    kwd = chat_mdl.chat(rendered_prompt, msg[1:], {"temperature": 0.5})
    if isinstance(kwd, tuple):
        kwd = kwd[0]
    kwd = re.sub(r"^.*</think>", "", kwd, flags=re.DOTALL)
    if kwd.find("**ERROR**") >= 0:
        raise Exception(kwd)

    try:
        obj = json_repair.loads(kwd)
    except json_repair.JSONDecodeError:
        try:
            result = kwd.replace(rendered_prompt[:-1], "").replace("user", "").replace("model", "").strip()
            result = "{" + result.split("{")[1].split("}")[0] + "}"
            obj = json_repair.loads(result)
        except Exception as e:
            logging.exception(f"JSON parsing error: {result} -> {e}")
            raise e
    res = {}
    for k, v in obj.items():
        try:
            if int(v) > 0:
                res[str(k)] = int(v)
        except Exception:
            pass
    return res


def vision_llm_describe_prompt(page=None) -> str:
    template = PROMPT_JINJA_ENV.from_string(VISION_LLM_DESCRIBE_PROMPT)

    return template.render(page=page)


def vision_llm_figure_describe_prompt() -> str:
    template = PROMPT_JINJA_ENV.from_string(VISION_LLM_FIGURE_DESCRIBE_PROMPT)
    return template.render()


def tool_schema(tools_description: list[dict], complete_task=False):
    if not tools_description:
        return ""
    desc = {}
    if complete_task:
        desc[COMPLETE_TASK] = {
            "type": "function",
            "function": {
                "name": COMPLETE_TASK,
                "description": "When you have the final answer and are ready to complete the task, call this function with your answer",
                "parameters": {
                    "type": "object",
                    "properties": {"answer":{"type":"string", "description": "The final answer to the user's question"}},
                    "required": ["answer"]
                }
            }
        }
    for tool in tools_description:
        desc[tool["function"]["name"]] = tool

    return "\n\n".join([f"## {i+1}. {fnm}\n{json.dumps(des, ensure_ascii=False, indent=4)}" for i, (fnm, des) in enumerate(desc.items())])


def form_history(history, limit=-6):
    context = ""
    for h in history[limit:]:
        if h["role"] == "system":
            continue
        role = "USER"
        if h["role"].upper()!= role:
            role = "AGENT"
        context += f"\n{role}: {h['content'][:2048] + ('...' if len(h['content'])>2048 else '')}"
    return context


def analyze_task(chat_mdl, prompt, task_name, tools_description: list[dict], user_defined_prompts: dict={}):
    tools_desc = tool_schema(tools_description)
    context = ""

    if user_defined_prompts.get("task_analysis"):
        template = PROMPT_JINJA_ENV.from_string(user_defined_prompts["task_analysis"])
    else:
        template = PROMPT_JINJA_ENV.from_string(ANALYZE_TASK_SYSTEM + "\n\n" + ANALYZE_TASK_USER)
    context = template.render(task=task_name, context=context, agent_prompt=prompt, tools_desc=tools_desc)
    kwd = chat_mdl.chat(context, [{"role": "user", "content": "Please analyze it."}])
    if isinstance(kwd, tuple):
        kwd = kwd[0]
    kwd = re.sub(r"^.*</think>", "", kwd, flags=re.DOTALL)
    if kwd.find("**ERROR**") >= 0:
        return ""
    return kwd


def next_step(chat_mdl, history:list, tools_description: list[dict], task_desc, user_defined_prompts: dict={}):
    if not tools_description:
        return ""
    desc = tool_schema(tools_description)
    template = PROMPT_JINJA_ENV.from_string(user_defined_prompts.get("plan_generation", NEXT_STEP))
    user_prompt = "\nWhat's the next tool to call? If ready OR IMPOSSIBLE TO BE READY, then call `complete_task`."
    hist = deepcopy(history)
    if hist[-1]["role"] == "user":
        hist[-1]["content"] += user_prompt
    else:
        hist.append({"role": "user", "content": user_prompt})
    json_str = chat_mdl.chat(template.render(task_analysis=task_desc, desc=desc, today=datetime.datetime.now().strftime("%Y-%m-%d")),
                             hist[1:], stop=["<|stop|>"])
    tk_cnt = num_tokens_from_string(json_str)
    json_str = re.sub(r"^.*</think>", "", json_str, flags=re.DOTALL)
    return json_str, tk_cnt


def reflect(chat_mdl, history: list[dict], tool_call_res: list[Tuple], user_defined_prompts: dict={}):
    tool_calls = [{"name": p[0], "result": p[1]} for p in tool_call_res]
    goal = history[1]["content"]
    template = PROMPT_JINJA_ENV.from_string(user_defined_prompts.get("reflection", REFLECT))
    user_prompt = template.render(goal=goal, tool_calls=tool_calls)
    hist = deepcopy(history)
    if hist[-1]["role"] == "user":
        hist[-1]["content"] += user_prompt
    else:
        hist.append({"role": "user", "content": user_prompt})
    _, msg = message_fit_in(hist, chat_mdl.max_length)
    ans = chat_mdl.chat(msg[0]["content"], msg[1:])
    ans = re.sub(r"^.*</think>", "", ans, flags=re.DOTALL)
    return """
**Observation**
{}

**Reflection**
{}
    """.format(json.dumps(tool_calls, ensure_ascii=False, indent=2), ans)


def form_message(system_prompt, user_prompt):
    return [{"role": "system", "content": system_prompt},{"role": "user", "content": user_prompt}]


def tool_call_summary(chat_mdl, name: str, params: dict, result: str, user_defined_prompts: dict={}) -> str:
    template = PROMPT_JINJA_ENV.from_string(SUMMARY4MEMORY)
    system_prompt = template.render(name=name,
                           params=json.dumps(params, ensure_ascii=False, indent=2),
                           result=result)
    user_prompt = "→ Summary: "
    _, msg = message_fit_in(form_message(system_prompt, user_prompt), chat_mdl.max_length)
    ans = chat_mdl.chat(msg[0]["content"], msg[1:])
    return re.sub(r"^.*</think>", "", ans, flags=re.DOTALL)


def rank_memories(chat_mdl, goal:str, sub_goal:str, tool_call_summaries: list[str], user_defined_prompts: dict={}):
    template = PROMPT_JINJA_ENV.from_string(RANK_MEMORY)
    system_prompt = template.render(goal=goal, sub_goal=sub_goal, results=[{"i": i, "content": s} for i,s in enumerate(tool_call_summaries)])
    user_prompt = " → rank: "
    _, msg = message_fit_in(form_message(system_prompt, user_prompt), chat_mdl.max_length)
    ans = chat_mdl.chat(msg[0]["content"], msg[1:], stop="<|stop|>")
    return re.sub(r"^.*</think>", "", ans, flags=re.DOTALL)


def gen_meta_filter(chat_mdl, meta_data:dict, query: str) -> list:
    sys_prompt = PROMPT_JINJA_ENV.from_string(META_FILTER).render(
        current_date=datetime.datetime.today().strftime('%Y-%m-%d'),
        metadata_keys=json.dumps(meta_data),
        user_question=query
    )
    user_prompt = "Generate filters:"
    ans = chat_mdl.chat(sys_prompt, [{"role": "user", "content": user_prompt}])
    ans = re.sub(r"(^.*</think>|```json\n|```\n*$)", "", ans, flags=re.DOTALL)
    try:
        ans = json_repair.loads(ans)
        assert isinstance(ans, list), ans
        return ans
    except Exception:
        logging.exception(f"Loading json failure: {ans}")
    return []


def gen_langextract_meta_filter(chat_mdl, query: str, prompt_description: str, 
                                examples: list = None, additional_context: str = None) -> list:
    """
    Generate metadata filter conditions for langextract based on query, extraction schema, and context.
    
    Args:
        chat_mdl: Chat model for LLM generation
        query: User query string
        prompt_description: Extraction prompt description for langextract (defines extraction schema)
        examples: List of example dicts for langextract (shows extraction structure)
        additional_context: Additional context string (available metadata.langextract data)
    
    Returns:
        List of filter dicts with "key", "value", "op" format, same as gen_meta_filter
    """
    try:
        # Format examples as JSON string
        examples_str = json.dumps(examples, ensure_ascii=False, indent=2) if examples else "[]"
        
        # Build system prompt
        sys_prompt = PROMPT_JINJA_ENV.from_string(LANGEXTRACT_META_FILTER).render(
            current_date=datetime.datetime.today().strftime('%Y-%m-%d'),
            prompt_description=prompt_description,
            examples=examples_str,
            additional_context=additional_context or "",
            user_question=query
        )
        
        user_prompt = "Generate filters:"
        ans = chat_mdl.chat(sys_prompt, [{"role": "user", "content": user_prompt}])
        ans = re.sub(r"(^.*</think>|```json\n|```\n*$)", "", ans, flags=re.DOTALL)
        try:
            ans = json_repair.loads(ans)
            assert isinstance(ans, list), ans
            return ans
        except Exception:
            logging.exception(f"Loading json failure: {ans}")
            return []
    except Exception as e:
        logging.exception(f"Error in gen_langextract_meta_filter: {e}")
        return []


def format_langextract_filter_context(metas: dict, filters: Optional[list] = None, doc_ids: Optional[list] = None) -> str:
    """
    Format langextract metadata as a context string for LLM-based filtering.

    Args:
        metas: Metadata dictionary returned by DocumentService.get_meta_by_kbs.
        filters: Optional list of filter conditions to apply.
        doc_ids: Optional list of document IDs to restrict the context to.

    Returns:
        Formatted string containing available langextract extraction information.
    """
    if "langextract" not in metas or not metas["langextract"]:
        return ""
    
    # Get langextract data structure
    # metas["langextract"] should be a dict mapping extraction values to doc_ids
    # Format: {"extraction_class": {"Product": ["doc1", "doc2"], ...}, ...}
    langextract_data = metas["langextract"]
    
    # If doc_ids provided, filter to only those documents
    if doc_ids:
        filtered_data = {}
        for key, value_map in langextract_data.items():
            filtered_value_map = {}
            for val, docs in value_map.items():
                filtered_docs = [d for d in docs if d in doc_ids]
                if filtered_docs:
                    filtered_value_map[val] = filtered_docs
            if filtered_value_map:
                filtered_data[key] = filtered_value_map
        langextract_data = filtered_data
    
    # Format as JSON string for context
    try:
        context_str = json.dumps(langextract_data, ensure_ascii=False, indent=2)
        return f"Available langextract metadata:\n{context_str}"
    except Exception as e:
        logging.exception(f"Error formatting langextract context: {e}")
        return ""


def _filter_langextract_docs(metas: dict, filters: list, regular_doc_ids: Optional[list] = None) -> list:
    """
    Filter documents based on langextract metadata filters.
    
    Args:
        metas: Metadata dict from DocumentService.get_meta_by_kbs
        filters: List of filter conditions (same format as gen_meta_filter)
        regular_doc_ids: Optional list of doc_ids from regular metadata filtering (for intersection)
    
    Returns:
        List of document IDs that match the langextract filters
    """
    if "langextract" not in metas or not metas["langextract"]:
        return []
    
    if not filters:
        return []
    
    # Get all documents that have langextract metadata
    all_langextract_docs = set()
    langextract_meta = metas["langextract"]
    
    
        
    # langextract_meta structure: {str(meta_list): [doc_id1, doc_id2, ...], ...}
    # where meta_list is a list of extraction dicts
    for meta_items_str, doc_ids in langextract_meta.items():
        try:
            # Try to parse as JSON first
            if isinstance(meta_items_str, str):
                try:
                    meta_items = json.loads(meta_items_str)
                except (json.JSONDecodeError, ValueError):
                    # If JSON parsing fails, try using json_repair or ast.literal_eval
                    try:
                        import ast
                        meta_items = ast.literal_eval(meta_items_str)
                    except (ValueError, SyntaxError):
                        logging.warning(f"Failed to parse meta_items: {meta_items_str[:100]}")
                        continue
            else:
                # If it's already a list/dict, use it directly
                meta_items = meta_items_str
            
            # Ensure meta_items is a list
            if not isinstance(meta_items, list):
                if isinstance(meta_items, dict):
                    meta_items = [meta_items]
                else:
                    logging.warning(f"meta_items is not a list or dict: {type(meta_items)}")
                    continue
            is_match = True
            for filter_item in filters:
                key = filter_item.get("key", "")
                op = filter_item.get("op", "=")
                value = filter_item.get("value", "")
                is_filter_match = False
                # Process each meta item
                for meta_item in meta_items:
                    if not isinstance(meta_item, dict):
                        continue
                    
                    # Handle different key formats
                    if key == "extraction_class":
                        if "extraction_class" in meta_item:
                            v = meta_item["extraction_class"]
                            is_filter_match = _is_match_filter_operator(v, op, value)
                    elif key == "extraction_text":
                        if "extraction_text" in meta_item:
                            v = meta_item["extraction_text"]
                            is_filter_match = _is_match_filter_operator(v, op, value)
                            
                    elif key.startswith("attributes_"):
                        # Filter by attribute (e.g., "attributes_price")
                        attr_name = key.replace("attributes_", "")
                        attr_key = f"attributes_{attr_name}"
                        if attr_key in meta_item:
                            v = meta_item[attr_key]
                            is_filter_match = _is_match_filter_operator(v, op, value)
                    # This means the current filter condition has been successfully matched, can continue to check the next filter condition
                    if is_filter_match:
                        break
                # This means the current filter condition has not been matched, can break out of the loop
                if not is_filter_match:
                    is_match = False
                    break
            if is_match:
                all_langextract_docs.update(doc_ids)
        except Exception as e:
            logging.exception(f"Error processing meta_items: {e}")
            continue
    
    result_doc_ids = list(all_langextract_docs)
    
    # Intersect with regular_doc_ids if provided
    if regular_doc_ids:
        result_doc_ids = [d for d in result_doc_ids if d in regular_doc_ids]
    
    return result_doc_ids


def _is_match_filter_operator(value_in_meta: str, operator: str, value: str) -> bool:
    """
    Applies a filter operator for a single metadata value.

    Args:
        value_in_meta: The value from the metadata to compare.
        operator: The filter operator to apply (e.g., contains, =, ≠, >, <, ≥, ≤, not contains, start with, end with).
        value: The value to compare against.

    Returns:
        bool: True if value_in_meta matches the operator and value, otherwise False.
    """
    is_match = False
    try:
        # Try numeric comparison
        value_in_meta_num = float(value_in_meta)
        val_num = float(value)
        
        if operator == "=":
            is_match = value_in_meta_num == val_num
        elif operator == "≠":
            is_match = value_in_meta_num != val_num
        elif operator == ">":
            is_match = value_in_meta_num > val_num
        elif operator == "<":
            is_match = value_in_meta_num < val_num
        elif operator == "≥":
            is_match = value_in_meta_num >= val_num
        elif operator == "≤":
            is_match = value_in_meta_num <= val_num
        elif operator == "contains":
            is_match = str(value).lower() in str(value_in_meta_num).lower()
        elif operator == "not contains":
            is_match = str(value).lower() not in str(value_in_meta_num).lower()
        elif operator == "start with":
            is_match = str(value_in_meta_num).lower().startswith(str(value).lower())
        elif operator == "end with":
            is_match = str(value_in_meta_num).lower().endswith(str(value).lower())
    except (ValueError, TypeError):
        # String comparison
        value_in_meta_str = str(value_in_meta).lower()
        val_str = str(value).lower()
        
        if operator == "=":
            is_match = value_in_meta_str == val_str
        elif operator == "≠":
            is_match = value_in_meta_str != val_str
        elif operator == ">":
            # String comparison for > operator
            is_match = value_in_meta_str > val_str
        elif operator == "<":
            # String comparison for < operator
            is_match = value_in_meta_str < val_str
        elif operator == "≥":
            # String comparison for ≥ operator
            is_match = value_in_meta_str >= val_str
        elif operator == "≤":
            # String comparison for ≤ operator
            is_match = value_in_meta_str <= val_str
        elif operator == "contains":
            is_match = val_str in value_in_meta_str
        elif operator == "not contains":
            is_match = val_str not in value_in_meta_str
        elif operator == "start with":
            is_match = value_in_meta_str.startswith(val_str)
        elif operator == "end with":
            is_match = value_in_meta_str.endswith(val_str)
        elif operator == "empty":
            is_match = not value_in_meta_str
        elif operator == "not empty":
            is_match = value_in_meta_str
    return is_match
  


def _get_langextract_config_from_pipeline(kb_ids: list) -> Optional[dict]:
    """
    Get langextract configuration from knowledge base's pipeline.
    Searches for Extractor nodes with extraction_type="langextract" in the pipeline DSL.
    
    Args:
        kb_ids: List of knowledge base IDs
    
    Returns:
        Dict with "prompt_description" and "examples" if found, None otherwise.
        Returns None if no langextract extractor is found in the pipeline (e.g., when using simple extraction).
    """
    try:
        from api.db.services.knowledgebase_service import KnowledgebaseService
        from api.db.services.canvas_service import UserCanvasService
        import json
        
        # Get knowledge bases
        kbs = KnowledgebaseService.get_by_ids(kb_ids)
        if not kbs:
            return None
        
        # Try each KB's pipeline
        for kb in kbs:
            if not kb.pipeline_id:
                continue
            
            # Get pipeline DSL
            e, canvas = UserCanvasService.get_by_canvas_id(kb.pipeline_id)
            if not e or not canvas:
                continue
            
            dsl = canvas.get("dsl") if isinstance(canvas, dict) else canvas.dsl
            if not dsl:
                continue
            
            # Parse DSL if it's a string
            if isinstance(dsl, str):
                try:
                    dsl = json.loads(dsl)
                except Exception:
                    continue
            
            # Find Extractor nodes with extraction_type="langextract"
            components = dsl.get("components", {})
            for component_id, component in components.items():
                obj = component.get("obj", {})
                component_name = obj.get("component_name", "")
                params = obj.get("params", {})
                
                # Check if this is an Extractor node with langextract type
                if component_name == "Extractor":
                    extraction_type = params.get("extraction_type", "")
                    if extraction_type == "langextract":
                        prompt_description = params.get("prompt_description", "")
                        examples = params.get("examples", [])
                        if prompt_description:
                            return {
                                "prompt_description": prompt_description,
                                "examples": examples if examples else []
                            }
        
        return None
    except Exception as e:
        logging.exception(f"Error getting langextract config from pipeline: {e}")
        return None


def apply_metadata_filter(metas: dict, meta_data_filter: dict, query: str, chat_mdl, initial_doc_ids: Optional[list] = None, kb_ids: Optional[list] = None):
    """
    Apply metadata filtering with support for both regular and langextract metadata.
    This is a unified function that handles all metadata filtering logic.
    
    Args:
        metas: Metadata dict from DocumentService.get_meta_by_kbs
        meta_data_filter: Filter configuration dict with keys:
            - method: "auto" or "manual"
            - manual: List of filter dicts (for manual method)
            - enable_custom_langextract_config: Optional boolean flag to enable custom langchain extraction config.
                                                If False or not set, will use config from knowledge base pipeline.
            - langextract_config: Optional dict with langextract config:
                - prompt_description: Extraction prompt description
                - examples: List of example dicts
        query: User query string (for auto method)
        chat_mdl: Chat model instance (for auto method)
        initial_doc_ids: Optional initial list of doc_ids to start with
        kb_ids: Optional list of knowledge base IDs (used to get langextract config from pipeline)
    
    Note:
        Whether langextract filtering is used depends on:
        1. Whether there is langextract metadata in the knowledge base
        2. Whether a valid prompt_description can be obtained (from custom config or pipeline)
    
    Returns:
        List of filtered document IDs, or None if no documents match
    """
    from api.db.services.dialog_service import meta_filter
    
    if not meta_data_filter:
        return initial_doc_ids if initial_doc_ids else None
    
    doc_ids = None
    
    # Check if custom langchain extraction config is enabled
    enable_custom_langextract_config = meta_data_filter.get("enable_custom_langextract_config", False)
    
    # Check if there's langextract metadata and configuration
    has_langextract = False
    langextract_config = meta_data_filter.get("langextract_config")
    prompt_description = ""
    examples = []
    
    # Try to get langextract config: use custom config if enabled, otherwise use pipeline config
    if kb_ids:
        # If custom config is enabled, try to get from custom config first
        if enable_custom_langextract_config and langextract_config:
            prompt_description = langextract_config.get("prompt_description", "")
            examples = langextract_config.get("examples", [])
        
        # If custom config is not enabled or missing/incomplete, try to get from pipeline
        if not enable_custom_langextract_config or not prompt_description or not examples:
            pipeline_config = _get_langextract_config_from_pipeline(kb_ids)
            if pipeline_config:
                if not prompt_description:
                    prompt_description = pipeline_config.get("prompt_description", "")
                if not examples:
                    examples = pipeline_config.get("examples", [])
                
                # If using pipeline config, update langextract_config for consistency
                # but don't overwrite custom config if it's enabled
                if not enable_custom_langextract_config:
                    if not langextract_config:
                        langextract_config = {}
                        meta_data_filter["langextract_config"] = langextract_config
                    if prompt_description:
                        langextract_config["prompt_description"] = prompt_description
                    if examples:
                        langextract_config["examples"] = examples
        
        # Check if we have prompt_description and if any document has langextract metadata
        if prompt_description:
            # Check if any document has langextract metadata
            if "langextract" in metas and metas["langextract"]:
                has_langextract = True
    
    if has_langextract and prompt_description:
        # Use langextract-specific filtering
        # prompt_description and examples are already set above
        
        if meta_data_filter.get("method") == "auto" or meta_data_filter.get("method") == "automatic":
            # First, get initial filters using regular meta_filter (for non-langextract fields)
            regular_metas = {k: v for k, v in metas.items() if k != "langextract"}
            regular_doc_ids = []
            if regular_metas:
                regular_filters = gen_meta_filter(chat_mdl, regular_metas, query)
                regular_doc_ids = meta_filter(regular_metas, regular_filters)
            
            # Get initial additional_context from all documents (before filtering)
            # initial_additional_context = format_langextract_filter_context(metas, [], None)
            
            # Generate langextract-specific filters
            langextract_filters = gen_langextract_meta_filter(
                chat_mdl, query, prompt_description, examples
            )
            
            # Apply langextract filters to get filtered doc_ids
            if langextract_filters:
                # Apply langextract filters using meta_filter logic adapted for langextract structure
                langextract_doc_ids = _filter_langextract_docs(metas, langextract_filters, regular_doc_ids)
                
                # Combine regular and langextract filtered doc_ids
                if regular_doc_ids:
                    doc_ids = list(set(regular_doc_ids) & set(langextract_doc_ids))
                else:
                    doc_ids = langextract_doc_ids
            else:
                doc_ids = regular_doc_ids
            
            # Intersect with initial_doc_ids if provided
            if initial_doc_ids:
                doc_ids = [d for d in doc_ids if d in initial_doc_ids]
            
            if not doc_ids:
                doc_ids = None
        elif meta_data_filter.get("method") == "manual":
            # Manual filters for langextract
            manual_filters = meta_data_filter["manual"]
            # Separate regular and langextract filters
            regular_filters = [f for f in manual_filters if f.get("key") != "langextract" and 
                              f.get("key") not in ["extraction_class", "extraction_text"] and
                              not f.get("key", "").startswith("attributes_")]
            langextract_filters = [f for f in manual_filters if f.get("key") in ["extraction_class", "extraction_text"] or
                                  f.get("key", "").startswith("attributes_")]
            
            regular_doc_ids = []
            if regular_filters:
                regular_metas = {k: v for k, v in metas.items() if k != "langextract"}
                if regular_metas:
                    regular_doc_ids = meta_filter(regular_metas, regular_filters)
            
            if langextract_filters:
                langextract_doc_ids = _filter_langextract_docs(metas, langextract_filters, regular_doc_ids)
                if regular_doc_ids:
                    doc_ids = list(set(regular_doc_ids) & set(langextract_doc_ids))
                else:
                    doc_ids = langextract_doc_ids
            else:
                doc_ids = regular_doc_ids
            
            # Intersect with initial_doc_ids if provided
            if initial_doc_ids:
                doc_ids = [d for d in doc_ids if d in initial_doc_ids]
            
            if not doc_ids:
                doc_ids = None
    else:
        # Regular metadata filtering (non-langextract)
        if meta_data_filter.get("method") == "auto" or meta_data_filter.get("method") == "automatic":
            filters = gen_meta_filter(chat_mdl, metas, query)
            filtered_doc_ids = meta_filter(metas, filters)
            if initial_doc_ids:
                doc_ids = [d for d in filtered_doc_ids if d in initial_doc_ids]
            else:
                doc_ids = filtered_doc_ids
            if not doc_ids:
                doc_ids = None
        elif meta_data_filter.get("method") == "manual":
            filtered_doc_ids = meta_filter(metas, meta_data_filter["manual"])
            if initial_doc_ids:
                doc_ids = [d for d in filtered_doc_ids if d in initial_doc_ids]
            else:
                doc_ids = filtered_doc_ids
            if not doc_ids:
                doc_ids = None
    
    return doc_ids


def gen_json(system_prompt:str, user_prompt:str, chat_mdl, gen_conf = None):
    from graphrag.utils import get_llm_cache, set_llm_cache
    cached = get_llm_cache(chat_mdl.llm_name, system_prompt, user_prompt, gen_conf)
    if cached:
        return json_repair.loads(cached)
    _, msg = message_fit_in(form_message(system_prompt, user_prompt), chat_mdl.max_length)
    ans = chat_mdl.chat(msg[0]["content"], msg[1:],gen_conf=gen_conf)
    ans = re.sub(r"(^.*</think>|```json\n|```\n*$)", "", ans, flags=re.DOTALL)
    try:
        res = json_repair.loads(ans)
        set_llm_cache(chat_mdl.llm_name, system_prompt, ans, user_prompt, gen_conf)
        return res
    except Exception:
        logging.exception(f"Loading json failure: {ans}")


TOC_DETECTION = load_prompt("toc_detection")
def detect_table_of_contents(page_1024:list[str], chat_mdl):
    toc_secs = []
    for i, sec in enumerate(page_1024[:22]):
        ans = gen_json(PROMPT_JINJA_ENV.from_string(TOC_DETECTION).render(page_txt=sec), "Only JSON please.", chat_mdl)
        if toc_secs and not ans["exists"]:
            break
        toc_secs.append(sec)
    return toc_secs


TOC_EXTRACTION = load_prompt("toc_extraction")
TOC_EXTRACTION_CONTINUE = load_prompt("toc_extraction_continue")
def extract_table_of_contents(toc_pages, chat_mdl):
    if not toc_pages:
        return []

    return gen_json(PROMPT_JINJA_ENV.from_string(TOC_EXTRACTION).render(toc_page="\n".join(toc_pages)), "Only JSON please.", chat_mdl)


def toc_index_extractor(toc:list[dict], content:str, chat_mdl):
    tob_extractor_prompt = """
    You are given a table of contents in a json format and several pages of a document, your job is to add the physical_index to the table of contents in the json format.

    The provided pages contains tags like <physical_index_X> and <physical_index_X> to indicate the physical location of the page X.

    The structure variable is the numeric system which represents the index of the hierarchy section in the table of contents. For example, the first section has structure index 1, the first subsection has structure index 1.1, the second subsection has structure index 1.2, etc.

    The response should be in the following JSON format: 
    [
        {
            "structure": <structure index, "x.x.x" or None> (string),
            "title": <title of the section>,
            "physical_index": "<physical_index_X>" (keep the format)
        },
        ...
    ]

    Only add the physical_index to the sections that are in the provided pages.
    If the title of the section are not in the provided pages, do not add the physical_index to it.
    Directly return the final JSON structure. Do not output anything else."""

    prompt = tob_extractor_prompt + '\nTable of contents:\n' + json.dumps(toc, ensure_ascii=False, indent=2) + '\nDocument pages:\n' + content
    return gen_json(prompt, "Only JSON please.", chat_mdl)


TOC_INDEX = load_prompt("toc_index")
def table_of_contents_index(toc_arr: list[dict], sections: list[str], chat_mdl):
    if not toc_arr or not sections:
        return []

    toc_map = {}
    for i, it in enumerate(toc_arr):
        k1 = (it["structure"]+it["title"]).replace(" ", "")
        k2 = it["title"].strip()
        if k1 not in toc_map:
            toc_map[k1] = []
        if k2 not in toc_map:
            toc_map[k2] = []
        toc_map[k1].append(i)
        toc_map[k2].append(i)

    for it in toc_arr:
        it["indices"] = []
    for i, sec in enumerate(sections):
        sec = sec.strip()
        if sec.replace(" ", "") in toc_map:
            for j in toc_map[sec.replace(" ", "")]:
                toc_arr[j]["indices"].append(i)

    all_pathes = []
    def dfs(start, path):
        nonlocal all_pathes
        if start >= len(toc_arr):
            if path:
                all_pathes.append(path)
            return
        if not toc_arr[start]["indices"]:
            dfs(start+1, path)
            return
        added = False
        for j in toc_arr[start]["indices"]:
            if path and j < path[-1][0]:
                continue
            _path = deepcopy(path)
            _path.append((j, start))
            added = True
            dfs(start+1, _path)
        if not added and path:
            all_pathes.append(path)

    dfs(0, [])
    path = max(all_pathes, key=lambda x:len(x))
    for it in toc_arr:
        it["indices"] = []
    for j, i in path:
        toc_arr[i]["indices"] = [j]
    print(json.dumps(toc_arr, ensure_ascii=False, indent=2))

    i = 0
    while i < len(toc_arr):
        it  = toc_arr[i]
        if it["indices"]:
            i += 1
            continue

        if i>0 and toc_arr[i-1]["indices"]:
            st_i = toc_arr[i-1]["indices"][-1]
        else:
            st_i = 0
        e = i + 1
        while e <len(toc_arr) and not toc_arr[e]["indices"]:
            e += 1
        if e >= len(toc_arr):
            e = len(sections)
        else:
            e = toc_arr[e]["indices"][0]

        for j in range(st_i, min(e+1, len(sections))):
            ans = gen_json(PROMPT_JINJA_ENV.from_string(TOC_INDEX).render(
                structure=it["structure"],
                title=it["title"],
                text=sections[j]), "Only JSON please.", chat_mdl)
            if ans["exist"] == "yes":
                it["indices"].append(j)
                break

        i += 1

    return toc_arr


def check_if_toc_transformation_is_complete(content, toc, chat_mdl):
    prompt = """
    You are given a raw table of contents and a  table of contents.
    Your job is to check if the  table of contents is complete.

    Reply format:
    {{
        "thinking": <why do you think the cleaned table of contents is complete or not>
        "completed": "yes" or "no"
    }}
    Directly return the final JSON structure. Do not output anything else."""

    prompt = prompt + '\n Raw Table of contents:\n' + content + '\n Cleaned Table of contents:\n' + toc
    response = gen_json(prompt, "Only JSON please.", chat_mdl)
    return response['completed']


def toc_transformer(toc_pages, chat_mdl):
    init_prompt = """
    You are given a table of contents, You job is to transform the whole table of content into a JSON format included table_of_contents.

    The `structure` is the numeric system which represents the index of the hierarchy section in the table of contents. For example, the first section has structure index 1, the first subsection has structure index 1.1, the second subsection has structure index 1.2, etc.
    The `title` is a short phrase or a several-words term.
    
    The response should be in the following JSON format: 
    [
        {
            "structure": <structure index, "x.x.x" or None> (string),
            "title": <title of the section>
        },
        ...
    ],
    You should transform the full table of contents in one go.
    Directly return the final JSON structure, do not output anything else. """

    toc_content = "\n".join(toc_pages)
    prompt = init_prompt + '\n Given table of contents\n:' + toc_content
    def clean_toc(arr):
        for a in arr:
            a["title"] = re.sub(r"[.·….]{2,}", "", a["title"])
    last_complete = gen_json(prompt, "Only JSON please.", chat_mdl)
    if_complete = check_if_toc_transformation_is_complete(toc_content, json.dumps(last_complete, ensure_ascii=False, indent=2), chat_mdl)
    clean_toc(last_complete)
    if if_complete == "yes":
        return last_complete

    while not (if_complete == "yes"):
        prompt = f"""
        Your task is to continue the table of contents json structure, directly output the remaining part of the json structure.
        The response should be in the following JSON format: 

        The raw table of contents json structure is:
        {toc_content}

        The incomplete transformed table of contents json structure is:
        {json.dumps(last_complete[-24:], ensure_ascii=False, indent=2)}

        Please continue the json structure, directly output the remaining part of the json structure."""
        new_complete = gen_json(prompt, "Only JSON please.", chat_mdl)
        if not new_complete or str(last_complete).find(str(new_complete)) >= 0:
            break
        clean_toc(new_complete)
        last_complete.extend(new_complete)
        if_complete = check_if_toc_transformation_is_complete(toc_content, json.dumps(last_complete, ensure_ascii=False, indent=2), chat_mdl)

    return last_complete


TOC_LEVELS = load_prompt("assign_toc_levels")
def assign_toc_levels(toc_secs, chat_mdl, gen_conf = {"temperature": 0.2}):
    if not toc_secs:
        return []
    return gen_json(
        PROMPT_JINJA_ENV.from_string(TOC_LEVELS).render(),
        str(toc_secs),
        chat_mdl,
        gen_conf
    )


TOC_FROM_TEXT_SYSTEM = load_prompt("toc_from_text_system")
TOC_FROM_TEXT_USER = load_prompt("toc_from_text_user")
# Generate TOC from text chunks with text llms
async def gen_toc_from_text(txt_info: dict, chat_mdl, callback=None):
    try:
        ans = gen_json(
            PROMPT_JINJA_ENV.from_string(TOC_FROM_TEXT_SYSTEM).render(),
            PROMPT_JINJA_ENV.from_string(TOC_FROM_TEXT_USER).render(text="\n".join([json.dumps(d, ensure_ascii=False) for d in txt_info["chunks"]])),
            chat_mdl,
            gen_conf={"temperature": 0.0, "top_p": 0.9}
        )
        txt_info["toc"] = ans if ans and not isinstance(ans, str) else []
        if callback:
            callback(msg="")
    except Exception as e:
        logging.exception(e)


def split_chunks(chunks, max_length: int):
    """
    Pack chunks into batches according to max_length, returning [{"id": idx, "text": chunk_text}, ...].
    Do not split a single chunk, even if it exceeds max_length.
    """

    result = []
    batch, batch_tokens = [], 0

    for idx, chunk in enumerate(chunks):
        t = num_tokens_from_string(chunk)
        if batch_tokens + t > max_length:
            result.append(batch)
            batch, batch_tokens = [], 0
        batch.append({idx: chunk})
        batch_tokens += t
    if batch:
        result.append(batch)
    return result


async def run_toc_from_text(chunks, chat_mdl, callback=None):
    input_budget = int(chat_mdl.max_length * INPUT_UTILIZATION) - num_tokens_from_string(
        TOC_FROM_TEXT_USER + TOC_FROM_TEXT_SYSTEM
    )

    input_budget =  1024 if input_budget > 1024 else input_budget
    chunk_sections = split_chunks(chunks, input_budget)
    titles = []

    chunks_res = []
    async with trio.open_nursery() as nursery:
        for i, chunk in enumerate(chunk_sections):
            if not chunk:
                continue
            chunks_res.append({"chunks": chunk})
            nursery.start_soon(gen_toc_from_text, chunks_res[-1], chat_mdl, callback)

    for chunk in chunks_res:
        titles.extend(chunk.get("toc", []))
        
    # Filter out entries with title == -1
    prune = len(titles) > 512
    max_len = 12 if prune else 22
    filtered = []
    for x in titles:
        if not isinstance(x, dict) or not x.get("title") or x["title"] == "-1":
            continue
        if len(rag_tokenizer.tokenize(x["title"]).split(" ")) > max_len:
            continue
        if re.match(r"[0-9,.()/ -]+$", x["title"]):
            continue
        filtered.append(x)

    logging.info(f"\n\nFiltered TOC sections:\n{filtered}")
    if not filtered:
        return []

    # Generate initial level (level/title)
    raw_structure = [x.get("title", "") for x in filtered]

    # Assign hierarchy levels using LLM
    toc_with_levels = assign_toc_levels(raw_structure, chat_mdl, {"temperature": 0.0, "top_p": 0.9})
    if not toc_with_levels:
        return []

    # Merge structure and content (by index)
    prune = len(toc_with_levels) > 512
    max_lvl = sorted([t.get("level", "0") for t in toc_with_levels])[-1]
    merged = []
    for _ , (toc_item, src_item) in enumerate(zip(toc_with_levels, filtered)):
        if prune and toc_item.get("level", "0") >= max_lvl:
            continue
        merged.append({
            "level": toc_item.get("level", "0"),
            "title": toc_item.get("title", ""),
            "chunk_id": src_item.get("chunk_id", ""),
        })

    return merged


TOC_RELEVANCE_SYSTEM = load_prompt("toc_relevance_system")
TOC_RELEVANCE_USER = load_prompt("toc_relevance_user")
def relevant_chunks_with_toc(query: str, toc:list[dict], chat_mdl, topn: int=6):
    import numpy as np
    try:
        ans = gen_json(
            PROMPT_JINJA_ENV.from_string(TOC_RELEVANCE_SYSTEM).render(),
            PROMPT_JINJA_ENV.from_string(TOC_RELEVANCE_USER).render(query=query, toc_json="[\n%s\n]\n"%"\n".join([json.dumps({"level": d["level"], "title":d["title"]}, ensure_ascii=False) for d in toc])),
            chat_mdl,
            gen_conf={"temperature": 0.0, "top_p": 0.9}
        )
        id2score = {}
        for ti, sc in zip(toc, ans):
            if not isinstance(sc, dict) or sc.get("score", -1) < 1:
                continue
            for id in ti.get("ids", []):
                if id not in id2score:
                    id2score[id] = []
                id2score[id].append(sc["score"]/5.)
        for id in id2score.keys():
            id2score[id] = np.mean(id2score[id])
        return [(id, sc) for id, sc in list(id2score.items()) if sc>=0.3][:topn]
    except Exception as e:
        logging.exception(e)
    return []
