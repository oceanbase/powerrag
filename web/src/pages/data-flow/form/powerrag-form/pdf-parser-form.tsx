import { Form, InputNumber, Switch } from 'antd';
import { useTranslation } from 'react-i18next';

const PDFParserForm = () => {
  const { t } = useTranslation();

  return (
    <>
      <Form.Item
        label={t('powerrag.pdfParser.formulaEnable')}
        name="formula_enable"
        valuePropName="checked"
        initialValue={true}
        tooltip={t('powerrag.pdfParser.formulaEnableTooltip')}
      >
        <Switch />
      </Form.Item>

      <Form.Item
        label={t('powerrag.pdfParser.enableOcr')}
        name="enable_ocr"
        valuePropName="checked"
        initialValue={false}
        tooltip={t('powerrag.pdfParser.enableOcrTooltip')}
      >
        <Switch />
      </Form.Item>

      <Form.Item
        label={t('powerrag.pdfParser.fromPage')}
        name="from_page"
        initialValue={0}
      >
        <InputNumber min={0} max={10000} style={{ width: '100%' }} />
      </Form.Item>

      <Form.Item
        label={t('powerrag.pdfParser.toPage')}
        name="to_page"
        initialValue={100000}
      >
        <InputNumber min={1} max={100000} style={{ width: '100%' }} />
      </Form.Item>
    </>
  );
};

export default PDFParserForm;
