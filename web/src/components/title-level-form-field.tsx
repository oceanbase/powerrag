import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
} from '@/components/ui/form';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useFormContext } from 'react-hook-form';
import { useTranslation } from 'react-i18next';

export function TitleLevelFormField() {
  const form = useFormContext();
  const { t } = useTranslation();

  return (
    <FormField
      control={form.control}
      name="parser_config.title_level"
      render={({ field }) => (
        <FormItem>
          <FormLabel
            tooltip={t('knowledgeConfiguration.titleLevelDescription')}
          >
            {t('knowledgeConfiguration.titleLevel')}
          </FormLabel>
          <Select
            onValueChange={(value) => field.onChange(Number(value))}
            value={String(field.value ?? 3)}
          >
            <FormControl>
              <SelectTrigger>
                <SelectValue
                  placeholder={t('knowledgeConfiguration.selectTitleLevel')}
                />
              </SelectTrigger>
            </FormControl>
            <SelectContent>
              <SelectItem value="1">1</SelectItem>
              <SelectItem value="2">2</SelectItem>
              <SelectItem value="3">3</SelectItem>
              <SelectItem value="4">4</SelectItem>
              <SelectItem value="5">5</SelectItem>
              <SelectItem value="6">6</SelectItem>
            </SelectContent>
          </Select>
        </FormItem>
      )}
    />
  );
}
