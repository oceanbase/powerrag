import { MaxTokenNumberFormField } from '@/components/max-token-number-from-field';
import { PdfParserFormField } from '@/components/pdf-parser-form-field';
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { useFormContext } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import {
  ConfigurationFormContainer,
  MainContainer,
} from '../configuration-form-container';

function MinChunkTokensFormField() {
  const form = useFormContext();
  const { t } = useTranslation();

  return (
    <FormField
      control={form.control}
      name="parser_config.min_chunk_tokens"
      render={({ field }) => (
        <FormItem>
          <FormLabel
            tooltip={t('knowledgeConfiguration.minChunkTokensDescription')}
          >
            {t('knowledgeConfiguration.minChunkTokens')}
          </FormLabel>
          <FormControl>
            <Input
              type="number"
              min="32"
              max="1024"
              {...field}
              onChange={(e) => field.onChange(Number(e.target.value))}
            />
          </FormControl>
        </FormItem>
      )}
    />
  );
}

export function SmartConfiguration() {
  return (
    <MainContainer>
      <ConfigurationFormContainer>
        <PdfParserFormField />
        <MaxTokenNumberFormField initialValue={256}></MaxTokenNumberFormField>
        <MinChunkTokensFormField />
      </ConfigurationFormContainer>
    </MainContainer>
  );
}
