import { Button } from '@/components/ui/button';
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Textarea } from '@/components/ui/textarea';
import { Plus, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useFieldArray, useFormContext } from 'react-hook-form';
import { useTranslation } from 'react-i18next';

type LangextractConfigProps = {
  prefix?: string;
};

export function LangextractConfig({ prefix = '' }: LangextractConfigProps) {
  const { t } = useTranslation();
  const form = useFormContext();

  const promptDescriptionName =
    prefix + 'meta_data_filter.langextract_config.prompt_description';
  const examplesName = prefix + 'meta_data_filter.langextract_config.examples';

  const { fields, append, remove } = useFieldArray({
    name: examplesName,
    control: form.control,
  });

  return (
    <div className="space-y-4">
      <FormField
        control={form.control}
        name={promptDescriptionName}
        render={({ field }) => (
          <FormItem>
            <FormLabel>
              {t('flow.promptDescription') || 'Prompt Description'}
            </FormLabel>
            <FormControl>
              <Textarea
                {...field}
                placeholder={
                  t('flow.promptDescriptionPlaceholder') ||
                  'Enter the extraction prompt description...'
                }
                rows={6}
                className="!overflow-y-auto"
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      <FormField
        control={form.control}
        name={examplesName}
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
              {fields.map((field, index) => {
                return (
                  <div key={field.id} className="flex items-start gap-2">
                    <FormField
                      control={form.control}
                      name={`${examplesName}.${index}`}
                      render={({ field: formField }) => {
                        const ExampleTextarea = () => {
                          const [localValue, setLocalValue] = useState('');
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
                                  onPaste={() => {
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
                                        formField.onChange(normalizedValue);
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
                        onClick={() => append({ text: '', extractions: [] })}
                      >
                        <Plus className="h-4 w-4" />
                      </Button>
                    ) : (
                      <Button
                        type="button"
                        variant="ghost"
                        className="mt-2"
                        onClick={() => remove(index)}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                );
              })}
              {fields.length === 0 && (
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => append({ text: '', extractions: [] })}
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
    </div>
  );
}
