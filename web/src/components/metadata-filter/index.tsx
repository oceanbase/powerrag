import { DatasetMetadata } from '@/constants/chat';
import { useTranslate } from '@/hooks/common-hooks';
import { useFetchKnowledgeMetadata } from '@/hooks/use-knowledge-request';
import { useFormContext, useWatch } from 'react-hook-form';
import { z } from 'zod';
import { SelectWithSearch } from '../originui/select-with-search';
import { RAGFlowFormItem } from '../ragflow-form';
import { SwitchFormField } from '../switch-fom-field';
import { LangextractConfig } from './langextract-config';
import { MetadataFilterConditions } from './metadata-filter-conditions';

type MetadataFilterProps = {
  prefix?: string;
};

export const MetadataFilterSchema = {
  meta_data_filter: z
    .object({
      method: z.string().optional(),
      manual: z
        .array(
          z.object({
            key: z.string(),
            op: z.string(),
            value: z.string(),
          }),
        )
        .optional(),
      enable_custom_langextract_config: z.boolean().optional(),
      langextract_config: z
        .object({
          prompt_description: z.string().optional(),
          examples: z.array(z.any()).optional(),
        })
        .optional(),
    })
    .optional(),
};

export function MetadataFilter({ prefix = '' }: MetadataFilterProps) {
  const { t } = useTranslate('chat');
  const form = useFormContext();

  const methodName = prefix + 'meta_data_filter.method';
  const enableLangextractConfigName =
    prefix + 'meta_data_filter.enable_custom_langextract_config';

  const kbIds: string[] = useWatch({
    control: form.control,
    name: prefix + 'kb_ids',
  });
  const metadata = useWatch({
    control: form.control,
    name: methodName,
  });
  const enableLangextractConfig = useWatch({
    control: form.control,
    name: enableLangextractConfigName,
  });
  const hasKnowledge = Array.isArray(kbIds) && kbIds.length > 0;

  // Check if langextract metadata exists
  const metadataData = useFetchKnowledgeMetadata(kbIds);
  const hasLangextract =
    metadataData.data && 'langextract' in metadataData.data;

  const MetadataOptions = Object.values(DatasetMetadata).map((x) => {
    return {
      value: x,
      label: t(`meta.${x}`),
    };
  });

  return (
    <>
      {hasKnowledge && (
        <RAGFlowFormItem
          label={t('metadata')}
          name={methodName}
          tooltip={t('metadataTip')}
        >
          <SelectWithSearch
            options={MetadataOptions}
            triggerClassName="!bg-bg-input"
          />
        </RAGFlowFormItem>
      )}
      {hasKnowledge && metadata === DatasetMetadata.Manual && (
        <MetadataFilterConditions
          kbIds={kbIds}
          prefix={prefix}
        ></MetadataFilterConditions>
      )}
      {hasKnowledge &&
        metadata === DatasetMetadata.Automatic &&
        hasLangextract && (
          <>
            <SwitchFormField
              name={enableLangextractConfigName}
              label={
                t('customLangchainExtractionConfig') ||
                'Custom Langchain Extraction Config'
              }
              tooltip={
                t('customLangchainExtractionConfigTip') ||
                'Enable custom langchain extraction configuration. If disabled, the configuration from the knowledge base pipeline will be used.'
              }
            />
            {enableLangextractConfig && (
              <LangextractConfig prefix={prefix}></LangextractConfig>
            )}
          </>
        )}
    </>
  );
}
