export interface IChangeParserConfigRequestBody {
  pages?: number[][];
  chunk_token_num?: number;
  layout_recognize?: string | boolean;
  task_page_size?: number;
  delimiter?: string;
  regex_pattern?: string;
  auto_keywords?: number;
  auto_questions?: number;
  html4excel?: boolean;
  toc_extraction?: boolean;
  entity_types?: string[];
  pattern?: string; // Deprecated: use regex_pattern instead, kept for backward compatibility
  min_chunk_tokens?: number;
  title_level?: number;
  [key: string]: any; // Allow additional fields
}

export interface IChangeParserRequestBody {
  parser_id: string;
  pipeline_id: string;
  doc_id: string;
  parser_config: IChangeParserConfigRequestBody;
}

export interface IDocumentMetaRequestBody {
  documentId: string;
  meta: string; // json format string
}
