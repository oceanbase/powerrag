import { ConfirmDeleteDialog } from '@/components/confirm-delete-dialog';
import { LargeModelFormField } from '@/components/large-model-form-field';
import { LlmSettingSchema } from '@/components/llm-setting-items/next';
import { SelectWithSearch } from '@/components/originui/select-with-search';
import { RAGFlowFormItem } from '@/components/ragflow-form';
import { Button } from '@/components/ui/button';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Textarea } from '@/components/ui/textarea';
import { PromptEditor } from '@/pages/agent/form/components/prompt-editor';
import { buildOptions } from '@/utils/form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Plus, X } from 'lucide-react';
import { memo, useEffect, useMemo, useRef, useState } from 'react';
import { useFieldArray, useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';
import {
  ContextGeneratorFieldName,
  initialExtractorValues,
} from '../../constant';
import { useBuildNodeOutputOptions } from '../../hooks/use-build-options';
import { useFormValues } from '../../hooks/use-form-values';
import { useWatchFormChange } from '../../hooks/use-watch-form-change';
import { INextOperatorForm } from '../../interface';
import { buildOutputList } from '../../utils/build-output-list';
import { FormWrapper } from '../components/form-wrapper';
import { Output } from '../components/output';
import { useSwitchPrompt } from './use-switch-prompt';

export const FormSchema = z
  .object({
    field_name: z.string(),
    sys_prompt: z.string().optional(),
    prompts: z.string().optional(),
    extraction_type: z.enum(['simple', 'langextract']).default('simple'),
    prompt_description: z.string().optional(),
    examples: z.array(z.any()).optional(),
    ...LlmSettingSchema,
  })
  .refine(
    (data) => {
      if (data.extraction_type === 'simple') {
        return !!data.sys_prompt && data.sys_prompt.trim().length > 0;
      }
      return true;
    },
    {
      message: 'System Prompt is required for simple extraction type',
      path: ['sys_prompt'],
    },
  )
  .refine(
    (data) => {
      if (data.extraction_type === 'langextract') {
        return (
          !!data.prompt_description && data.prompt_description.trim().length > 0
        );
      }
      return true;
    },
    {
      message: 'Prompt Description is required for langextract extraction type',
      path: ['prompt_description'],
    },
  );

export type ExtractorFormSchemaType = z.infer<typeof FormSchema>;

const outputList = buildOutputList(initialExtractorValues.outputs);

const ExtractorForm = ({ node }: INextOperatorForm) => {
  const defaultValues = useFormValues(initialExtractorValues, node);
  const { t } = useTranslation();

  const form = useForm<ExtractorFormSchemaType>({
    defaultValues,
    resolver: zodResolver(FormSchema),
    // mode: 'onChange',
  });

  const promptOptions = useBuildNodeOutputOptions(node?.id);

  const options = buildOptions(ContextGeneratorFieldName, t, 'dataflow');

  const {
    handleFieldNameChange,
    confirmSwitch,
    hideModal,
    visible,
    cancelSwitch,
  } = useSwitchPrompt(form);

  useWatchFormChange(node?.id, form);

  // Watch extraction_type to reactively update UI
  const extractionType =
    form.watch('extraction_type') || defaultValues?.extraction_type || 'simple';

  const extractionTypeOptions = useMemo(
    () => [
      { value: 'simple', label: t('flow.extractionType.simple') || 'Simple' },
      {
        value: 'langextract',
        label: t('flow.extractionType.langextract') || 'Langextract',
      },
    ],
    [t],
  );

  const {
    fields: exampleFields,
    append: appendExample,
    remove: removeExample,
  } = useFieldArray({
    name: 'examples',
    control: form.control,
  });

  const isLangextract = extractionType === 'langextract';

  return (
    <Form {...form}>
      <FormWrapper>
        <LargeModelFormField></LargeModelFormField>
        <RAGFlowFormItem
          label={t('flow.extractionType') || 'Extraction Type'}
          name="extraction_type"
        >
          {(field) => (
            <SelectWithSearch
              {...field}
              options={extractionTypeOptions}
            ></SelectWithSearch>
          )}
        </RAGFlowFormItem>
        <RAGFlowFormItem label={t('dataflow.fieldName')} name="field_name">
          {(field) => (
            <SelectWithSearch
              onChange={(value) => {
                field.onChange(value);
                // Only trigger prompt switch for simple extraction type
                if (!isLangextract) {
                  handleFieldNameChange(value);
                }
              }}
              value={field.value}
              placeholder={t('dataFlowPlaceholder')}
              options={options}
            ></SelectWithSearch>
          )}
        </RAGFlowFormItem>
        {!isLangextract && (
          <>
            <RAGFlowFormItem label={t('flow.systemPrompt')} name="sys_prompt">
              <PromptEditor
                placeholder={t('flow.messagePlaceholder')}
                showToolbar={true}
                baseOptions={promptOptions}
              ></PromptEditor>
            </RAGFlowFormItem>
            <RAGFlowFormItem label={t('flow.userPrompt')} name="prompts">
              <PromptEditor
                showToolbar={true}
                baseOptions={promptOptions}
              ></PromptEditor>
            </RAGFlowFormItem>
          </>
        )}
        {isLangextract && (
          <>
            <RAGFlowFormItem
              label={t('flow.promptDescription') || 'Prompt Description'}
              name="prompt_description"
              required
            >
              <PromptEditor
                placeholder={
                  t('flow.promptDescriptionPlaceholder') ||
                  'Enter the extraction prompt description...'
                }
                showToolbar={true}
                baseOptions={promptOptions}
              ></PromptEditor>
            </RAGFlowFormItem>
            <FormField
              control={form.control}
              name="examples"
              render={() => (
                <FormItem>
                  <FormLabel
                    tooltip={
                      t('flow.examplesTooltip') ||
                      'Examples for langextract extraction'
                    }
                  >
                    {t('flow.examples') || 'Examples'}
                  </FormLabel>
                  <div className="space-y-4">
                    {exampleFields.map((field, index) => {
                      return (
                        <div key={field.id} className="flex items-start gap-2">
                          <FormField
                            control={form.control}
                            name={`examples.${index}`}
                            render={({ field: formField }) => {
                              const ExampleTextarea = () => {
                                const [localValue, setLocalValue] =
                                  useState('');
                                const isEditingRef = useRef(false);

                                // Initialize local value from field value
                                useEffect(() => {
                                  // Only update if not currently editing to avoid overwriting user input
                                  if (!isEditingRef.current) {
                                    const jsonValue =
                                      typeof formField.value === 'string'
                                        ? formField.value
                                        : JSON.stringify(
                                            formField.value || {
                                              text: '',
                                              extractions: [],
                                            },
                                            null,
                                            2,
                                          );
                                    setLocalValue(jsonValue);
                                  }
                                }, [formField.value]);

                                return (
                                  <FormItem className="flex-1">
                                    <FormControl>
                                      <Textarea
                                        value={localValue}
                                        onFocus={() => {
                                          isEditingRef.current = true;
                                        }}
                                        onChange={(e) => {
                                          const newValue = e.target.value;
                                          setLocalValue(newValue);
                                        }}
                                        onPaste={(e) => {
                                          // Allow default paste behavior
                                          // The onChange will handle the update
                                          isEditingRef.current = true;
                                        }}
                                        onBlur={(e) => {
                                          isEditingRef.current = false;
                                          // On blur, try to parse and validate
                                          const value = e.target.value.trim();
                                          if (!value) {
                                            formField.onChange({
                                              text: '',
                                              extractions: [],
                                            });
                                            setLocalValue('{}');
                                            return;
                                          }
                                          try {
                                            const parsed = JSON.parse(value);
                                            if (
                                              typeof parsed === 'object' &&
                                              parsed !== null
                                            ) {
                                              const normalizedValue = {
                                                text: parsed.text || '',
                                                extractions: Array.isArray(
                                                  parsed.extractions,
                                                )
                                                  ? parsed.extractions
                                                  : [],
                                              };
                                              formField.onChange(
                                                normalizedValue,
                                              );
                                              setLocalValue(
                                                JSON.stringify(
                                                  normalizedValue,
                                                  null,
                                                  2,
                                                ),
                                              );
                                            } else {
                                              formField.onChange({
                                                text: '',
                                                extractions: [],
                                              });
                                              setLocalValue('{}');
                                            }
                                          } catch (error) {
                                            // If invalid JSON, revert to last valid value
                                            const jsonValue =
                                              typeof formField.value ===
                                              'string'
                                                ? formField.value
                                                : JSON.stringify(
                                                    formField.value || {
                                                      text: '',
                                                      extractions: [],
                                                    },
                                                    null,
                                                    2,
                                                  );
                                            setLocalValue(jsonValue);
                                          }
                                        }}
                                        placeholder={
                                          t('flow.examplesPlaceholder') ||
                                          'Enter example as JSON: {"text": "...", "extractions": [...]}'
                                        }
                                        rows={4}
                                        className="!overflow-y-auto"
                                        style={{
                                          maxHeight: '400px',
                                          minHeight: '80px',
                                          overflowY: 'auto',
                                        }}
                                      />
                                    </FormControl>
                                    <FormMessage />
                                  </FormItem>
                                );
                              };
                              return <ExampleTextarea />;
                            }}
                          />
                          {index === 0 ? (
                            <Button
                              type="button"
                              variant="ghost"
                              className="mt-2"
                              onClick={() =>
                                appendExample({ text: '', extractions: [] })
                              }
                            >
                              <Plus className="h-4 w-4" />
                            </Button>
                          ) : (
                            <Button
                              type="button"
                              variant="ghost"
                              className="mt-2"
                              onClick={() => removeExample(index)}
                            >
                              <X className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      );
                    })}
                    {exampleFields.length === 0 && (
                      <Button
                        type="button"
                        variant="ghost"
                        onClick={() =>
                          appendExample({ text: '', extractions: [] })
                        }
                        className="text-sm text-blue-500"
                      >
                        {t('flow.addExample') || '+ Add Example'}
                      </Button>
                    )}
                  </div>
                  <FormMessage />
                </FormItem>
              )}
            />
          </>
        )}
        <Output list={outputList}></Output>
      </FormWrapper>
      {visible && (
        <ConfirmDeleteDialog
          title={t('dataflow.switchPromptMessage')}
          open
          onOpenChange={hideModal}
          onOk={confirmSwitch}
          onCancel={cancelSwitch}
        ></ConfirmDeleteDialog>
      )}
    </Form>
  );
};

export default memo(ExtractorForm);
