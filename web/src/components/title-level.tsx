import { useTranslate } from '@/hooks/common-hooks';
import { Form, Select } from 'antd';

interface IProps {
  initialValue?: number;
}

/**
 * TitleLevel component for Ant Design Form
 * Reuses the same logic and options as TitleLevelFormField (for react-hook-form)
 */
const TitleLevel = ({ initialValue = 3 }: IProps) => {
  const { t } = useTranslate('knowledgeConfiguration');

  return (
    <Form.Item
      name={['parser_config', 'title_level']}
      label={t('titleLevel')}
      tooltip={t('titleLevelDescription')}
      initialValue={initialValue}
      rules={[{ required: true, message: t('selectTitleLevel') }]}
    >
      <Select placeholder={t('selectTitleLevel')}>
        <Select.Option value={1}>1</Select.Option>
        <Select.Option value={2}>2</Select.Option>
        <Select.Option value={3}>3</Select.Option>
        <Select.Option value={4}>4</Select.Option>
        <Select.Option value={5}>5</Select.Option>
        <Select.Option value={6}>6</Select.Option>
      </Select>
    </Form.Item>
  );
};

export default TitleLevel;
