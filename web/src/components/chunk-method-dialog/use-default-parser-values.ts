import { DocumentParserType } from '@/constants/knowledge';
import { IParserConfig } from '@/interfaces/database/document';
import { useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { ParseDocumentType } from '../layout-recognize-form-field';

export function useDefaultParserValues(parserId?: string) {
  const { t } = useTranslation();

  const defaultParserValues = useMemo(() => {
    // Set delimiter and regex_pattern based on parser type
    let delimiter = '\n';
    let regex_pattern: string | undefined = undefined;
    if (parserId === DocumentParserType.Regex) {
      delimiter = '\n。.；;！!？？';
      regex_pattern = '[.!?]+\\s*';
    }

    const defaultParserValues = {
      task_page_size: 12,
      layout_recognize: ParseDocumentType.DeepDOC,
      chunk_token_num: 512,
      min_chunk_tokens: 64,
      delimiter,
      regex_pattern,
      auto_keywords: 0,
      auto_questions: 0,
      html4excel: false,
      toc_extraction: false,
      // raptor: {
      //   use_raptor: false,
      //   prompt: t('knowledgeConfiguration.promptText'),
      //   max_token: 256,
      //   threshold: 0.1,
      //   max_cluster: 64,
      //   random_seed: 0,
      // },
      // graphrag: {
      //   use_graphrag: false,
      // },
      entity_types: [],
      pages: [],
    };

    return defaultParserValues;
  }, [t, parserId]);

  return defaultParserValues;
}

export function useFillDefaultValueOnMount() {
  const fillDefaultValue = useCallback(
    (parserConfig: IParserConfig, parserId?: string) => {
      // Get default delimiter and regex_pattern based on parser type
      let defaultDelimiter = '\n';
      let defaultRegexPattern: string | undefined = undefined;
      if (parserId === DocumentParserType.Regex) {
        defaultDelimiter = '\n。.；;！!？？';
        defaultRegexPattern = '[.!?]+\\s*';
      }

      // Build default values object
      const defaultParserValues = {
        task_page_size: 12,
        layout_recognize: ParseDocumentType.DeepDOC,
        chunk_token_num: 512,
        min_chunk_tokens: 64,
        delimiter: defaultDelimiter,
        regex_pattern: defaultRegexPattern,
        auto_keywords: 0,
        auto_questions: 0,
        html4excel: false,
        toc_extraction: false,
        entity_types: [],
        pages: [],
      };

      return Object.entries(defaultParserValues).reduce<Record<string, any>>(
        (pre, [key, value]) => {
          if (key in parserConfig) {
            pre[key] = parserConfig[key as keyof IParserConfig];
          } else {
            pre[key] = value;
          }
          return pre;
        },
        {},
      );
    },
    [],
  );

  return fillDefaultValue;
}
