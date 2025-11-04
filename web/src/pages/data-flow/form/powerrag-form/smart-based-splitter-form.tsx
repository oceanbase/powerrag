import { Form, InputNumber } from 'antd';
import { useTranslation } from 'react-i18next';

const SmartBasedSplitterForm = () => {
  const { t } = useTranslation();

  return (
    <>
      <Form.Item
        label={t('powerrag.smartBasedSplitter.chunkTokenNum')}
        name="chunk_token_num"
        initialValue={256}
        tooltip={t('powerrag.smartBasedSplitter.chunkTokenNumTooltip')}
      >
        <InputNumber min={50} max={2048} style={{ width: '100%' }} />
      </Form.Item>

      <Form.Item
        label={t('powerrag.smartBasedSplitter.minChunkTokens')}
        name="min_chunk_tokens"
        initialValue={64}
        tooltip={t('powerrag.smartBasedSplitter.minChunkTokensTooltip')}
      >
        <InputNumber min={32} max={1024} style={{ width: '100%' }} />
      </Form.Item>
    </>
  );
};

export default SmartBasedSplitterForm;
