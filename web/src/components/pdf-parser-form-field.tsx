import { cn } from '@/lib/utils';
import { ReactNode } from 'react';
import { useFormContext } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { SelectWithSearch } from './originui/select-with-search';
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from './ui/form';

export const enum PdfParserType {
  MinerU = 'mineru',
  DotsOCR = 'dots_ocr',
}

export function PdfParserFormField({
  name = 'parser_config.layout_recognize',
  horizontal = true,
  label,
}: {
  name?: string;
  horizontal?: boolean;
  label?: ReactNode;
}) {
  const form = useFormContext();
  const { t } = useTranslation();

  const options = [
    {
      label: 'MinerU (vLLM)',
      value: PdfParserType.MinerU,
    },
    {
      label: 'DotsOCR (vLLM)',
      value: PdfParserType.DotsOCR,
    },
  ];

  return (
    <FormField
      control={form.control}
      name={name}
      render={({ field }) => {
        // Map layout_recognize value to pdf_parser display value
        const getDisplayValue = (value: string | undefined) => {
          if (!value) return '';
          if (value === 'mineru') return PdfParserType.MinerU;
          if (value === 'dots_ocr') return PdfParserType.DotsOCR;
          // Default to MinerU for unknown values
          return PdfParserType.MinerU;
        };

        const handleChange = (value: string) => {
          // Update layout_recognize field based on pdf_parser selection
          if (value === PdfParserType.MinerU) {
            field.onChange('mineru');
          } else if (value === PdfParserType.DotsOCR) {
            field.onChange('dots_ocr');
          }
        };

        return (
          <FormItem className={'items-center space-y-0 '}>
            <div
              className={cn('flex', {
                'flex-col ': !horizontal,
                'items-center': horizontal,
              })}
            >
              <FormLabel
                tooltip={t('knowledgeConfiguration.pdfParserTip')}
                className={cn('text-sm text-text-secondary whitespace-wrap', {
                  ['w-1/4']: horizontal,
                })}
              >
                {label || t('knowledgeConfiguration.pdfParser')}
              </FormLabel>
              <div className={horizontal ? 'w-3/4' : 'w-full'}>
                <FormControl>
                  <SelectWithSearch
                    value={getDisplayValue(field.value)}
                    onChange={handleChange}
                    options={options}
                    placeholder={t('knowledgeConfiguration.selectPdfParser')}
                  ></SelectWithSearch>
                </FormControl>
              </div>
            </div>
            <div className="flex pt-1">
              <div className={horizontal ? 'w-1/4' : 'w-full'}></div>
              <FormMessage />
            </div>
          </FormItem>
        );
      }}
    />
  );
}
