import { Form, InputNumber, Select, Switch } from 'antd';
import { useTranslation } from 'react-i18next';

const EntityExtractorForm = () => {
  const { t } = useTranslation();

  return (
    <>
      <Form.Item
        label={t('powerrag.entityExtractor.entityTypes')}
        name="entity_types"
        initialValue={[
          'PERSON',
          'ORG',
          'GPE',
          'MONEY',
          'DATE',
          'TIME',
          'EMAIL',
          'PHONE',
        ]}
        tooltip={t('powerrag.entityExtractor.entityTypesTooltip')}
      >
        <Select
          mode="multiple"
          placeholder={t('powerrag.entityExtractor.selectEntityTypes')}
        >
          <Select.Option value="PERSON">Person</Select.Option>
          <Select.Option value="ORG">Organization</Select.Option>
          <Select.Option value="GPE">Geopolitical Entity</Select.Option>
          <Select.Option value="MONEY">Money</Select.Option>
          <Select.Option value="DATE">Date</Select.Option>
          <Select.Option value="TIME">Time</Select.Option>
          <Select.Option value="EMAIL">Email</Select.Option>
          <Select.Option value="PHONE">Phone</Select.Option>
        </Select>
      </Form.Item>

      <Form.Item
        label={t('powerrag.entityExtractor.useRegex')}
        name="use_regex"
        valuePropName="checked"
        initialValue={true}
        tooltip={t('powerrag.entityExtractor.useRegexTooltip')}
      >
        <Switch />
      </Form.Item>

      <Form.Item
        label={t('powerrag.entityExtractor.useLlm')}
        name="use_llm"
        valuePropName="checked"
        initialValue={false}
        tooltip={t('powerrag.entityExtractor.useLlmTooltip')}
      >
        <Switch />
      </Form.Item>

      <Form.Item
        label={t('powerrag.entityExtractor.minLength')}
        name="min_length"
        initialValue={2}
      >
        <InputNumber min={1} max={100} style={{ width: '100%' }} />
      </Form.Item>

      <Form.Item
        label={t('powerrag.entityExtractor.maxLength')}
        name="max_length"
        initialValue={50}
      >
        <InputNumber min={1} max={200} style={{ width: '100%' }} />
      </Form.Item>
    </>
  );
};

export default EntityExtractorForm;
