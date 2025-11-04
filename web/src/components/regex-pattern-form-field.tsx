import { useFormContext } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from './ui/form';
import { Input } from './ui/input';

export function RegexPatternFormField() {
  const { t } = useTranslation();
  const form = useFormContext();

  return (
    <FormField
      control={form.control}
      name={'parser_config.regex_pattern'}
      render={({ field }) => {
        if (typeof field.value === 'undefined') {
          // default value set
          form.setValue('parser_config.regex_pattern', '[.!?]+\\s*');
        }
        return (
          <FormItem className=" items-center space-y-0 ">
            <div className="flex items-center gap-1">
              <FormLabel
                required
                tooltip={t('knowledgeDetails.regexPatternTip')}
                className="text-sm text-text-secondary whitespace-break-spaces w-1/4"
              >
                {t('knowledgeDetails.regexPattern')}
              </FormLabel>
              <div className="w-3/4">
                <FormControl>
                  <Input
                    {...field}
                    placeholder="[.!?]+\\s*"
                    className="bg-bg-base"
                  />
                </FormControl>
              </div>
            </div>
            <div className="flex pt-1">
              <div className="w-1/4"></div>
              <FormMessage />
            </div>
          </FormItem>
        );
      }}
    />
  );
}
