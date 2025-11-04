import { LlmModelType } from '@/constants/knowledge';
import { useSetModalState } from '@/hooks/common-hooks';

import { useSelectLlmOptionsByModelType } from '@/hooks/llm-hooks';
import { useFetchKnowledgeBaseConfiguration } from '@/hooks/use-knowledge-request';
import { useSelectParserList } from '@/hooks/user-setting-hooks';
import { useIsFetching } from '@tanstack/react-query';
import { pick } from 'lodash';
import { useCallback, useEffect, useState } from 'react';
import { UseFormReturn } from 'react-hook-form';
import { z } from 'zod';
import { formSchema } from './form-schema';

// The value that does not need to be displayed in the analysis method Select
const HiddenFields = ['email', 'picture', 'audio'];

export function useSelectChunkMethodList() {
  const parserList = useSelectParserList();

  return parserList.filter((x) => !HiddenFields.some((y) => y === x.value));
}

export function useSelectEmbeddingModelOptions() {
  const allOptions = useSelectLlmOptionsByModelType();
  return allOptions[LlmModelType.Embedding];
}

export function useHasParsedDocument(isEdit?: boolean) {
  const { data: knowledgeDetails } = useFetchKnowledgeBaseConfiguration({
    isEdit,
  });
  return knowledgeDetails.chunk_num > 0;
}

export const useFetchKnowledgeConfigurationOnMount = (
  form: UseFormReturn<z.infer<typeof formSchema>, any, undefined>,
) => {
  const { data: knowledgeDetails } = useFetchKnowledgeBaseConfiguration();

  useEffect(() => {
    if (!knowledgeDetails || !knowledgeDetails.parser_id) {
      return;
    }

    // Start with backend data first, then merge defaults for missing fields
    const backendParserConfig = knowledgeDetails.parser_config || {};
    const defaultParserConfig =
      form.formState?.defaultValues?.parser_config || {};

    // Set default delimiter and regex_pattern based on parser type
    let defaultDelimiter = defaultParserConfig.delimiter || '\n';
    let defaultRegexPattern = defaultParserConfig.regex_pattern || '[.!?]+\\s*';

    if (knowledgeDetails.parser_id === 'regex') {
      if (!backendParserConfig.delimiter) {
        defaultDelimiter = '\n。.；;！!？？';
      }
      if (!backendParserConfig.regex_pattern) {
        defaultRegexPattern = '[.!?]+\\s*';
      }
    }

    const parser_config = {
      // Start with defaults
      ...defaultParserConfig,
      // Override with backend data (backend data takes priority)
      ...backendParserConfig,
      // Set delimiter: use backend value if exists, otherwise use parser-specific default
      delimiter: backendParserConfig.delimiter || defaultDelimiter,
      // Set regex_pattern: use backend value if exists, otherwise use parser-specific default
      regex_pattern: backendParserConfig.regex_pattern || defaultRegexPattern,
      // Handle nested objects
      raptor: {
        ...defaultParserConfig?.raptor,
        ...backendParserConfig?.raptor,
        use_raptor: backendParserConfig?.raptor?.use_raptor ?? true,
      },
      graphrag: {
        ...defaultParserConfig?.graphrag,
        ...backendParserConfig?.graphrag,
        use_graphrag: backendParserConfig?.graphrag?.use_graphrag ?? true,
      },
    };

    // Explicitly preserve title_level from backend if it exists
    if (
      backendParserConfig.title_level !== undefined &&
      backendParserConfig.title_level !== null
    ) {
      parser_config.title_level = backendParserConfig.title_level;
    }

    console.log(
      '🔍 Final parser_config:',
      JSON.stringify(parser_config, null, 2),
    );
    console.log(
      '🔍 Final parser_config.title_level:',
      parser_config.title_level,
    );

    const formValues = {
      ...pick({ ...knowledgeDetails, parser_config: parser_config }, [
        'description',
        'name',
        'permission',
        'embd_id',
        'parser_id',
        'language',
        'parser_config',
        'pagerank',
        'avatar',
      ]),
    } as z.infer<typeof formSchema>;

    console.log(
      '🔍 Form values before reset:',
      JSON.stringify(formValues, null, 2),
    );
    console.log(
      '🔍 Form values.parser_config.title_level:',
      formValues.parser_config?.title_level,
    );

    // Use reset with options to ensure values are properly set
    form.reset(formValues, {
      keepDefaultValues: false,
      keepValues: false,
    });

    // Verify after reset - use multiple checks
    setTimeout(() => {
      const currentTitleLevel = form.getValues('parser_config.title_level');
      const currentParserConfig = form.getValues('parser_config');
      console.log(
        '🔍 Form value after reset - parser_config.title_level:',
        currentTitleLevel,
      );
      console.log(
        '🔍 Form value after reset - parser_config:',
        JSON.stringify(currentParserConfig, null, 2),
      );

      // If title_level is not correct, try to set it again
      if (
        formValues.parser_config?.title_level !== undefined &&
        formValues.parser_config?.title_level !== null &&
        currentTitleLevel !== formValues.parser_config?.title_level
      ) {
        console.warn(
          '⚠️ title_level mismatch! Expected:',
          formValues.parser_config?.title_level,
          'Got:',
          currentTitleLevel,
        );
        console.warn('⚠️ Attempting to fix by setting title_level directly...');
        form.setValue(
          'parser_config.title_level',
          formValues.parser_config.title_level,
        );
        const fixedTitleLevel = form.getValues('parser_config.title_level');
        console.log('🔧 Fixed title_level:', fixedTitleLevel);
      }
    }, 200);
  }, [form, knowledgeDetails]);

  return knowledgeDetails;
};

export const useSelectKnowledgeDetailsLoading = () =>
  useIsFetching({ queryKey: ['fetchKnowledgeDetail'] }) > 0;

export const useRenameKnowledgeTag = () => {
  const [tag, setTag] = useState<string>('');
  const {
    visible: tagRenameVisible,
    hideModal: hideTagRenameModal,
    showModal: showFileRenameModal,
  } = useSetModalState();

  const handleShowTagRenameModal = useCallback(
    (record: string) => {
      setTag(record);
      showFileRenameModal();
    },
    [showFileRenameModal],
  );

  return {
    initialName: tag,
    tagRenameVisible,
    hideTagRenameModal,
    showTagRenameModal: handleShowTagRenameModal,
  };
};
