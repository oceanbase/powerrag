import { SelectWithSearch } from '@/components/originui/select-with-search';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { useFetchKnowledgeMetadata } from '@/hooks/use-knowledge-request';
import { SwitchOperatorOptions } from '@/pages/agent/constant';
import { useBuildSwitchOperatorOptions } from '@/pages/agent/form/switch-form';
import { Plus, X } from 'lucide-react';
import { useCallback, useMemo } from 'react';
import { useFieldArray, useFormContext } from 'react-hook-form';
import { useTranslation } from 'react-i18next';

export function MetadataFilterConditions({
  kbIds,
  prefix = '',
}: {
  kbIds: string[];
  prefix?: string;
}) {
  const { t } = useTranslation();
  const form = useFormContext();
  const name = prefix + 'meta_data_filter.manual';
  const metadata = useFetchKnowledgeMetadata(kbIds);

  const switchOperatorOptions = useBuildSwitchOperatorOptions();

  const { fields, remove, append } = useFieldArray({
    name,
    control: form.control,
  });

  // Check if langextract metadata exists
  const hasLangextract = metadata.data && 'langextract' in metadata.data;

  // Get available metadata keys, including langextract-specific fields if present
  const availableKeys = useMemo(() => {
    const keys: string[] = [];

    // Add regular metadata keys (excluding langextract)
    const regularKeys = Object.keys(metadata.data || {}).filter(
      (key) => key !== 'langextract',
    );
    keys.push(...regularKeys);

    // If langextract metadata exists, add langextract-specific filter fields
    if (hasLangextract) {
      // Add base langextract fields
      if (!keys.includes('extraction_class')) {
        keys.push('extraction_class');
      }
      if (!keys.includes('extraction_text')) {
        keys.push('extraction_text');
      }

      // Extract all attributes_* keys from langextract metadata
      // langextract is an array of objects, each containing extraction_class, extraction_text, and attributes_*
      const langextractMeta = metadata.data?.langextract;
      if (langextractMeta) {
        const attributeKeysSet = new Set<string>();

        // Handle both array and object formats
        if (Array.isArray(langextractMeta)) {
          // If it's an array, iterate through each item
          langextractMeta.forEach((item: any) => {
            if (item && typeof item === 'object') {
              // Extract all keys that start with 'attributes_'
              Object.keys(item).forEach((key) => {
                if (key.startsWith('attributes_')) {
                  attributeKeysSet.add(key);
                }
              });
            }
          });
        } else if (typeof langextractMeta === 'object') {
          // If it's an object, check if it has attributes_* keys directly
          Object.keys(langextractMeta).forEach((key) => {
            if (key.startsWith('attributes_')) {
              attributeKeysSet.add(key);
            }
          });
        }

        // Add unique attribute keys to the list
        attributeKeysSet.forEach((attrKey) => {
          if (!keys.includes(attrKey)) {
            keys.push(attrKey);
          }
        });
      }
    }

    // Sort keys: regular fields first, then langextract fields (extraction_class, extraction_text, then attributes_*)
    return keys.sort((a, b) => {
      const aIsLangextract =
        a === 'extraction_class' ||
        a === 'extraction_text' ||
        a.startsWith('attributes_');
      const bIsLangextract =
        b === 'extraction_class' ||
        b === 'extraction_text' ||
        b.startsWith('attributes_');

      if (aIsLangextract && !bIsLangextract) return 1;
      if (!aIsLangextract && bIsLangextract) return -1;

      // Within langextract fields, sort: extraction_class, extraction_text, then attributes_*
      if (aIsLangextract && bIsLangextract) {
        if (a === 'extraction_class') return -1;
        if (b === 'extraction_class') return 1;
        if (a === 'extraction_text') return -1;
        if (b === 'extraction_text') return 1;
      }

      return a.localeCompare(b);
    });
  }, [metadata.data, hasLangextract]);

  const add = useCallback(
    (key: string) => () => {
      append({
        key,
        value: '',
        op: SwitchOperatorOptions[0].value,
      });
    },
    [append],
  );

  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <FormLabel>{t('chat.conditions')}</FormLabel>
        <DropdownMenu>
          <DropdownMenuTrigger>
            <Button variant={'ghost'} type="button">
              <Plus />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="max-h-[300px] !overflow-y-auto scrollbar-auto">
            {availableKeys.map((key, idx) => {
              return (
                <DropdownMenuItem key={idx} onClick={add(key)}>
                  {key}
                </DropdownMenuItem>
              );
            })}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <div className="space-y-5">
        {fields.map((field, index) => {
          const typeField = `${name}.${index}.key`;
          return (
            <div key={field.id} className="flex w-full items-center gap-2">
              <FormField
                control={form.control}
                name={typeField}
                render={({ field }) => (
                  <FormItem className="flex-1 overflow-hidden">
                    <FormControl>
                      <Input
                        {...field}
                        placeholder={t('common.pleaseInput')}
                      ></Input>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <Separator className="w-3 text-text-secondary" />
              <FormField
                control={form.control}
                name={`${name}.${index}.op`}
                render={({ field }) => (
                  <FormItem className="flex-1 overflow-hidden">
                    <FormControl>
                      <SelectWithSearch
                        {...field}
                        options={switchOperatorOptions}
                      ></SelectWithSearch>
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <Separator className="w-3 text-text-secondary" />
              <FormField
                control={form.control}
                name={`${name}.${index}.value`}
                render={({ field }) => (
                  <FormItem className="flex-1 overflow-hidden">
                    <FormControl>
                      <Input placeholder={t('common.pleaseInput')} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <Button variant={'ghost'} onClick={() => remove(index)}>
                <X className="text-text-sub-title-invert " />
              </Button>
            </div>
          );
        })}
      </div>
    </section>
  );
}
