import { Form, Input, InputNumber } from 'antd';
import { useTranslation } from 'react-i18next';

const RegexBasedSplitterForm = () => {
  const { t } = useTranslation();

  return (
    <>
      <Form.Item
        label={t('powerrag.regexBasedSplitter.pattern')}
        name="pattern"
        initialValue="[.!?]+\s*"
        tooltip={t('powerrag.regexBasedSplitter.patternTooltip')}
      >
        <Input placeholder="[.!?]+\s*" />
      </Form.Item>

      <Form.Item
        label={t('powerrag.regexBasedSplitter.chunkTokenNum')}
        name="chunk_token_num"
        initialValue={512}
        tooltip={t('powerrag.regexBasedSplitter.chunkTokenNumTooltip')}
      >
        <InputNumber min={50} max={2048} style={{ width: '100%' }} />
      </Form.Item>

      <Form.Item
        label={t('powerrag.regexBasedSplitter.minChunkTokens')}
        name="min_chunk_tokens"
        initialValue={128}
        tooltip={t('powerrag.regexBasedSplitter.minChunkTokensTooltip')}
      >
        <InputNumber min={32} max={1024} style={{ width: '100%' }} />
      </Form.Item>
    </>
  );
};

export default RegexBasedSplitterForm;
