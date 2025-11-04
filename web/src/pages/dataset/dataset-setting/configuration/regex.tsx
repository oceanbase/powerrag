import { DelimiterFormField } from '@/components/delimiter-form-field';
import { MaxTokenNumberFormField } from '@/components/max-token-number-from-field';
import { PdfParserFormField } from '@/components/pdf-parser-form-field';
import { RegexPatternFormField } from '@/components/regex-pattern-form-field';
import {
  ConfigurationFormContainer,
  MainContainer,
} from '../configuration-form-container';

export function RegexConfiguration() {
  return (
    <MainContainer>
      <ConfigurationFormContainer>
        <RegexPatternFormField />
        <DelimiterFormField></DelimiterFormField>
        <PdfParserFormField />
        <MaxTokenNumberFormField initialValue={512}></MaxTokenNumberFormField>
      </ConfigurationFormContainer>
    </MainContainer>
  );
}
