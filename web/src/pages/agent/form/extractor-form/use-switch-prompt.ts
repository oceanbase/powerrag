import { LlmSettingSchema } from '@/components/llm-setting-items/next';
import { useSetModalState } from '@/hooks/common-hooks';
import { useCallback, useRef } from 'react';
import { UseFormReturn } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';

export const FormSchema = z.object({
  field_name: z.string(),
  sys_prompt: z.string().optional(),
  prompts: z.string().optional(),
  extraction_type: z.enum(['simple', 'langextract']).default('simple'),
  prompt_description: z.string().optional(),
  examples: z.array(z.any()).optional(),
  ...LlmSettingSchema,
});

export type ExtractorFormSchemaType = z.infer<typeof FormSchema>;

export function useSwitchPrompt(form: UseFormReturn<any>) {
  const { visible, showModal, hideModal } = useSetModalState();
  const { t } = useTranslation();
  const previousFieldNames = useRef<string[]>([form.getValues('field_name')]);

  const setPromptValue = useCallback(
    (field: keyof ExtractorFormSchemaType, key: string, value: string) => {
      form.setValue(field, t(`flow.prompts.${key}.${value}`), {
        shouldDirty: true,
        shouldValidate: true,
      });
    },
    [form, t],
  );

  const handleFieldNameChange = useCallback(
    (value: string) => {
      if (value) {
        const names = previousFieldNames.current;
        if (names.length > 1) {
          names.shift();
        }
        names.push(value);
        showModal();
      }
    },
    [showModal],
  );

  const confirmSwitch = useCallback(() => {
    const value = form.getValues('field_name');
    setPromptValue('sys_prompt', 'system', value);
    setPromptValue('prompts', 'user', value);
  }, [form, setPromptValue]);

  const cancelSwitch = useCallback(() => {
    const previousValue = previousFieldNames.current.at(-2);
    if (previousValue) {
      form.setValue('field_name', previousValue, {
        shouldDirty: true,
        shouldValidate: true,
      });
    }
  }, [form]);

  return {
    handleFieldNameChange,
    confirmSwitch,
    hideModal,
    visible,
    cancelSwitch,
  };
}
