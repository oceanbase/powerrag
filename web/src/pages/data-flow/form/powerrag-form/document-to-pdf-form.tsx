import { Form, Select } from 'antd';
import { useTranslation } from 'react-i18next';

const DocumentToPDFForm = () => {
  const { t } = useTranslation();

  return (
    <>
      <Form.Item
        label={t('powerrag.documentToPdf.formatType')}
        name="format_type"
        initialValue="office"
        tooltip={t('powerrag.documentToPdf.formatTypeTooltip')}
      >
        <Select>
          <Select.Option value="office">Office Documents</Select.Option>
          <Select.Option value="html">HTML Documents</Select.Option>
        </Select>
      </Form.Item>
    </>
  );
};

export default DocumentToPDFForm;
