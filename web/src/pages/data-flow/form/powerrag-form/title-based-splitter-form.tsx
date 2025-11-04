import { Form, Input, InputNumber } from 'antd';
import { useTranslation } from 'react-i18next';

const TitleBasedSplitterForm = () => {
  const { t } = useTranslation();

  return (
    <>
      <Form.Item
        label={t('powerrag.titleBasedSplitter.titleLevel')}
        name="title_level"
        initialValue={3}
        tooltip={t('powerrag.titleBasedSplitter.titleLevelTooltip')}
      >
        <InputNumber min={1} max={6} style={{ width: '100%' }} />
      </Form.Item>

      <Form.Item
        label={t('powerrag.titleBasedSplitter.chunkTokenNum')}
        name="chunk_token_num"
        initialValue={256}
        tooltip={t('powerrag.titleBasedSplitter.chunkTokenNumTooltip')}
      >
        <InputNumber min={50} max={2048} style={{ width: '100%' }} />
      </Form.Item>

      <Form.Item
        label={t('powerrag.titleBasedSplitter.delimiter')}
        name="delimiter"
        initialValue="\n!?;。；！？"
        tooltip={t('powerrag.titleBasedSplitter.delimiterTooltip')}
      >
        <Input placeholder="\n!?;。；！？" />
      </Form.Item>
    </>
  );
};

export default TitleBasedSplitterForm;
