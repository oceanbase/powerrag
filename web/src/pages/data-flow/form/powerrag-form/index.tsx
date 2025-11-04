import { Operator } from '../../constant';
import DocumentToPDFForm from './document-to-pdf-form';
import EntityExtractorForm from './entity-extractor-form';
import PDFParserForm from './pdf-parser-form';
import RegexBasedSplitterForm from './regex-based-splitter-form';
import SmartBasedSplitterForm from './smart-based-splitter-form';
import TitleBasedSplitterForm from './title-based-splitter-form';

export const PowerRAGFormConfigMap = {
  [Operator.PowerRAGPDFParser]: {
    component: PDFParserForm,
  },
  [Operator.PowerRAGDocumentToPDF]: {
    component: DocumentToPDFForm,
  },
  [Operator.PowerRAGTitleBasedSplitter]: {
    component: TitleBasedSplitterForm,
  },
  [Operator.PowerRAGRegexBasedSplitter]: {
    component: RegexBasedSplitterForm,
  },
  [Operator.PowerRAGSmartBasedSplitter]: {
    component: SmartBasedSplitterForm,
  },
  [Operator.PowerRAGEntityExtractor]: {
    component: EntityExtractorForm,
  },
};

export default PowerRAGFormConfigMap;
